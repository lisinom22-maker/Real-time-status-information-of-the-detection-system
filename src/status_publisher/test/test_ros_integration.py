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

"""Verify actual ROS delivery into the Qt window in one process."""

import time

from PyQt5.QtWidgets import QApplication
import rclpy
from rclpy.context import Context
from rclpy.parameter import Parameter

from status_publisher.status_window import StatusWindow
from status_publisher.sys_status_gui import GuiRuntime, SysStatusGui
from status_publisher.sys_status_pub import SysStatusPub


def test_actual_ros_delivery_and_recovery():
    """Catch wiring/QoS errors that direct callback tests cannot expose."""
    app = QApplication.instance() or QApplication([])
    context = Context()
    rclpy.init(context=context)
    window = StatusWindow()
    gui = SysStatusGui(window, context=context, parameter_overrides=[
        Parameter('stale_timeout', value=0.2)])
    runtime = GuiRuntime(gui, window)
    pub = SysStatusPub(context=context, parameter_overrides=[
        Parameter('publish_period', value=0.1)])
    runtime.executor.add_node(pub)
    try:
        deadline = time.monotonic() + 4.0
        while time.monotonic() < deadline:
            app.processEvents()
            runtime.tick()
            if '实时更新' in window.connection_label.text():
                break
            time.sleep(0.01)
        assert '实时更新' in window.connection_label.text()
        assert window.values['hostname'].text() not in ('—', '')
        assert 'GiB' in window.values['memory_total'].text()
        pub.timer.cancel()
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            app.processEvents()
            runtime.tick()
            if '数据已过期' in window.connection_label.text():
                break
            time.sleep(0.01)
        assert '数据已过期' in window.connection_label.text()
        pub.timer.reset()
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            app.processEvents()
            runtime.tick()
            if '实时更新' in window.connection_label.text():
                break
            time.sleep(0.01)
        assert '实时更新' in window.connection_label.text()
    finally:
        runtime.executor.remove_node(pub)
        pub.destroy_node()
        runtime.close()
        window.close()
