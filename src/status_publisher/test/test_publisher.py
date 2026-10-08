# Copyright 2026 lisinom22-maker
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Exercise real ROS nodes, message mapping and recovery."""

from types import SimpleNamespace
from unittest.mock import Mock

from builtin_interfaces.msg import Time as TimeMsg
import pytest
import rclpy
from rclpy.context import Context
from rclpy.parameter import Parameter
from rclpy.serialization import deserialize_message, serialize_message
from rclpy.time import Time
from status_interfaces.msg import SystemStatus

from status_publisher import sys_status_pub as publisher_module
from status_publisher.metrics import MetricsCollectionError, SystemMetrics


@pytest.fixture
def context():
    """Isolate each ROS test from global initialization state."""
    value = Context()
    rclpy.init(context=value)
    yield value
    value.try_shutdown()


def make_node(context, period=1.0, collector=None):
    """Construct the real node with external counters controlled."""
    assert hasattr(publisher_module, 'SysStatusPub'), 'publisher missing'
    return publisher_module.SysStatusPub(
        context=context, collector=collector,
        parameter_overrides=[Parameter('publish_period', value=period)])


@pytest.mark.parametrize('period', [0.1, 1.0, 60.0])
def test_period_boundaries(context, period):
    """Honor legal periods without coercing them."""
    node = make_node(context, period, Mock())
    try:
        assert node.timer.timer_period_ns == round(period * 1e9)
        result = node.set_parameters([
            Parameter('publish_period', value=2.0)])[0]
        assert not result.successful
    finally:
        node.destroy_node()


@pytest.mark.parametrize('period', [
    0.0, -1.0, 0.09, 60.1, float('nan'), float('inf'),
])
def test_invalid_period(context, period):
    """Reject periods that could stall or flood the monitor."""
    assert hasattr(publisher_module, 'SysStatusPub')
    with pytest.raises(ValueError, match='publish_period'):
        make_node(context, period, Mock())


def test_payload_and_timestamp(context):
    """Catch swapped values and incorrect timestamp construction."""
    sample = SystemMetrics('fixed-host', 25.0, 62.5, 8.0, 3.0, 2.0, 5.0)
    collector = Mock(sample=Mock(return_value=sample))
    node = make_node(context, collector=collector)
    sink = Mock()
    node.publisher = sink
    node._sample_clock = SimpleNamespace(now=lambda: Time(
        seconds=1700000000, nanoseconds=123000000))
    try:
        node.publish_status()
        message = sink.publish.call_args.args[0]
        assert message.stamp == TimeMsg(sec=1700000000, nanosec=123000000)
        assert message.hostname == 'fixed-host'
        assert message.cpu_percent == 25.0
        assert message.memory_percent == 62.5
        assert message.memory_total == 8.0
        assert message.memory_available == 3.0
        assert message.net_sent == 2.0
        assert message.net_recv == 5.0
        decoded = deserialize_message(serialize_message(message), SystemStatus)
        assert decoded == message
    finally:
        node.destroy_node()


def test_failure_skips_and_recovers(context):
    """Failed rounds emit nothing; good rounds resume immediately."""
    sample = SystemMetrics('fixed-host', 25.0, 62.5, 8.0, 3.0, 2.0, 5.0)
    collector = Mock(sample=Mock(side_effect=[
        MetricsCollectionError('offline'), sample]))
    node = make_node(context, collector=collector)
    sink = Mock()
    node.publisher = sink
    try:
        node.publish_status()
        assert sink.publish.call_count == 0
        node.publish_status()
        assert sink.publish.call_count == 1
        assert sink.publish.call_args.args[0].hostname == 'fixed-host'
    finally:
        node.destroy_node()


def test_error_logging_throttled(context):
    """Repeated OS failures must not flood logs."""
    collector = Mock(sample=Mock(side_effect=MetricsCollectionError('offline')))
    node = make_node(context, collector=collector)
    clock = iter([10.0, 11.0, 14.9, 15.0])
    node._monotonic = lambda: next(clock)
    logger = Mock()
    node.get_logger = lambda: logger
    try:
        for _ in range(4):
            node.publish_status()
        assert logger.error.call_count == 2
    finally:
        node.destroy_node()


def test_simulated_time_rejected(context):
    """Host monitoring must not silently publish paused simulated stamps."""
    assert hasattr(publisher_module, 'SysStatusPub')
    with pytest.raises(ValueError, match='use_sim_time'):
        publisher_module.SysStatusPub(
            context=context, collector=Mock(),
            parameter_overrides=[Parameter('use_sim_time', value=True)])


def test_repeat_sigint_during_cleanup():
    """A second Ctrl+C must not interrupt node destruction."""
    import subprocess
    import sys

    code = '''
import os
import signal
from status_publisher import sys_status_pub as module
class Node:
    def destroy_node(self):
        os.kill(os.getpid(), signal.SIGINT)
        print('cleanup-finished')
def interrupt(node):
    raise KeyboardInterrupt
module.SysStatusPub = Node
module.rclpy.spin = interrupt
raise SystemExit(module.main(args=[]))
'''
    result = subprocess.run(
        [sys.executable, '-c', code], text=True, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert 'cleanup-finished' in result.stdout
    assert 'Traceback' not in result.stderr
