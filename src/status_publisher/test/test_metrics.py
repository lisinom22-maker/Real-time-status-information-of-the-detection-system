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

"""Verify metric units, warm-up and failure recovery boundaries."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from status_publisher import metrics


@pytest.fixture
def source():
    """Supply deterministic OS counters at the external API boundary."""
    return Mock(
        cpu_percent=Mock(side_effect=[0.0, 25.0, 35.0]),
        virtual_memory=Mock(return_value=SimpleNamespace(
            total=8589934592, available=3221225472, percent=62.5)),
        net_io_counters=Mock(return_value=SimpleNamespace(
            bytes_sent=2097152, bytes_recv=5242880)),
    )


def collect(source, hostname='test-host'):
    """Run the actual collector with fixed external observations."""
    assert hasattr(metrics, 'MetricsCollector'), 'collector not implemented'
    collector = metrics.MetricsCollector(
        source=source, hostname_provider=lambda: hostname)
    collector.warm_up()
    return collector.sample()


def test_units_and_cpu_warmup(source):
    """Catch swapped counters, incorrect powers and publishing CPU warm-up."""
    result = collect(source)
    assert result.hostname == 'test-host'
    assert result.cpu_percent == 25.0
    assert result.memory_percent == 62.5
    assert result.memory_total == 8.0
    assert result.memory_available == 3.0
    assert result.net_sent == 2.0
    assert result.net_recv == 5.0
    source.cpu_percent.assert_has_calls([
        ((), {'interval': None}), ((), {'interval': None})])
    assert source.virtual_memory.call_count == 1
    assert source.net_io_counters.call_count == 1


def test_empty_hostname(source):
    """Do not display an empty host identifier."""
    assert collect(source, '').hostname == 'unknown'


@pytest.mark.parametrize('field,value', [
    ('total', 0), ('total', -1), ('available', -1),
    ('available', 17179869184), ('percent', -1), ('percent', 101),
    ('total', float('inf')), ('available', float('nan')),
])
def test_invalid_memory(source, field, value):
    """Reject impossible or nonfinite memory rather than publishing it."""
    assert hasattr(metrics, 'MetricsCollectionError')
    setattr(source.virtual_memory.return_value, field, value)
    with pytest.raises(metrics.MetricsCollectionError):
        collect(source)


@pytest.mark.parametrize('value', [-1.0, 101.0, float('nan'), float('inf')])
def test_invalid_cpu(source, value):
    """Reject invalid percentages."""
    assert hasattr(metrics, 'MetricsCollectionError')
    source.cpu_percent.side_effect = [0.0, value]
    with pytest.raises(metrics.MetricsCollectionError):
        collect(source)


@pytest.mark.parametrize('field,value', [
    ('bytes_sent', -1), ('bytes_recv', -1),
    ('bytes_sent', float('inf')), ('bytes_recv', float('nan')),
])
def test_invalid_network(source, field, value):
    """Reject corrupt cumulative counters."""
    assert hasattr(metrics, 'MetricsCollectionError')
    setattr(source.net_io_counters.return_value, field, value)
    with pytest.raises(metrics.MetricsCollectionError):
        collect(source)


def test_no_network_counter(source):
    """Missing counters must not become fake zero traffic."""
    assert hasattr(metrics, 'MetricsCollectionError')
    source.net_io_counters.return_value = None
    with pytest.raises(metrics.MetricsCollectionError):
        collect(source)


def test_sample_recovers_after_os_error(source):
    """A failed sampling round must not prevent the next good round."""
    assert hasattr(metrics, 'MetricsCollector')
    source.virtual_memory.side_effect = [
        OSError('unavailable'), source.virtual_memory.return_value]
    collector = metrics.MetricsCollector(source, lambda: 'test-host')
    collector.warm_up()
    with pytest.raises(metrics.MetricsCollectionError):
        collector.sample()
    assert collector.sample().cpu_percent == 35.0
