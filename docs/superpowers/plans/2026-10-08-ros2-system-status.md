# ROS2 系统状态监控 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Ubuntu 22.04 + ROS2 Humble 上，通过两个 ROS2 包采集、发布并在 Qt 小窗口中实时显示八项系统状态，最终提交到 GitHub Public 仓库。

**Architecture:** `status_interfaces` 是独立的 ament_cmake 消息接口包；`status_publisher` 是 ament_python 功能包，包含采集发布节点、Qt 订阅显示节点和启动文件。显示节点只读取 ROS2 消息，发布节点不依赖图形会话，两者可独立运行。

**Tech Stack:** Ubuntu 22.04、ROS2 Humble、系统 Python 3.10、rclpy、psutil、platform、PyQt5、colcon、pytest。

**Spec:** 本文第 1—5 节保存用户需求及实现约定，与后续任务和验收表一起构成项目规格。

**文档状态：** 计划，未实现、未运行验收、未创建远端仓库。当前交付仅为此文档。下述命令都是实施或验收时执行的命令，不表示已经通过。

## Global Constraints

- 目标环境固定为 Ubuntu22.04 + ROS2 Humble；最终必须在这一组合上验收。
- 恰好两个 ROS2 包，名称为 `status_interfaces`、`status_publisher`。
- 自定义 `SystemStatus.msg` 必须包含八个指定字段，字段名称、顺序和类型保持题目示例。
- 必须显示记录时间、主机名、CPU 使用率、内存使用率、内存总大小、剩余内存、网络发送量和接收量。
- 必须有简单 Qt 小窗口，并以真实 ROS2 订阅消息更新界面。
- 最终交付 GitHub Public 仓库、可复现运行说明和验收证据。

## Review Focus

1. 发布端尚未启动或中断：窗口明确显示等待或数据过期，不能把旧值当成当前值；由 T4、A09 验证。
2. CPU 首次非阻塞采样无有效统计间隔：预热后再发布首个样本；由 T2、A05 验证。
3. 网络累计量与速率混淆、float32 精度受限：统一为累计 MiB，声明近似精度；由 T2、A06 验证。
4. GUI 事件循环阻塞或退出资源未释放：采用非阻塞 ROS 处理、限制每轮回调工作量，验证拖动与关闭；由 T4、A10 验证。
5. 采集失败、无网络计数器或非法发布周期：明确跳过失败样本、拒绝非法参数；由 T2、T3、A11 验证。

## 1. 需求边界与交付物

### 1.1 必须完成

| 编号 | 需求 | 对应交付物 |
|---|---|---|
| R01 | 自定义消息接口 | 接口包、八字段消息、可导入的生成接口 |
| R02 | 获取系统实时状态 | psutil 采集模块与 ROS2 发布节点 |
| R03 | 记录信息时间及主机名 | 采样时刻 `stamp`、`platform.node()` |
| R04 | Qt 实时展示 | 订阅节点、小窗口、单位、状态提示 |
| R05 | 正确构建和启动 | 包配置、入口点、launch、依赖说明 |
| R06 | GitHub 公开提交 | Public 仓库网址、提交记录、README、许可证 |
| R07 | 可核对质量 | 自动测试、目标环境验证、截图与验收报告 |

“记录信息的时间”解释为每条消息中的采样时间，不默认增加数据库或历史日志持久化功能。网络数据量解释为系统网络计数器报告的累计发送/接收量，不解释为每秒网速。若后续需要历史 CSV、网络速率、曲线或多主机选择，再另行扩展；本期不增加第三个包。

### 1.2 交付清单

- 两个包的完整源码及 Apache-2.0 LICENSE。
- README：环境要求、依赖安装、构建、分开启动、一键启动、消息单位、常见故障。
- 本计划文档与 `docs/acceptance-report.md`。
- `docs/images/system-status.png`：真实 Ubuntu Qt 窗口截图。
- 自动测试结果和关键 ROS2 命令输出摘要，记录对应 Git 提交 SHA。
- GitHub Public 仓库链接，支持未登录查看和匿名克隆。

## 2. 系统结构与文件职责

```text
psutil + platform
        │
        ▼
sys_status_pub（采样、组装 SystemStatus）
        │ /system_status
        ▼
sys_status_gui（ROS2 订阅、Qt 展示）
```

仓库根目录就是 colcon 工作空间根目录，预计结构如下：

```text
ros2-system-status/
├── README.md
├── LICENSE
├── .gitignore
├── docs/
│   ├── superpowers/plans/2026-10-08-ros2-system-status.md
│   ├── acceptance-report.md
│   └── images/system-status.png
└── src/
    ├── status_interfaces/
    │   ├── CMakeLists.txt
    │   ├── package.xml
    │   ├── LICENSE
    │   └── msg/SystemStatus.msg
    └── status_publisher/
        ├── package.xml
        ├── setup.py
        ├── setup.cfg
        ├── LICENSE
        ├── resource/status_publisher
        ├── launch/system_status.launch.py
        ├── status_publisher/
        │   ├── __init__.py
        │   ├── metrics.py
        │   ├── sys_status_pub.py
        │   ├── sys_status_gui.py
        │   └── status_window.py
        └── test/
            ├── test_copyright.py
            ├── test_flake8.py
            ├── test_pep257.py
            ├── test_metrics.py
            ├── test_publisher.py
            └── test_status_gui.py
```

`metrics.py` 负责采集与单位转换，不导入 Qt；`sys_status_pub.py` 管理 ROS2 发布；`sys_status_gui.py` 管理订阅和事件循环；`status_window.py` 管理布局、格式化和状态展示。接口生成代码由 colcon 生成，不手写或提交生成目录。

## 3. 消息和数据契约

### 3.1 消息定义

`src/status_interfaces/msg/SystemStatus.msg`：

```text
builtin_interfaces/Time stamp
string hostname
float32 cpu_percent
float32 memory_percent
float32 memory_total
float32 memory_available
float32 net_sent
float32 net_recv
```

实际文件添加单位说明注释，不增加字段。

| 字段 | 数据来源 | 约定单位或含义 | 显示格式 |
|---|---|---|---|
| stamp | 发布节点系统时钟 | 采样开始时的 Unix 时间，sec + nanosec；默认 use_sim_time=false | 本地日期时间，毫秒及 UTC 偏移 |
| hostname | platform.node() | 采集主机名称；空值替换为 unknown | 完整可复制文本 |
| cpu_percent | psutil.cpu_percent(interval=None) | 所有 CPU 的整体使用率，0—100 % | 一位小数与进度条 |
| memory_percent | psutil.virtual_memory().percent | psutil 报告的系统内存使用率，0—100 % | 一位小数与进度条 |
| memory_total | virtual_memory().total / 1024³ | GiB | 两位小数 + GiB |
| memory_available | virtual_memory().available / 1024³ | 可用内存 GiB，包含系统可回收的内存 | 两位小数 + GiB |
| net_sent | net_io_counters().bytes_sent / 1024² | 系统报告的累计发送量 MiB | 两位小数 + MiB |
| net_recv | net_io_counters().bytes_recv / 1024² | 系统报告的累计接收量 MiB | 两位小数 + MiB |

内存“剩余”使用 available 而非 free，界面标签写“剩余内存（可用）”。网络采用 `pernic=False` 的汇总值，可能包含回环与虚拟接口，不表示特定物理网卡或互联网流量。累计量基准由操作系统计数器决定，通常随启动累计；重启、接口变化或计数器重置可能改变基准，不能保证跨重启连续。

保留题目 float32 类型，因此内存和网络量是近似数。累计量越大，分辨率越低；验证按 float32 误差容限进行，不能要求逐字节精度。将来若有精确计费或长期统计需求，应另行改用整数 byte 字段，不在本期改动消息契约。

### 3.2 采集约定

- 启动时调用一次非阻塞 `cpu_percent(interval=None)` 预热，不发布该次结果；经过一个发布周期后开始发布。
- 同一轮只读取一次 virtual_memory 和一次 net_io_counters，避免字段来自不同轮采样。
- 任一采集调用失败或网络计数器返回 None：记录限频错误日志，跳过该轮，不伪造为 0；后续周期继续尝试。
- 对采集结果检查有限数值和范围；无效样本跳过。内存总量必须大于 0，可用量在 0 与总量之间。
- 不采用阻塞一秒的 CPU 采集方式；时间戳表示近似采样时刻，各指标并非原子快照。

psutil 官方文档说明首次非阻塞 CPU 结果应忽略，并定义了网络 byte 计数器：[psutil 文档](https://psutil.readthedocs.io/stable/index.html)。

## 4. ROS2 运行约定

| 项目 | 约定 |
|---|---|
| 发布节点名 | sys_status_pub |
| 订阅节点名 | sys_status_gui |
| 默认话题 | /system_status |
| 消息类型 | status_interfaces/msg/SystemStatus |
| QoS | 双端 KEEP_LAST、depth=10、RELIABLE、VOLATILE |
| 发布周期参数 | publish_period，double，默认 1.0 秒 |
| 周期有效范围 | 有限数且 0.1 ≤ publish_period ≤ 60.0 秒 |
| 参数修改 | 只在启动时设置；本期不支持运行时改周期 |
| GUI 过期参数 | stale_timeout，double，默认 3.0 秒，必须有限且 > 0 |
| 话题改变 | 通过标准 ROS2 remap；发布和订阅必须一致 |
| 入口点 | sys_status_pub、sys_status_gui |
| 一键启动 | system_status.launch.py，传递 publish_period、stale_timeout |

界面以本机 monotonic 时间计算消息接收后的年龄，避免系统时钟跳变导致错误过期。消息时间用于展示，不作为连接状态判断依据。使用慢发布周期时，README 提示将 stale_timeout 设置为大于两个发布周期。

接口包 CMake 查找 `ament_cmake`、`rosidl_default_generators`、`builtin_interfaces`，通过 `rosidl_generate_interfaces` 生成消息，声明 builtin_interfaces 依赖并导出 rosidl_default_runtime。package.xml 声明构建、运行依赖以及 `rosidl_interface_packages` 成员资格。此拆分符合 [ROS2 Humble 官方接口教程](https://github.com/ros2/ros2_documentation/blob/humble/source/Tutorials/Beginner-Client-Libraries/Custom-ROS2-Interfaces.rst)。

功能包声明 `ament_python`、`rclpy`、`status_interfaces`、`python3-psutil`、`python3-pyqt5`、`launch`、`launch_ros`；测试依赖包括 pytest 和 ament 的 lint 工具。setup.py 安装 ament 资源标记、package.xml、launch 文件并注册入口点；setup.cfg 将脚本安装到 `lib/status_publisher`。

## 5. Qt 窗口和交互

采用 PyQt5 原生控件，窗口初始约 560 × 420，允许缩放。使用布局管理器；长主机名可换行或水平查看，字体缩放不遮挡单位。

```text
系统实时状态
主机名             ubuntu-host
记录时间           2026-10-08 14:30:05.123 +08:00
CPU 使用率         18.2 %  [进度条]
内存使用率         42.5 %  [进度条]
内存总大小         15.50 GiB
剩余内存（可用）   8.91 GiB
累计发送量         120.34 MiB
累计接收量         567.89 MiB
状态：实时更新 / 等待数据 / 数据已过期
```

- 启动但无消息：数值显示“—”，状态显示“等待数据”。
- 收到消息：整体更新同一条消息的八个字段，状态显示“实时更新”。
- 超时：保留最后样本并明确标记“数据已过期”，显示距上次接收的秒数。
- 发布端恢复：首条新消息到达即恢复“实时更新”。
- 窗口只展示信息，不加入无关按钮、装饰动画、弹层或透明材质；状态同时使用文字，不能仅依赖颜色。
- 使用清晰标签、可访问名称和可复制文本，支持键盘操作和标准关闭窗口行为；默认静态刷新满足减少动态效果偏好。
- Qt 主线程运行 QApplication；QTimer 每 50 ms 调用一次非阻塞 `executor.spin_once(timeout_sec=0.0)`，每轮最多处理一个回调，回调只缓存最新消息；随后更新窗口。禁止在主线程使用阻塞 rclpy.spin 或 sleep。
- 用独立状态计时器检查过期；关闭窗口或 Ctrl+C 时停止计时器、关闭 executor、销毁节点并执行 rclpy.shutdown，重复清理必须安全。
- 无图形会话时发布节点仍可运行；GUI 启动文档说明需要本地桌面或可用图形转发，离屏自动测试不能替代真实桌面验收。

交互原则采用本地 apple-design 技能中的即时反馈、可预测性和可访问性；实际选择原生 Qt 控件，不照搬网页动画参数。

## 6. 实施任务

### Task 1: T1 建立工作空间与接口包

**文件：** 根目录 LICENSE、.gitignore，以及 `src/status_interfaces/` 下全部文件。

**输入：** 第 3 节消息契约。**输出：** 可导入的 `status_interfaces.msg.SystemStatus`。

- [ ] 建立仓库和 src 目录；忽略 build/、install/、log/、__pycache__/、pytest 缓存。
- [ ] 写八字段消息和 CMake/package.xml；填写真实维护者信息和一致许可证。
- [ ] `colcon build --packages-select status_interfaces` 构建成功。
- [ ] source 工作空间后运行 `ros2 interface show status_interfaces/msg/SystemStatus`，核对八个顶层字段。
- [ ] `/usr/bin/python3 -c "from status_interfaces.msg import SystemStatus; print(SystemStatus())"` 成功。
- [ ] 提交 `feat: add system status message interface`。

### Task 2: T2 采集模块与数据测试

**文件：** `metrics.py`、`test_metrics.py`，以及功能包基础配置。

**接口：** `SystemMetrics` 为具名不可变数据对象，包含 hostname 和六项数值（cpu_percent、memory_percent、memory_total、memory_available、net_sent、net_recv）；时间戳由发布节点生成。`MetricsCollector.warm_up() -> None`；`MetricsCollector.sample() -> SystemMetrics`；采集失败抛出 `MetricsCollectionError`。

- [ ] 用可注入或 mock 的 psutil/platform 写测试：8 GiB 总内存、3 GiB 可用内存、2 MiB 发送和 5 MiB 接收，转换结果分别为 8、3、2、5。
- [ ] 测试 CPU 预热调用一次且结果不被当成有效样本；测试主机名空值映射 unknown。
- [ ] 测试网络 None、采集异常、NaN/Inf、负计数和无效内存值均被识别为采集失败。
- [ ] 运行 `python3 -m pytest src/status_publisher/test/test_metrics.py -q`，确认新测试首先因未实现而失败。
- [ ] 实现采集接口和验证；重复上述命令直至通过。
- [ ] 提交 `feat: collect and normalize system metrics`。

### Task 3: T3 ROS2 发布节点

**文件：** `sys_status_pub.py`、`test_publisher.py`、setup.py、setup.cfg、package.xml、resource 标记。

**输入：** T1 消息、T2 采集接口。**输出：** `SysStatusPub(Node)`；`main(args=None)`；入口点 sys_status_pub；默认 /system_status 发布。

- [ ] 测试消息字段映射及时间戳：注入确定采样和固定节点时钟，所有字段对应一致。
- [ ] 测试 publish_period 边界 0.1、60.0 接受；0、负值、0.09、60.1、NaN/Inf 拒绝，启动返回非零并说明原因。
- [ ] 测试一次采集失败不发布，下一次有效样本正常发布；错误日志限频至最多每 5 秒一次。
- [ ] 在 source 后运行 `python3 -m pytest src/status_publisher/test/test_publisher.py -q`，先确认失败，再实现并通过。
- [ ] 实现启动预热、定时采集、时间戳、发布和安全退出，入口点可通过 ros2 run 调用。
- [ ] 用 `ros2 topic echo /system_status --once` 验证真实数据消息；用 `ros2 topic hz /system_status` 观察默认 1 Hz。
- [ ] 提交 `feat: publish system status over ROS2`。

### Task 4: T4 Qt 订阅窗口

**文件：** `status_window.py`、`sys_status_gui.py`、`test_status_gui.py`。

**输入：** SystemStatus 消息。**输出：** `StatusWindow.render_status(message: SystemStatus) -> None`；`StatusWindow.set_connection_state(state: str, age_seconds: float | None) -> None`；`SysStatusGui(Node)` 和 GUI `main(args=None)`；入口点 sys_status_gui。

- [ ] 使用 pytest + QApplication 离屏测试八项字段、单位、百分比格式和进度条取值；测试长主机名和零网络值。
- [ ] 使用可控 monotonic 时钟测试等待 → 实时 → 超时 → 恢复，默认超时严格大于 3.0 秒后转过期。
- [ ] 测试 stale_timeout 非正值及 NaN/Inf 被拒绝，数据未到达时不显示伪造的零值。
- [ ] `QT_QPA_PLATFORM=offscreen python3 -m pytest src/status_publisher/test/test_status_gui.py -q`，先确认新测试失败，再实现并通过。
- [ ] 集成非阻塞 Qt/ROS2 循环；测试重复关闭清理无异常。
- [ ] 真正启动桌面窗口，检查持续刷新时拖动、缩放、键盘关闭和 Ctrl+C 结束状态。
- [ ] 停止并重启发布节点，验证过期提示和自动恢复；保存实际截图。
- [ ] 提交 `feat: display ROS2 system status in Qt`。

### Task 5: T5 一键启动和可复现文档

**文件：** launch/system_status.launch.py、README.md、三个标准 lint 测试。

**输入：** 两个可独立启动的入口点。**输出：** 同时启动发布与显示的 launch；从干净环境可执行的 README。

- [ ] launch 声明 publish_period、stale_timeout 并按 double 类型传入；GUI 退出时结束其配套发布节点，避免隐藏后台进程。
- [ ] setup.py 安装 launch 文件；README 包含安装、构建、运行、单位和故障排查。
- [ ] README 说明 ROS_DOMAIN_ID 一致、两个终端都需 source、GUI 所需显示环境及 available 与 free 的区别。
- [ ] 加入 copyright、flake8、pep257 测试，修复实际格式和文档问题。
- [ ] 按第 7 节执行完整构建与测试，验证单独运行及一键运行。
- [ ] 提交 `docs: add launch workflow and usage instructions`。

### Task 6: T6 目标环境验收和 Public 仓库交付

**文件：** docs/acceptance-report.md、docs/images/system-status.png、完整仓库。

**输入：** 所有实现及测试。**输出：** 第 8 节通过记录、仓库链接和提交 SHA。

- [ ] 在 Ubuntu 22.04 + Humble 桌面执行全部验收，记录硬件、依赖版本、命令、结果和证据路径。
- [ ] 检查 Git 暂存内容，排除构建产物、凭据和无关文件。
- [ ] 使用实施时已登录的 GitHub 账号建立 `ros2-system-status` Public 仓库并推送 main；账号归属实施时核实，不能虚构仓库链接。
- [ ] 若尚未登录，使用正常交互授权；不在源码或文档保存访问 token。
- [ ] 验证 GitHub 显示 Public，未登录可浏览；在新的临时目录匿名克隆，按 README 重新构建并测试。
- [ ] 报告仓库正式网址、最终提交 SHA、自动测试结果、桌面截图及所有未通过项目；有未通过必选项不得声明完成。

## 7. 构建、启动与验证操作

以下以已安装 ROS2 Humble、已配置 rosdep 的 Ubuntu 22.04 为前提，工作空间为 `~/ros2-system-status`。首次系统 ROS 安装采用官方说明；不使用 Conda 替代 Humble 的系统 Python。

### 7.1 安装依赖与构建

```bash
sudo apt update
sudo apt install python3-colcon-common-extensions python3-rosdep python3-psutil python3-pyqt5 python3-pytest
source /opt/ros/humble/setup.bash
cd ~/ros2-system-status
rosdep update
rosdep install --from-paths src --ignore-src --rosdistro humble -r -y
colcon build --symlink-install --packages-select status_interfaces status_publisher
source install/setup.bash
ros2 interface show status_interfaces/msg/SystemStatus
ros2 pkg executables status_publisher
```

若 rosdep 尚未初始化，首次执行 `sudo rosdep init`；已初始化则跳过。优先使用 apt 的 psutil/PyQt5，避免 pip 与系统 ROS Python 混用。

### 7.2 分别启动

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

### 7.3 一键启动及调整周期

```bash
ros2 launch status_publisher system_status.launch.py
```

```bash
ros2 launch status_publisher system_status.launch.py publish_period:=0.5 stale_timeout:=3.0
```

### 7.4 话题与测试

在另外一个已经 source 的终端执行：

```bash
ros2 node list
ros2 topic info /system_status --verbose
ros2 topic echo /system_status --once
ros2 topic hz /system_status
QT_QPA_PLATFORM=offscreen colcon test --packages-select status_interfaces status_publisher --event-handlers console_direct+
colcon test-result --verbose
```

`topic hz` 持续观察至少 30 秒后手动 Ctrl+C；验收报告记录测量窗口和平均频率。离屏环境只用于自动测试，真实窗口另外在桌面验收。

## 8. 验收标准

所有 A01—A13 为必选项。以目标环境实际执行结果为准，不以代码存在、计划勾选或测试数量代替功能验收。

| 编号 | 验收项 | 操作与证据 | 通过标准 |
|---|---|---|---|
| A01 | 环境 | 记录 /etc/os-release、ROS_DISTRO、python3 --version | Ubuntu 22.04、Humble、系统 Python 3.10；具有可运行 Qt 的桌面会话 |
| A02 | 包数量与构建 | colcon list；从干净克隆执行构建 | 仅指定两个包，构建退出码 0，未缺依赖 |
| A03 | 消息接口 | interface show、Python 导入 | 八个顶层字段名称/顺序/类型完全匹配；Time 的嵌套字段不计入顶层字段数 |
| A04 | ROS2 通信 | node list、topic info、echo | 正确节点、消息类型、匹配 QoS；GUI 通过订阅收到数据 |
| A05 | CPU、内存、主机与时间 | mock 自动测试；目标机对照 platform/psutil | 固定输入映射正确；实际百分比在 0—100；total>0 且 available≤total；主机名一致；正常时钟下 stamp 与接收墙钟相差≤2秒 |
| A06 | 单位和网络量 | 固定 byte 输入转换、消息序列化往返；实际网络活动前后观察 | GiB/MiB 转换正确，值非负；无计数器重置时累计量不下降；受控流量后计数增长；float32 往返误差≤max(1e-6, abs(expected)×1e-6) |
| A07 | 更新频率 | 默认周期稳定后 topic hz 测量至少30秒 | 空闲验收机平均频率 0.9—1.1 Hz；0.5秒参数下平均 1.8—2.2 Hz |
| A08 | 八项 Qt 展示 | 截图；向 GUI 单独注入已知 SystemStatus 消息 | 所有字段完整，数值/单位/时间准确，同条消息整体刷新，零值不会显示成缺失 |
| A09 | 等待、过期、恢复 | GUI 先启动；启动/停止/重启发布端 | 初始等待；首次消息到达后实时；默认超过3秒未接收后在额外0.5秒内标记过期；重启后的首条消息使其恢复 |
| A10 | 窗口响应与退出 | 连续10分钟运行，反复拖动缩放；关闭和Ctrl+C | 无崩溃、无明显持续冻结、布局不遮挡；退出≤3秒，无未处理 traceback；分开启动只关闭GUI时发布端继续运行；一键启动关闭GUI时配套发布端结束 |
| A11 | 异常处理 | 自动注入采集异常/网络None；传入非法参数；慢周期测试 | 跳过坏样本且随后恢复；不发送假零值；非法参数非零退出且原因明确；日志限频；慢周期配合正确超时不误报 |
| A12 | 测试与文档 | colcon test-result；依README从干净克隆运行 | 所有测试通过、无失败/错误；必需测试不跳过；文档命令可复现，截图真实且对应提交 |
| A13 | GitHub Public | 未登录浏览、匿名克隆、提交记录 | 仓库明确Public，源码/README/许可证/报告齐全，最终代码已推送，仓库无凭据与构建产物 |

补充判定说明：真实 CPU 和 available 内存会随采样时间变化，不能把另一时刻的 top/free 数值当作逐项精确预期；精确计算通过固定输入测试核对，真实运行主要检查范围、趋势、更新和来源。网络活动以受控下载或本地已知流量实验观察，流量大小应足以超过当前 float32 分辨率；不要求累计发送/接收量等于下载文件体积。

### 8.1 验收报告模板

`docs/acceptance-report.md` 至少包含：

```text
验收日期：
执行人：
GitHub 仓库地址：
最终提交 SHA：
操作系统 / ROS2 / Python / psutil / PyQt5 版本：
CPU / 内存 / 图形会话：
构建命令、退出码及输出摘要：
测试命令、通过/失败/跳过数量：
话题类型及频率测量结果：
A01—A13：通过 / 未通过 / 未执行，逐项证据路径：
桌面截图路径：
10分钟运行、断连恢复和退出结果：
匿名克隆及重建结果：
遗留问题与限制：
```

## 9. 实施顺序与预估

| 阶段 | 任务 | 预计投入 | 完成门槛 |
|---|---|---|---|
| 消息与采集 | T1—T2 | 1.5—2.5小时 | 消息可导入，采集测试通过 |
| ROS2 发布 | T3 | 1—1.5小时 | 可观察真实消息及稳定频率 |
| Qt 展示 | T4 | 2—3小时 | 八字段、过期恢复、退出通过 |
| 集成与文档 | T5 | 1—1.5小时 | 一键启动与完整测试通过 |
| 验收与公开交付 | T6 | 1—2小时 | 目标机验证、公开克隆重建通过 |

总预计 6.5—10.5 小时，前提为目标环境和 GitHub 账号可用；ROS 安装、登录等待和环境修复另计。按 T1 → T2 → T3 → T4 → T5 → T6 顺序实施，任何必选验收项未通过都需修复或明确标为未完成。

## 10. 计划自检

- [x] 用户全部要求映射至 R01—R07、T1—T6 和 A01—A13。
- [x] 包数量、消息八字段、类型、单位、主题及入口点一致。
- [x] 发布和 Qt 展示位于同一功能包，未额外增加 ROS2 包。
- [x] 明确 CPU 首次采样、累计网络量、float32 精度和可用内存语义。
- [x] 覆盖等待、过期、恢复、采集异常、GUI 响应与退出。
- [x] 自动测试与真实 Ubuntu 桌面验收分别定义，未声称已验证。
- [x] GitHub Public 属于最终实施交付，当前计划阶段未创建或发布仓库。
