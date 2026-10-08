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

"""Integrate a ROS2 subscriber with the Qt main-thread event loop."""

import math
import os
import signal
import sys
import time

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication
from rcl_interfaces.msg import ParameterDescriptor
import rclpy
from rclpy.executors import ExternalShutdownException, SingleThreadedExecutor
from rclpy.node import Node
from rclpy.qos import QoSProfile
from rclpy.signals import SignalHandlerOptions
from status_interfaces.msg import SystemStatus

from status_publisher.status_window import StatusWindow


class SysStatusGui(Node):
    """Cache ROS samples and update native Qt widgets in their owner thread."""

    def __init__(self, window, monotonic=time.monotonic, **kwargs):
        """Subscribe and validate a read-only elapsed-time threshold."""
        super().__init__('sys_status_gui', **kwargs)
        try:
            self.stale_timeout = self.declare_parameter(
                'stale_timeout', 3.0,
                ParameterDescriptor(
                    read_only=True,
                    description='Positive freshness timeout in seconds.',
                )).value
            if not math.isfinite(self.stale_timeout) or self.stale_timeout <= 0:
                raise ValueError('stale_timeout must be finite and greater than zero')
            self._window = window
            self._monotonic = monotonic
            self._last_received = None
            self._pending = None
            self._last_invalid_warning = float('-inf')
            self.subscription = self.create_subscription(
                SystemStatus, '/system_status', self.receive_status, QoSProfile(depth=10))
        except Exception:
            self.destroy_node()
            raise

    def receive_status(self, message: SystemStatus) -> None:
        """Cache only valid samples without refreshing age on bad payloads."""
        now = self._monotonic()
        values = (message.cpu_percent, message.memory_percent,
                  message.memory_total, message.memory_available,
                  message.net_sent, message.net_recv)
        valid = (
            all(math.isfinite(value) for value in values)
            and 0 <= message.cpu_percent <= 100
            and 0 <= message.memory_percent <= 100
            and message.memory_total > 0
            and 0 <= message.memory_available <= message.memory_total
            and message.net_sent >= 0 and message.net_recv >= 0
        )
        if not valid:
            if now - self._last_invalid_warning >= 5.0:
                self.get_logger().warning('Ignoring invalid system status sample')
                self._last_invalid_warning = now
            return
        self._pending = message
        self._last_received = now

    def update_window(self) -> None:
        """Render new data and mark old data without clearing its values."""
        if self._pending is not None:
            self._window.render_status(self._pending)
            self._pending = None
        if self._last_received is None:
            self._window.set_connection_state('waiting', None)
            return
        age = self._monotonic() - self._last_received
        state = 'stale' if age > self.stale_timeout else 'live'
        self._window.set_connection_state(state, age)


class GuiRuntime:
    """Own a bounded ROS executor and Qt timers with idempotent cleanup."""

    def __init__(self, node, window):
        """Process at most one nonblocking ROS callback every 50 ms."""
        self._node = node
        self._closed = False
        self._quit_requested = False
        self.executor = SingleThreadedExecutor(context=node.context)
        self.executor.add_node(node)
        self.ros_timer = QTimer(window)
        self.ros_timer.setInterval(50)
        self.ros_timer.timeout.connect(self.tick)
        self.state_timer = QTimer(window)
        self.state_timer.setInterval(100)
        self.state_timer.timeout.connect(node.update_window)
        self.ros_timer.start()
        self.state_timer.start()

    def request_quit(self) -> None:
        """Defer signal-triggered exit until no ROS callback is active."""
        self._quit_requested = True

    def tick(self) -> None:
        """Service ROS without blocking pointer, resize or close events."""
        if self._closed:
            return
        if self._quit_requested or not self._node.context.ok():
            QApplication.instance().quit()
            return
        try:
            self.executor.spin_once(timeout_sec=0.0)
            self._node.update_window()
        except ExternalShutdownException:
            QApplication.instance().quit()

    def close(self) -> None:
        """Stop timers before releasing the executor, node and ROS context."""
        if self._closed:
            return
        self._closed = True
        self.ros_timer.stop()
        self.state_timer.stop()
        self.executor.shutdown(timeout_sec=0.0)
        self._node.destroy_node()
        self._node.context.try_shutdown()


def main(args=None):
    """Run the desktop subscriber and handle terminal interruption safely."""
    if not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')
            or os.environ.get('QT_QPA_PLATFORM') in ('offscreen', 'minimal')):
        print('sys_status_gui requires a desktop DISPLAY or WAYLAND_DISPLAY.', file=sys.stderr)
        return 1
    node = None
    runtime = None
    window = None
    previous_signal = None
    rclpy.init(args=args, signal_handler_options=SignalHandlerOptions.NO)
    try:
        app = QApplication.instance() or QApplication([sys.argv[0]])
        window = StatusWindow()
        node = SysStatusGui(window)
        runtime = GuiRuntime(node, window)
        app.aboutToQuit.connect(runtime.close)
        previous_signal = signal.signal(signal.SIGINT, lambda *_: runtime.request_quit())
        window.show()
        return app.exec_()
    except (ValueError, rclpy.exceptions.ParameterException) as exc:
        print(f'Cannot start sys_status_gui: {exc}', file=sys.stderr)
        return 1
    finally:
        if runtime is not None:
            runtime.close()
        elif node is not None:
            node.destroy_node()
        if window is not None:
            window.close()
        rclpy.try_shutdown()
        if previous_signal is not None:
            signal.signal(signal.SIGINT, previous_signal)


if __name__ == '__main__':
    sys.exit(main())
