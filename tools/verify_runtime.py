#!/usr/bin/env python3
"""Exercise real in-process ROS delivery and Qt for a timed smoke run."""

import argparse
import json
import platform
from pathlib import Path
import time

from PyQt5.QtCore import PYQT_VERSION_STR, QT_VERSION_STR
from PyQt5.QtWidgets import QApplication
import psutil
import rclpy
from rclpy.context import Context
from rclpy.parameter import Parameter
from status_interfaces.msg import SystemStatus

from status_publisher.status_window import StatusWindow
from status_publisher.sys_status_gui import GuiRuntime, SysStatusGui
from status_publisher.sys_status_pub import SysStatusPub


def run(seconds, output, preview):
    """Observe 1 Hz/2 Hz delivery, stale recovery and event responsiveness."""
    app = QApplication([])
    context = Context()
    rclpy.init(context=context)
    window = StatusWindow()
    gui = SysStatusGui(window, context=context)
    runtime = GuiRuntime(gui, window)
    probe = rclpy.create_node('acceptance_probe', context=context)
    arrivals = []
    messages = []

    def receive(message):
        arrivals.append(time.monotonic())
        messages.append(message)

    subscription = probe.create_subscription(SystemStatus, '/system_status', receive, 10)
    runtime.executor.add_node(probe)

    def publisher(period):
        node = SysStatusPub(context=context, parameter_overrides=[
            Parameter('publish_period', value=period)])
        runtime.executor.add_node(node)
        return node

    pub = publisher(1.0)
    window.show()
    started = time.monotonic()
    captured = False
    stale_seen = False
    recovered = False
    switched = False
    rates = {}
    max_loop_gap = 0.0
    previous = started
    try:
        while time.monotonic() - started < seconds:
            now = time.monotonic()
            elapsed = now - started
            max_loop_gap = max(max_loop_gap, now - previous)
            previous = now
            app.processEvents()
            state = window.connection_label.text()
            if elapsed > 5 and not captured and '实时更新' in state:
                preview.parent.mkdir(parents=True, exist_ok=True)
                assert window.grab().save(str(preview)), 'preview save failed'
                captured = True
            if elapsed > 35 and '1hz' not in rates:
                observed = [x for x in arrivals if 3 <= x - started <= 35]
                rates['1hz'] = (len(observed) - 1) / (observed[-1] - observed[0])
                pub.timer.cancel()
            if elapsed > 38 and '数据已过期' in state:
                stale_seen = True
            if elapsed > 40 and not switched:
                runtime.executor.remove_node(pub)
                pub.destroy_node()
                pub = publisher(0.5)
                switched = True
            if switched and elapsed > 41 and '实时更新' in state:
                recovered = True
            if elapsed > 75 and '2hz' not in rates:
                observed = [x for x in arrivals if 43 <= x - started <= 75]
                rates['2hz'] = (len(observed) - 1) / (observed[-1] - observed[0])
            time.sleep(0.01)
        assert len(messages) > 0, 'no ROS deliveries'
        assert captured and stale_seen and recovered, 'freshness transitions missing'
        assert 0.9 <= rates['1hz'] <= 1.1, rates
        assert 1.8 <= rates['2hz'] <= 2.2, rates
        assert all(0 <= x.cpu_percent <= 100 for x in messages)
        assert all(0 <= x.memory_percent <= 100 for x in messages)
        assert all(0 <= x.memory_available <= x.memory_total for x in messages)
        assert all(x.net_sent >= 0 and x.net_recv >= 0 for x in messages)
        report = {
            'scope': 'real ROS2 same-process delivery + Qt event loop; '
                     'not a desktop manipulation or cross-process DDS test',
            'elapsed_seconds': time.monotonic() - started,
            'message_count': len(messages),
            'rates_hz': rates,
            'stale_seen': stale_seen,
            'recovered': recovered,
            'maximum_loop_gap_seconds': max_loop_gap,
            'qt_platform': app.platformName(),
            'versions': {'python': platform.python_version(),
                         'psutil': psutil.__version__,
                         'pyqt': PYQT_VERSION_STR, 'qt': QT_VERSION_STR},
            'hostname': messages[-1].hostname,
            'preview': str(preview),
            'last_sample': {
                field: getattr(messages[-1], field)
                for field in ('cpu_percent', 'memory_percent', 'memory_total',
                              'memory_available', 'net_sent', 'net_recv')},
        }
    finally:
        runtime.executor.remove_node(pub)
        pub.destroy_node()
        runtime.executor.remove_node(probe)
        probe.destroy_node()
        start_close = time.monotonic()
        runtime.close()
        window.close()
    report['cleanup_seconds'] = time.monotonic() - start_close
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))


def main():
    """Use the installed ROS packages and an available Qt backend."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', type=float, default=600)
    parser.add_argument('--output', type=Path, default=Path('docs/runtime-results.json'))
    parser.add_argument('--preview', type=Path,
                        default=Path('docs/images/offscreen-preview.png'))
    args = parser.parse_args()
    if args.seconds < 80:
        parser.error('--seconds must be at least 80 to measure both rates')
    run(args.seconds, args.output, args.preview)


if __name__ == '__main__':
    main()
