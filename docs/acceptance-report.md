# 验收报告

**状态：源码实现、构建、自动测试和 GitHub Public 交付已完成；真实桌面与跨进程 DDS 验收待完成。**

## 环境和版本

- 日期：2026-10-08。
- 操作系统：Ubuntu 22.04.5 LTS；ROS2 Humble。
- Python：系统 3.10.12；psutil 5.9.0；PyQt5 5.15.6；Qt 5.15.3。
- 项目目录：`/home/lisinom/ros2-system-status`。
- 开发分支：`feat/system-status`，按用户要求保留全部已有成果和提交。
- 核心最终源码提交：`9b77269`；文档和证据在后续提交保存。使用 `git log -1 --format=%H` 查看完整交付提交。
- 维护者：已连接的 GitHub 账号 `lisinom22-maker`。
- 公开仓库地址：https://github.com/lisinom22-maker/Real-time-status-information-of-the-detection-system

## 构建、测试和审查

执行前 source `/opt/ros/humble/setup.bash` 和本项目 `install/setup.bash`。

| 检查 | 实际结果 |
|---|---|
| colcon build --symlink-install | 两个包构建成功 |
| ros2 interface show | 八个顶层字段名称、顺序和类型符合规格 |
| Python 接口导入、消息序列化 | 成功 |
| 直接 pytest | 59 passed，2 项上游 flake8 依赖弃用警告 |
| colcon test-result --verbose | 59 tests，0 errors，0 failures，0 skipped |
| launch --show-args | publish_period / stale_timeout 正确暴露 |
| pkg executables | sys_status_pub / sys_status_gui 已注册 |
| 同进程实际 ROS2 + Qt | 真正订阅接收发布消息，过期及恢复通过 |
| 非法参数 CLI | publish_period=0 / stale_timeout=0 非零退出，无 traceback |
| 节点 Ctrl+C | 独立发布、GUI 退出正常 |
| launch 整组 Ctrl+C | 修复后两个子进程均正常结束，无 traceback，测试要求在 3 秒内结束 |
| rosdep check | 当前机器没有 rosdep 命令；已安装依赖支持直接构建 |
| 独立代码审查 | 两个 Important 问题已用 RED→GREEN 回归修复，见 code-review.md |

干净本地克隆位置：`/tmp/ros2-system-status-clean`，使用 `git clone --no-hardlinks`，未复用原工作空间 build/install。初次干净构建成功，47 项测试通过；更新最终源码后再次执行完整测试：59 tests，0 errors，0 failures，0 skipped。最终结果保存于 `docs/evidence/clean-test.log`。本地克隆不能代替 GitHub 匿名克隆。

## 十分钟持续运行结果

检查从 `86de32a` 的实现启动；后续退出和非法样本修复另以最终完整测试验证。详情见 [runtime-results.json](runtime-results.json)。

| 项目 | 实际值 |
|---|---|
| 运行时间 | 600.007 秒 |
| 接收消息数 | 1153 条 |
| 默认 1 Hz 测量 | 0.999733 Hz |
| 0.5 秒周期测量 | 2.000165 Hz |
| 过期提示及恢复 | 均成功 |
| 主检查循环最大间隔 | 0.019942 秒 |
| 资源清理耗时 | 0.002301 秒 |
| Qt 后端 | offscreen |

测试范围为真实 ROS2 同进程消息传递和真实 Qt 事件循环，不包含窗口管理器的拖动缩放体验。主循环最大间隔不等于完整 GUI 输入延迟，不能据此声称桌面响应体验已验证。

已查看 [离屏预览](images/offscreen-preview.png)，八字段、单位、进度条和状态均可见。它不是实际 Ubuntu 桌面截图。

## 环境限制与剩余验收

沙箱禁止 UDP socket 和网卡接口枚举，DDS 报告 Operation not permitted。同进程收发成功不能证明两个独立进程的 DDS 发现和通信。当前 DISPLAY=:1，但沙箱内 Qt 无法连接真实桌面；离屏自动测试不能替代桌面操作验收。当前网络采样计数为 0，未将其当成受控网络活动增长验证。

项目已上传至 GitHub Public 仓库。GitHub Actions 文件已提供，线上工作流结果需在 GitHub Actions 页面确认。

| 编号 | 当前状态 | 证据或待补内容 |
|---|---|---|
| A01 | 部分通过 | Ubuntu/Humble/Python 正确；真实图形会话待验收 |
| A02 | 本地通过，公开复现待补 | 干净本地克隆构建成功；GitHub 匿名克隆待完成 |
| A03 | 通过 | 自定义接口显示、导入、字段检查 |
| A04 | 部分通过 | 同进程 ROS2 消息收发通过；跨进程 CLI 验收待完成 |
| A05 | 部分通过 | 固定输入映射、真实采样通过；正常网络环境对照待补 |
| A06 | 部分通过 | 单位、范围、序列化通过；受控网络活动趋势待验证 |
| A07 | 部分通过 | 30 秒以上窗口测得 1 Hz/2 Hz 符合范围；CLI topic hz 待补 |
| A08 | 部分通过 | 八字段自动测试和离屏预览；桌面截图待补 |
| A09 | 部分通过 | 同进程消息和可控时间测试通过；独立发布进程重启待补 |
| A10 | 部分通过 | 十分钟运行、资源清理、CLI 和 launch 退出通过；桌面拖动缩放待补 |
| A11 | 部分通过 | 非法参数、采集异常、坏消息、限频与恢复通过；慢周期桌面运行待补 |
| A12 | 部分通过 | 完整自动测试通过，中文 README 和本地克隆复现；真实桌面截图待补 |
| A13 | 通过 | Public 仓库已创建并上传，可通过公开地址访问 |

## 执行中的决策

- 在新建独立仓库的开发分支实施，无需改动无效的 home/.git；若路径选择不合适，仅需迁移项目。
- 计划任务标题统一为 Task，便于 superpowers 提取任务；需求没有变化。
- 桌面和网络受限项明确标为待验收；可能仍有环境相关问题，不能声称全面通过。
- Public 仓库创建接口不可用，保留本地交付并等待仓库地址；代价是公开发布延后。
- 历史存储、网速和多主机维持本期范围；新增需求需后续开发。

## 继续开发时的保留规则

先执行 `git status --short`、`git log --oneline -10`，读取本报告和测试证据。保留全部已有提交及未提交成果，只处理明确问题，不重新搭建项目、不删除已有源码。

下一步：在正常 Ubuntu 桌面运行 README 的 launch 和两个独立节点，完成截图、话题频率、断连恢复及受控网络活动。
