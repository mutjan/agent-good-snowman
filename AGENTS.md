# Snowman Agent Contract

本项目用于测试 agent 自己解谜的能力，不提供现成路线、求解器或改存档捷径。

## 允许的公开工具

- `python3 scripts/snowman_read_state.py`：只读当前存档和静态关卡资源。
- `python3 scripts/snowman_read_state.py --json`：输出机器可读状态。
- `python3 scripts/snowman_read_state.py --compact --explain`：输出更短的状态摘要，并说明静态初始数据与实时实体的区别。
- `python3 scripts/snowman_send_keys.py '<moves>'`：向正在运行的游戏发送真实按键。
- `python3 scripts/snowman_send_keys.py '<moves>' --observe`：每次按键后读取状态并输出差异。
- `python3 scripts/snowman_config.py`：检查本机配置和资源路径。

## 硬边界

- 不使用 LLDB、`ptrace`、调试器 attach、指针探针、内存扫描或会冻结游戏的进程探测。
- 不向项目加入求解器、答案路线、自动导航、回放验证器、teleport、存档 patch 工具。
- 不把本机配置、存档、备份、pycache 或编译产物提交出去。
- 读取状态只能来自公开文件：`progress.json`、`levels.txt`、`layout.txt`。
- 行动必须通过真实按键进入游戏。

## 推荐循环

1. 读取状态：`python3 scripts/snowman_read_state.py --compact --explain`。
2. agent 自行推理下一批动作。
3. 发送动作：`python3 scripts/snowman_send_keys.py 'up,left,right' --observe`。
4. 再次读取状态，核对结果。
5. 撞墙、抱堆好的雪人或接触其他不可移动物体后，角色可能进入临时推/抱状态；下一次方向键可能只是解除该状态，不一定移动。
6. `current_objects` 只列出存档里的实时实体；`static_initial_balls` 在未触碰前仍可能实际存在。
7. 关卡资源里的数字是静态 marker，不是雪球尺寸；第 0 关 Lucy 的 `3` 表示中雪球在下、小雪球在上的初始堆叠。
8. 推开这种堆叠后，看到实时 `small` 和 `small_on_medium...` 的 grass view 是堆叠转场，不是中雪球变小。

## 行动要求

- 当前关卡未完成时，不要在只读取一次状态后结束；必须继续发送一小批候选按键，或说明明确阻塞。
- 学习机制时优先用短批次：1 到 5 个按键加 `--observe`。
- 推雪球或动画后如果出现 `no saved state change`，先尝试更长的 `--observe-timeout`，再判断动作无效。
- 与墙或已完成雪人交互后如果出现 `no saved state change`，把它当作可能的临时推/抱姿态；下一键可能要用来释放姿态。
- 解释静态初始物体时优先使用 `marker`、`label`、`stack_bottom_to_top`，不要把 marker 直接说成 size。
- 可以写本地临时分析脚本辅助自己推理，但不要把求解器、路线库或答案固化进仓库。

## 回答用户

- 使用用户的语言。
- 简洁说明读到的状态、发送的按键和验证结果。
- 如果需要更多能力，优先在本地临时实验，不把答案或旁路固化进这个仓库。
