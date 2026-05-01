# Snowman Agent Contract

本项目用于测试 agent 自己解谜的能力，不提供现成路线、求解器或改存档捷径。

## 允许的公开工具

- `python3 scripts/snowman_read_state.py`：只读当前存档和静态关卡资源。
- `python3 scripts/snowman_read_state.py --json`：输出机器可读状态。
- `python3 scripts/snowman_read_state.py --compact --explain`：输出更短的状态摘要，并说明静态初始数据与实时实体的区别。
- `python3 scripts/snowman_send_keys.py '<moves>'`：向正在运行的游戏发送真实按键。
- `python3 scripts/snowman_send_keys.py '<moves>' --observe`：每次按键后读取状态并输出差异。
- `python3 scripts/snowman_send_keys.py 'undo' --observe` 或 `python3 scripts/snowman_send_keys.py 'z' --observe`：撤销一步。
- `python3 scripts/snowman_send_keys.py 'reset' --observe` 或 `python3 scripts/snowman_send_keys.py 'r' --observe`：重置当前关卡。
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
9. 用 `map_overlay` 判断墙、玩家、实时雪球和静态 marker；坐标是 `x,y`，`x` 向右增大，`y` 向下增大。
10. 完成当前关卡后查看 `level_exits`；`status=open` 的出口会给出 `stand=x,y` 和 `move=direction`，站到 `stand` 后按 `move` 离开。静态网格可能仍显示 `#`，不要据此否定开放出口。
11. `dead_state.status=likely_unwinnable` 表示从存档里的目标数量和雪球尺寸保守推断当前局面很可能无解；这不是求解器，也不是直接读取 UI 气泡。
12. `map_overlay` 的覆盖优先级是玩家 > 开放出口 `E` > 实时物体 > 静态 marker；如果实时物体或玩家压在 marker 格上，查看 `static_marker_overlaps`，不要推断 marker 已经消失。
13. `reset_spawn=x,y` 是重置后的出生坐标，不是走上去会触发重置的地板；重置必须按 `reset`/`r`。

## 行动要求

- 当前关卡未完成时，不要在只读取一次状态后结束；必须继续发送一小批候选按键，或说明明确阻塞。
- 学习机制时优先用短批次：1 到 5 个按键加 `--observe`。
- 推雪球或动画后如果出现 `no saved state change`，先尝试更长的 `--observe-timeout`，再判断动作无效。
- 如果只出现 `no material state change`，说明存档时间变了但玩家、实时物体、雪人和完成状态都没变；不要当成成功移动。
- 与墙或已完成雪人交互后如果出现 `no saved state change`，把它当作可能的临时推/抱姿态；下一键可能要用来释放姿态。
- 当前关卡完成后，优先按 `level_exits` 的开放出口离开，不要把静态顶/底/侧边的 `#` 当成仍然封闭。比如 `open up at 3,0 stand=3,1` 表示站到 `3,1` 后按 `up`。
- 如果 `dead_state.status=likely_unwinnable`，优先 `undo`/`z` 回退刚才一步；如果已经多步不可恢复，再用 `reset`/`r` 重开当前关卡。
- 推物体时必须站在物体反方向的相邻格，例如向右推要站在物体左侧。
- 推动前同时检查目标格和目标后方一格；墙、地图边缘、不可兼容物体、没有站位都会阻挡。
- 较小雪球推向较大雪球可能堆叠；同尺寸或较大推向较小通常不会完成堆叠，可能阻挡或继续推动。
- 推动堆叠体时可能只把顶部雪球推出去，下方雪球和玩家都不移动；用 `--observe` 的 diff 判断实际发生了什么。
- 发现刚才一步把球推入角落或造成明显死局时，优先立刻用 `undo`/`z`；多步后难以恢复时再用 `reset`/`r`。
- 解释静态初始物体时优先使用 `marker`、`label`、`stack_bottom_to_top`，不要把 marker 直接说成 size。
- 可以写本地临时分析脚本辅助自己推理，但不要把求解器、路线库或答案固化进仓库。

## 回答用户

- 使用用户的语言。
- 简洁说明读到的状态、发送的按键和验证结果。
- 如果需要更多能力，优先在本地临时实验，不把答案或旁路固化进这个仓库。
