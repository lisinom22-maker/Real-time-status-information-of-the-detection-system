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

"""Render ROS status messages with native, accessible Qt widgets."""

from datetime import datetime

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QFormLayout, QGroupBox, QLabel, QProgressBar, QVBoxLayout, QWidget,
)
from status_interfaces.msg import SystemStatus


class StatusWindow(QWidget):
    """Show eight readings and an explicit message freshness state."""

    def __init__(self):
        """Build a compact resizable window with selectable reading text."""
        super().__init__()
        self.setWindowTitle('系统实时状态 · ROS2')
        self.resize(560, 420)
        self.setMinimumSize(420, 360)
        layout = QVBoxLayout(self)
        title = QLabel('系统实时状态')
        font = title.font()
        font.setPointSize(font.pointSize() + 4)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)
        group = QGroupBox('当前主机状态')
        form = QFormLayout(group)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.values = {}
        fields = (
            ('hostname', '主机名'), ('stamp', '记录时间'),
            ('cpu_percent', 'CPU 使用率'), ('memory_percent', '内存使用率'),
            ('memory_total', '内存总大小'),
            ('memory_available', '剩余内存（可用）'),
            ('net_sent', '累计发送量'), ('net_recv', '累计接收量'),
        )
        for key, caption in fields:
            value = QLabel('—')
            value.setTextFormat(Qt.PlainText)
            value.setWordWrap(True)
            value.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
            value.setFocusPolicy(Qt.StrongFocus)
            value.setAccessibleName(caption)
            self.values[key] = value
            form.addRow(caption, value)
            if key in ('cpu_percent', 'memory_percent'):
                bar = QProgressBar()
                bar.setRange(0, 1000)
                bar.setTextVisible(False)
                bar.setAccessibleName(caption + '进度')
                bar.setValue(0)
                if key == 'cpu_percent':
                    self.cpu_bar = bar
                else:
                    self.memory_bar = bar
                form.addRow('', bar)
        layout.addWidget(group)
        self.connection_label = QLabel()
        self.connection_label.setAccessibleName('数据更新状态')
        self.connection_label.setWordWrap(True)
        layout.addWidget(self.connection_label)
        hint = QLabel('网络为系统累计量；内存为可用内存。')
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addStretch()
        self.set_connection_state('waiting', None)

    def render_status(self, message: SystemStatus) -> None:
        """Replace all displayed readings from a single received message."""
        self.values['hostname'].setText(message.hostname)
        stamp = datetime.fromtimestamp(message.stamp.sec).astimezone()
        offset = stamp.strftime('%z')
        offset = offset[:3] + ':' + offset[3:]
        text = stamp.strftime('%Y-%m-%d %H:%M:%S')
        text += f'.{message.stamp.nanosec // 1000000:03d} {offset}'
        self.values['stamp'].setText(text)
        for key in ('cpu_percent', 'memory_percent'):
            self.values[key].setText(f'{getattr(message, key):.1f} %')
        for key in ('memory_total', 'memory_available'):
            self.values[key].setText(f'{getattr(message, key):.2f} GiB')
        for key in ('net_sent', 'net_recv'):
            self.values[key].setText(f'{getattr(message, key):.2f} MiB')
        self.cpu_bar.setValue(round(message.cpu_percent * 10))
        self.memory_bar.setValue(round(message.memory_percent * 10))

    def set_connection_state(self, state: str, age_seconds: float | None) -> None:
        """Explain whether readings are waiting, current or stale in text."""
        if state == 'waiting':
            text = '状态：等待数据'
        elif state == 'live':
            text = '状态：实时更新'
        else:
            text = f'状态：数据已过期（距上次接收 {age_seconds:.1f} 秒）'
        self.connection_label.setText(text)
