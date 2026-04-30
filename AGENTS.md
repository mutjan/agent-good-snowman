# Snowman Agent Contract

本项目用于测试 agent 自己解谜的能力，不提供现成路线、求解器或改存档捷径。

## 允许的公开工具

- `python3 scripts/snowman_read_state.py`：只读当前存档和静态关卡资源。
- `python3 scripts/snowman_read_state.py --json`：输出机器可读状态。
- `python3 scripts/snowman_send_keys.py '<moves>'`：向正在运行的游戏发送真实按键。
- `python3 scripts/snowman_config.py`：检查本机配置和资源路径。

## 硬边界

- 不使用 LLDB、`ptrace`、调试器 attach、指针探针、内存扫描或会冻结游戏的进程探测。
- 不向项目加入求解器、答案路线、自动导航、回放验证器、teleport、存档 patch 工具。
- 不把本机配置、存档、备份、pycache 或编译产物提交出去。
- 读取状态只能来自公开文件：`progress.json`、`levels.txt`、`layout.txt`。
- 行动必须通过真实按键进入游戏。

## 推荐循环

1. 读取状态：`python3 scripts/snowman_read_state.py --json`。
2. agent 自行推理下一批动作。
3. 发送动作：`python3 scripts/snowman_send_keys.py 'up,left,right'`。
4. 再次读取状态，核对结果。
5. 如果推墙后卡在推的状态，下一次方向键可能只是解除该状态；用状态变化确认后继续。

## 回答用户

- 使用用户的语言。
- 简洁说明读到的状态、发送的按键和验证结果。
- 如果需要更多能力，优先在本地临时实验，不把答案或旁路固化进这个仓库。
