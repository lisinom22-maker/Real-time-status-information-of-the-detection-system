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

"""Launch the status publisher and its Qt subscriber together."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, EmitEvent, RegisterEventHandler
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    """Pass typed periods and terminate the publisher when the GUI exits."""
    publisher = Node(
        package='status_publisher', executable='sys_status_pub', output='screen',
        parameters=[{'publish_period': ParameterValue(
            LaunchConfiguration('publish_period'), value_type=float)}],
    )
    gui = Node(
        package='status_publisher', executable='sys_status_gui', output='screen',
        parameters=[{'stale_timeout': ParameterValue(
            LaunchConfiguration('stale_timeout'), value_type=float)}],
    )
    return LaunchDescription([
        DeclareLaunchArgument('publish_period', default_value='1.0'),
        DeclareLaunchArgument('stale_timeout', default_value='3.0'),
        RegisterEventHandler(OnProcessExit(
            target_action=gui,
            on_exit=[EmitEvent(event=Shutdown(reason='Status window closed'))],
        )),
        publisher,
        gui,
    ])
