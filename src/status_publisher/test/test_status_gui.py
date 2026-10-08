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

"""Verify displayed data, stale status and bounded event processing."""

import time

from builtin_interfaces.msg import Time
from PyQt5.QtWidgets import QApplication
import pytest
import rclpy
from rclpy.context import Context
from rclpy.parameter import Parameter
from status_interfaces.msg import SystemStatus

from status_publisher import status_window, sys_status_gui


@pytest.fixture(scope='module')
def app():
    """Keep a Qt application alive for real widget tests."""
    return QApplication.instance() or QApplication([])


@pytest.fixture
def context():
    """Release an isolated ROS context after each test."""
    value = Context()
    rclpy.init(context=value)
    yield value
    value.try_shutdown()


def window_factory(app):
    """Require and construct the production window."""
    assert hasattr(status_window, 'StatusWindow'), 'window missing'
    return status_window.StatusWindow()


def sample():
    """Provide literals that expose swapped fields and formatting mistakes."""
    return SystemStatus(
        stamp=Time(sec=1700000000, nanosec=123000000),
        hostname='fixed-host', cpu_percent=25.3, memory_percent=62.5,
        memory_total=8.0, memory_available=3.0, net_sent=2.0, net_recv=5.0)


def test_all_fields_and_units(app):
    """Render every field from the same message without unit ambiguity."""
    window = window_factory(app)
    try:
        window.render_status(sample())
        assert window.values['hostname'].text() == 'fixed-host'
        stamp = window.values['stamp'].text()
        assert '.123 ' in stamp and len(stamp) >= 29
        expected = {
            'cpu_percent': '25.3 %', 'memory_percent': '62.5 %',
            'memory_total': '8.00 GiB', 'memory_available': '3.00 GiB',
            'net_sent': '2.00 MiB', 'net_recv': '5.00 MiB',
        }
        for field, text in expected.items():
            assert window.values[field].text() == text
        assert window.cpu_bar.value() == 253
        assert window.memory_bar.value() == 625
    finally:
        window.close()


def test_waiting_and_zero_values(app):
    """Distinguish unknown readings from valid zero traffic."""
    window = window_factory(app)
    try:
        assert all(value.text() == '—' for value in window.values.values())
        assert '等待数据' in window.connection_label.text()
        message = sample()
        message.hostname = 'long-host-' * 30
        message.net_sent = 0.0
        message.net_recv = 0.0
        window.render_status(message)
        assert window.values['hostname'].text() == message.hostname
        assert window.values['net_sent'].text() == '0.00 MiB'
        assert window.values['net_recv'].text() == '0.00 MiB'
    finally:
        window.close()


def test_waiting_live_stale_recovery(app, context):
    """Use elapsed arrival time, preserve old samples, recover on new data."""
    assert hasattr(sys_status_gui, 'SysStatusGui'), 'GUI subscriber missing'
    window = window_factory(app)
    clock = [10.0]
    node = sys_status_gui.SysStatusGui(
        window, context=context, monotonic=lambda: clock[0])
    try:
        node.update_window()
        assert '等待数据' in window.connection_label.text()
        node.receive_status(sample())
        node.update_window()
        assert '实时更新' in window.connection_label.text()
        clock[0] = 13.0
        node.update_window()
        assert '实时更新' in window.connection_label.text()
        clock[0] = 13.01
        node.update_window()
        assert '数据已过期' in window.connection_label.text()
        assert window.values['hostname'].text() == 'fixed-host'
        new_message = sample()
        new_message.hostname = 'recovered-host'
        node.receive_status(new_message)
        node.update_window()
        assert '实时更新' in window.connection_label.text()
        assert window.values['hostname'].text() == 'recovered-host'
    finally:
        node.destroy_node()
        window.close()


@pytest.mark.parametrize('timeout', [0.0, -1.0, float('nan'), float('inf')])
def test_invalid_timeout(app, context, timeout):
    """Reject an invalid age threshold before entering the Qt loop."""
    assert hasattr(sys_status_gui, 'SysStatusGui')
    window = window_factory(app)
    try:
        with pytest.raises(ValueError, match='stale_timeout'):
            sys_status_gui.SysStatusGui(
                window, context=context,
                parameter_overrides=[Parameter('stale_timeout', value=timeout)])
    finally:
        window.close()


def test_runtime_ticks_and_idempotent_close(app, context):
    """A GUI frame must not block while waiting for a ROS message."""
    assert hasattr(sys_status_gui, 'GuiRuntime'), 'event integration missing'
    window = window_factory(app)
    node = sys_status_gui.SysStatusGui(window, context=context)
    runtime = sys_status_gui.GuiRuntime(node, window)
    start = time.monotonic()
    runtime.tick()
    assert time.monotonic() - start < 0.2
    assert runtime.ros_timer.interval() == 50
    runtime.close()
    runtime.close()
    assert not runtime.ros_timer.isActive()
    assert not runtime.state_timer.isActive()
    assert not context.ok()
    window.close()


def test_signal_quit_is_deferred_to_timer(app, context, monkeypatch):
    """Do not reenter ROS cleanup from a signal interrupting a callback."""
    from unittest.mock import Mock

    window = window_factory(app)
    node = sys_status_gui.SysStatusGui(window, context=context)
    runtime = sys_status_gui.GuiRuntime(node, window)
    quit_app = Mock()
    monkeypatch.setattr(app, 'quit', quit_app)
    try:
        assert hasattr(runtime, 'request_quit'), 'deferred quit not implemented'
        runtime.request_quit()
        quit_app.assert_not_called()
        runtime.tick()
        quit_app.assert_called_once()
    finally:
        runtime.close()
        window.close()


@pytest.mark.parametrize('field,value', [
    ('cpu_percent', float('nan')), ('cpu_percent', float('inf')),
    ('cpu_percent', -1.0), ('memory_percent', 101.0),
    ('memory_total', 0.0), ('memory_total', float('inf')),
    ('memory_available', -1.0), ('memory_available', 9.0),
    ('net_sent', -1.0), ('net_recv', float('nan')),
])
def test_invalid_message_does_not_refresh_valid_data(app, context, field, value):
    """Reject bad ROS payloads, preserve the last good sample and its age."""
    window = window_factory(app)
    clock = [10.0]
    node = sys_status_gui.SysStatusGui(
        window, context=context, monotonic=lambda: clock[0])
    try:
        node.receive_status(sample())
        node.update_window()
        clock[0] = 14.0
        invalid = sample()
        invalid.hostname = 'invalid-host'
        setattr(invalid, field, value)
        node.receive_status(invalid)
        node.update_window()
        assert '数据已过期' in window.connection_label.text()
        assert window.values['hostname'].text() == 'fixed-host'
        assert window.values['cpu_percent'].text() == '25.3 %'
        node.receive_status(sample())
        node.update_window()
        assert '实时更新' in window.connection_label.text()
    finally:
        node.destroy_node()
        window.close()
