# ROS2 系统实时状态监控

适用于 **Ubuntu 22.04 + ROS2 Humble + 系统 Python 3.10**。两个 ROS2 包完成系统采集、消息发布和 Qt 小窗口显示。

- `status_interfaces`：ament_cmake 自定义消息接口包。
- `status_publisher`：ament_python 功能包，包含发布节点、Qt 订阅节点及一键启动文件。

```text
psutil / platform → sys_status_pub → /system_status → sys_status_gui → Qt 窗口
```

## 安装依赖

先按 [ROS2 Humble 官方安装说明](https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debians.html)安装 ROS2。使用系统 `/usr/bin/python3`，不要混用 Conda 的 Python。

```bash
sudo apt update
sudo apt install python3-colcon-common-extensions python3-rosdep \
  python3-psutil python3-pyqt5 python3-pytest
source /opt/ros/humble/setup.bash
```

若 rosdep 从未初始化，执行一次 `sudo rosdep init`；已初始化则跳过。

## 构建

仓库根目录即 colcon 工作空间根目录。下载或克隆后进入项目目录：

```bash
cd ~/ros2-system-status
source /opt/ros/humble/setup.bash
rosdep update
rosdep install --from-paths src --ignore-src --rosdistro humble -r -y
colcon build --symlink-install --packages-select status_interfaces status_publisher
source install/setup.bash
```

## 一键运行

在 Ubuntu 桌面终端运行：

```bash
source /opt/ros/humble/setup.bash
cd ~/ros2-system-status
source install/setup.bash
ros2 launch status_publisher system_status.launch.py
```

窗口显示八项系统信息，CPU 和内存使用率带进度条。关闭窗口会结束本次 launch 的发布节点；Ctrl+C 也会结束两者。

调整发布周期：

```bash
ros2 launch status_publisher system_status.launch.py \
  publish_period:=0.5 stale_timeout:=3.0
```

`publish_period` 为 double，允许 0.1～60.0 秒，默认 1.0 秒。`stale_timeout` 为正 double，默认 3.0 秒。两者仅支持启动时配置。较慢的发布周期应配合大于两个发布周期的过期时间，例如周期 5 秒、过期时间 12 秒。

## 分开运行

两个终端均需 source ROS2 和本项目工作空间，并保持 `ROS_DOMAIN_ID` 一致。

终端 A：

```bash
source /opt/ros/humble/setup.bash
cd ~/ros2-system-status
source install/setup.bash
ros2 run status_publisher sys_status_pub
```

终端 B：

```bash
source /opt/ros/humble/setup.bash
cd ~/ros2-system-status
source install/setup.bash
ros2 run status_publisher sys_status_gui
```

分开运行时，关闭窗口不会停止独立的发布节点。发布节点不需要图形界面。

修改话题时，双方使用相同 remap：

```bash
ros2 run status_publisher sys_status_pub --ros-args -r /system_status:=/host_status
```

```bash
ros2 run status_publisher sys_status_gui --ros-args -r /system_status:=/host_status
```

## 消息与单位

消息类型为 `status_interfaces/msg/SystemStatus`，包含八个顶层字段：

| 字段 | 类型 | 单位和含义 |
|---|---|---|
| stamp | builtin_interfaces/Time | 采样开始时的系统时间，sec + nanosec |
| hostname | string | platform.node() 返回的主机名 |
| cpu_percent | float32 | 整体 CPU 使用率，0～100 % |
| memory_percent | float32 | psutil 报告的内存使用率，0～100 % |
| memory_total | float32 | 内存总大小，GiB |
| memory_available | float32 | 可用内存，GiB |
| net_sent | float32 | 系统累计发送量，MiB |
| net_recv | float32 | 系统累计接收量，MiB |

- GiB = bytes / 1024³；MiB = bytes / 1024²。
- 剩余内存使用 `available`，包括可回收内存，不等同于 `free`。
- 网络量是系统计数器累计值，不是 MiB/s；汇总接口可能包含回环和虚拟网卡。
- 系统重启、接口变化或计数器重置可能改变累计基准，不保证跨重启连续。
- 按题目保留 float32，数值是近似量，大累计值不能保证逐字节精度。
- CPU 首次非阻塞读数被丢弃，正常启动约一个发布周期后发送首条消息。
- 发布端使用真实系统时钟，不支持 `use_sim_time:=true`，避免暂停的仿真时钟使主机监控失效。
- 数据采集失败时跳过该轮并限频记录错误，后续自动重试，不发布伪造的零值。
- GUI 丢弃 NaN/Inf 或越界的订阅样本，不重置最后有效样本的年龄；正常消息随后到达可恢复。

窗口时间显示本地时区、毫秒和 UTC 偏移。首次消息前显示“等待数据”；过期后保留最后样本并标注“数据已过期”；新消息到达自动恢复。过期判断使用本机 monotonic 接收时间，不受墙钟校时影响。

## 检查与测试

```bash
ros2 interface show status_interfaces/msg/SystemStatus
ros2 pkg executables status_publisher
ros2 node list
ros2 topic info /system_status --verbose
ros2 topic echo /system_status --once
ros2 topic hz /system_status
```

保持发布节点运行，使用 `topic hz` 观察至少 30 秒，再按 Ctrl+C 结束测量。

运行测试：

```bash
QT_QPA_PLATFORM=offscreen colcon test \
  --packages-select status_interfaces status_publisher \
  --event-handlers console_direct+
colcon test-result --verbose
```

直接运行 pytest：

```bash
QT_QPA_PLATFORM=offscreen /usr/bin/python3 -m pytest src/status_publisher/test -q
```

测试覆盖单位转换、边界参数、时间戳与字段映射、错误恢复、消息序列化、Qt 格式、过期恢复、事件循环清理、真实同进程 ROS 消息传递以及版权/flake8/pep257。

持续运行检查（约 10 分钟）：

```bash
QT_QPA_PLATFORM=offscreen /usr/bin/python3 tools/verify_runtime.py --seconds 600
```

这会保存 `docs/runtime-results.json` 和 `docs/images/offscreen-preview.png`，检查约 1 Hz/2 Hz 更新及过期恢复。离屏检查不等于真实桌面操作或跨进程 DDS 验收；真实桌面需额外检查拖动、缩放、关闭及独立进程收发。

## 常见问题

| 现象 | 处理 |
|---|---|
| 找不到包或自定义消息 | 先构建，再在每个终端 source install/setup.bash |
| GUI 一直等待 | 确认发布节点运行、双方 ROS_DOMAIN_ID 和 remap 一致、QoS 可兼容 |
| 周期较长时提示过期 | 增大 stale_timeout 至大于两个发布周期 |
| Qt 无法连接显示 | 在 Ubuntu 桌面终端启动；检查 DISPLAY/WAYLAND_DISPLAY，SSH 需要可用的图形转发 |
| DDS socket/网络权限错误 | 当前运行环境限制 ROS2 网络通信；到允许本地 DDS 通信的环境验收 |
| symlink 构建目录冲突 | 切换构建方式后，只清理本项目 build/、install/、log/ 生成目录并重新构建 |
| CPU 与 top 不完全相同 | 两者采样间隔不同；本项目显示整体 CPU 使用率 |
| 内存与 free 数字不同 | 核对 available 字段与 GiB 换算，不要对比 free 或十进制 GB |

## 参考与实现说明

实现参考了以下官方资料的节点组织、接口生成和事件循环方式，业务采集、显示和测试为本项目编写：

- [ROS2 Humble 官方 Python 发布节点示例](https://github.com/ros2/examples/blob/humble/rclpy/topics/minimal_publisher/examples_rclpy_minimal_publisher/publisher_member_function.py)
- [ROS2 Humble 自定义消息接口教程源码](https://github.com/ros2/ros2_documentation/blob/humble/source/Tutorials/Beginner-Client-Libraries/Custom-ROS2-Interfaces.rst)
- [psutil 官方文档](https://psutil.readthedocs.io/stable/index.html)
- [Qt 5 QTimer 官方文档](https://doc.qt.io/archives/qt-5.15/qtimer.html)

详细实施计划见 [计划文档](docs/superpowers/plans/2026-10-08-ros2-system-status.md)，实际验证状态见 [验收报告](docs/acceptance-report.md)。

许可证：Apache-2.0，见 [LICENSE](LICENSE)。
