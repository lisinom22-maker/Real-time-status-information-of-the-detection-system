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

"""Collect nonblocking system metrics in GiB and cumulative MiB."""

from dataclasses import dataclass
import math
import platform

import psutil


@dataclass(frozen=True)
class SystemMetrics:
    """Represent one validated system sample without a ROS timestamp."""

    hostname: str
    cpu_percent: float
    memory_percent: float
    memory_total: float
    memory_available: float
    net_sent: float
    net_recv: float


class MetricsCollectionError(RuntimeError):
    """Report an unavailable or invalid OS measurement."""


class MetricsCollector:
    """Read each OS counter once and convert bytes into documented units."""

    def __init__(self, source=psutil, hostname_provider=platform.node):
        """Accept an OS measurement provider and hostname function."""
        self._source = source
        self._hostname_provider = hostname_provider

    def warm_up(self) -> None:
        """Discard the first nonblocking CPU reading."""
        try:
            self._source.cpu_percent(interval=None)
        except (OSError, psutil.Error, ValueError) as exc:
            raise MetricsCollectionError(str(exc)) from exc

    def sample(self) -> SystemMetrics:
        """Return validated data; propagate failure without fake zero values."""
        try:
            cpu = float(self._source.cpu_percent(interval=None))
            memory = self._source.virtual_memory()
            network = self._source.net_io_counters(pernic=False)
            if network is None:
                raise ValueError('network counters unavailable')
            total = float(memory.total)
            available = float(memory.available)
            percent = float(memory.percent)
            sent = float(network.bytes_sent)
            recv = float(network.bytes_recv)
            values = (cpu, percent, total, available, sent, recv)
            if not all(math.isfinite(value) for value in values):
                raise ValueError('nonfinite system measurement')
            if not (0 <= cpu <= 100 and 0 <= percent <= 100):
                raise ValueError('percentage outside 0..100')
            if not (total > 0 and 0 <= available <= total):
                raise ValueError('invalid total or available memory')
            if sent < 0 or recv < 0:
                raise ValueError('negative network counter')
            return SystemMetrics(
                hostname=self._hostname_provider() or 'unknown',
                cpu_percent=cpu,
                memory_percent=percent,
                memory_total=total / 1024**3,
                memory_available=available / 1024**3,
                net_sent=sent / 1024**2,
                net_recv=recv / 1024**2,
            )
        except (OSError, psutil.Error, ValueError, TypeError) as exc:
            raise MetricsCollectionError(str(exc)) from exc
