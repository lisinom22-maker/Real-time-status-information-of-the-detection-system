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

"""Verify launch parameters are typed and GUI exit ends the launch."""

import importlib.util
from pathlib import Path

from launch import LaunchContext
from launch.actions import DeclareLaunchArgument, RegisterEventHandler
from launch.events.process import ProcessExited
from launch_ros.actions import Node
from launch_ros.utilities import evaluate_parameters


def test_launch_arguments_and_gui_exit_handler():
    """Catch missing executable wiring and string-valued numeric params."""
    path = Path(__file__).parents[1] / 'launch/system_status.launch.py'
    assert path.exists(), 'launch file missing'
    spec = importlib.util.spec_from_file_location('status_launch', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    description = module.generate_launch_description()
    entities = description.entities
    arguments = [x for x in entities if isinstance(x, DeclareLaunchArgument)]
    assert {x.name for x in arguments} == {'publish_period', 'stale_timeout'}
    nodes = [x for x in entities if isinstance(x, Node)]
    assert len(nodes) == 2
    context = LaunchContext()
    context.launch_configurations.update(publish_period='0.5', stale_timeout='4.0')
    values = [evaluate_parameters(context, x._Node__parameters) for x in nodes]
    assert values[0][0] == {'publish_period': 0.5}
    assert values[1][0] == {'stale_timeout': 4.0}
    handlers = [x for x in entities if isinstance(x, RegisterEventHandler)]
    assert len(handlers) == 1

    def exit_event(action):
        return ProcessExited(
            action=action, pid=1, returncode=0, name='test',
            cmd=['test'], cwd=None, env=None)
    handler = handlers[0].event_handler
    assert handler.matches(exit_event(nodes[1]))
    assert not handler.matches(exit_event(nodes[0]))


def test_launch_repeated_sigint_exits_cleanly():
    """Terminal and launch SIGINT must both leave clean child processes."""
    import os
    import signal
    import subprocess
    import time

    command = ['ros2', 'launch', 'status_publisher', 'system_status.launch.py']
    environment = dict(os.environ, QT_QPA_PLATFORM='offscreen')
    process = subprocess.Popen(
        command, env=environment, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, start_new_session=True)
    try:
        time.sleep(1.5)
        assert process.poll() is None, process.communicate()[0]
        os.killpg(process.pid, signal.SIGINT)
        output, _ = process.communicate(timeout=3)
        assert process.returncode == 0, output
        assert 'Traceback' not in output, output
        assert output.count('process has finished cleanly') == 2, output
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate(timeout=3)
