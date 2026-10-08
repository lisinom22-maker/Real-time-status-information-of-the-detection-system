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

"""Publish timestamped host status using a nonblocking ROS2 timer."""

import math
import signal
import sys
import time

from rcl_interfaces.msg import ParameterDescriptor, SetParametersResult
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import QoSProfile
from rclpy.signals import SignalHandlerOptions
from status_interfaces.msg import SystemStatus

from status_publisher.metrics import MetricsCollectionError, MetricsCollector


class SysStatusPub(Node):
    """Sample the OS and publish status at a validated fixed period."""

    def __init__(self, collector=None, **kwargs):
        """Create the publisher and discard the CPU baseline reading."""
        super().__init__('sys_status_pub', **kwargs)
        try:
            period = self.declare_parameter(
                'publish_period', 1.0,
                ParameterDescriptor(
                    read_only=True,
                    description='Sampling period in seconds (0.1..60).',
                )).value
            if not math.isfinite(period) or not 0.1 <= period <= 60.0:
                raise ValueError('publish_period must be finite and in 0.1..60 seconds')
            if self.get_parameter('use_sim_time').value:
                raise ValueError('use_sim_time must be false for host monitoring')
            self.add_on_set_parameters_callback(self._validate_clock)
            self._collector = collector if collector is not None else MetricsCollector()
            self._sample_clock = self.get_clock()
            self._monotonic = time.monotonic
            self._last_error = float('-inf')
            self._warmed_up = False
            self.publisher = self.create_publisher(
                SystemStatus, '/system_status', QoSProfile(depth=10))
            self._warm_up()
            self.timer = self.create_timer(period, self.publish_status)
        except Exception:
            self.destroy_node()
            raise

    def _validate_clock(self, parameters):
        for parameter in parameters:
            if parameter.name == 'use_sim_time' and parameter.value:
                return SetParametersResult(
                    successful=False, reason='host monitoring requires wall-clock time')
        return SetParametersResult(successful=True)

    def _log_failure(self, error):
        now = self._monotonic()
        if now - self._last_error >= 5.0:
            self.get_logger().error(f'System sampling failed: {error}')
            self._last_error = now

    def _warm_up(self):
        try:
            self._collector.warm_up()
            self._warmed_up = True
        except MetricsCollectionError as exc:
            self._log_failure(exc)

    def publish_status(self) -> None:
        """Publish one valid round, or skip a failed round and retry later."""
        if not self._warmed_up:
            self._warm_up()
            return
        stamp = self._sample_clock.now().to_msg()
        try:
            sample = self._collector.sample()
        except MetricsCollectionError as exc:
            self._log_failure(exc)
            return
        message = SystemStatus(
            stamp=stamp,
            hostname=sample.hostname,
            cpu_percent=sample.cpu_percent,
            memory_percent=sample.memory_percent,
            memory_total=sample.memory_total,
            memory_available=sample.memory_available,
            net_sent=sample.net_sent,
            net_recv=sample.net_recv,
        )
        self.publisher.publish(message)


def main(args=None):
    """Run the publisher until interrupted and always release ROS resources."""
    node = None
    rclpy.init(args=args, signal_handler_options=SignalHandlerOptions.NO)
    try:
        node = SysStatusPub()
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    except (ValueError, rclpy.exceptions.ParameterException) as exc:
        print(f'Cannot start sys_status_pub: {exc}', file=sys.stderr)
        return 1
    finally:
        # Launch and the terminal can both send SIGINT to the child.
        previous_signal = signal.signal(signal.SIGINT, signal.SIG_IGN)
        try:
            if node is not None:
                node.destroy_node()
            rclpy.try_shutdown()
        finally:
            signal.signal(signal.SIGINT, previous_signal)
    return 0


if __name__ == '__main__':
    sys.exit(main())
