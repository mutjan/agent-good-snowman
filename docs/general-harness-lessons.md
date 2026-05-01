# 从游戏 Harness 迁移到 Coding Harness 的经验

这份笔记来自对 `A Good Snowman Is Hard To Build` 游戏 harness 的迭代。它不是解关卡策略，也不是要把游戏规则搬到 coding 任务里，而是总结一种更通用的 Agent 任务环境设计方法。

核心结论：harness 最有价值的部分不是替 agent 做决策，而是把“当前状态、可行动作、动作后果、失败原因、恢复路径”稳定地暴露出来。

## 1. 核心原则

好的 harness 应该给弱 agent 护栏，给强 agent 仪表盘。

弱 agent 常见问题是：

- 读错状态。
- 坐标或对象身份算错。
- 不知道某个动作没有产生实质变化。
- 被隐藏状态卡住后继续凭空推理。
- 犯错后没有局部恢复手段，只能越走越乱。

强 agent 常见需求不同：

- 需要更完整、更低噪声的事实。
- 需要能绕过建议，直接使用原始状态。
- 需要快速验证假设。
- 需要 checkpoint、diff、测试和日志，而不是强制流程。

因此 harness 应该分层输出：

| 层级 | 作用 | 对应游戏 harness | 对应 coding harness |
| --- | --- | --- | --- |
| Raw facts | 不带解释的事实 | 玩家坐标、雪球列表、格子内容 | git 状态、文件列表、依赖版本、测试结果 |
| Summary | 稳定摘要 | 当前关卡、对象类型、阻挡关系 | 改动范围、失败检查、模块边界 |
| Guidance | 可选提示 | 可推/不可推、是否进入 holding 状态 | 推荐下一步检查、可能相关测试 |
| Policy | 硬约束 | 不使用会卡死进程的探针 | 不覆盖用户改动、不跑破坏性命令 |

弱 agent 主要消费 `Summary` 和 `Guidance`，强 agent 主要消费 `Raw facts` 和 `Policy`，并把 `Guidance` 当作可参考信息。

## 2. 从游戏到 Coding 的映射

| 游戏 harness 经验 | Coding / 通用 harness 映射 |
| --- | --- |
| `read_state` 要给出实时状态，而不是依赖截图 | 提供 `repo_state`、`env_state`、`test_state`，避免 agent 靠记忆猜测 |
| 地图 overlay 要标出对象、墙、雪地、出口 | 模块地图要标出入口文件、生成文件、测试、配置、危险区 |
| 动作后要返回是否发生 material change | 每次 patch 后报告是否改变了目标文件、行为证据是否变化 |
| 推墙会进入 holding/pushing 状态 | coding 中也有隐藏状态，例如 dev server 未重启、缓存未清、测试进程卡住 |
| reset 和 undo 是一等能力 | 提供 checkpoint、仅回滚自己改动、重跑单项验证 |
| 坐标名不能混淆动作名 | 变量名要避免把事实字段和命令字段混在一起，例如 `reset_spawn` 比 `reset` 清楚 |
| 规则说明缺失会让 agent 自创规则 | API、架构边界、测试约定、生成文件规则要显式化 |
| 阻挡关系必须说明 | coding 中要说明不可编辑文件、依赖方向、权限、外部服务限制 |
| 探针会导致游戏无响应 | coding harness 也要标明高风险工具，例如慢测试、破坏性迁移、会污染状态的脚本 |

## 3. Coding Harness 应该暴露什么

一个 coding harness 不一定要复杂，但至少应该让 agent 快速回答这些问题：

- 我现在在哪个 repo、哪个分支、是否有用户未提交改动？
- 哪些文件是用户改过的，哪些文件是我刚改的？
- 这个任务最可能涉及哪些入口文件、测试文件和配置？
- 哪些文件是生成物、锁文件、快照文件、构建产物？
- 有哪些检查可以快速验证当前改动？
- 上一次检查失败的错误类型是什么：语法、类型、测试断言、环境、超时、依赖缺失？
- 我能否安全地撤销自己的最近一步？
- 如果状态变脏或服务卡住，推荐的恢复动作是什么？

这些信息可以通过脚本输出，而不是只写在长文档里。文档适合定义契约，脚本适合提供实时事实。

## 4. 推荐的工具形状

### `repo_state`

用于替代 agent 的“凭感觉扫 repo”。

示例输出：

```text
repo_state:
  cwd: /path/to/project
  branch: feature/foo
  dirty: true
  user_modified:
    - src/api/client.ts
  agent_modified:
    - src/ui/Form.tsx
  generated:
    - dist/
    - src/generated/
  risky_zones:
    - migrations/
    - package-lock.json
```

### `task_map`

用于给出和当前任务相关的局部地图。

示例输出：

```text
task_map:
  likely_entrypoints:
    - src/pages/settings.tsx
  likely_tests:
    - src/pages/settings.test.tsx
  nearby_contracts:
    - src/api/settings.ts
    - docs/settings-api.md
  ownership_notes:
    - src/generated/ is generated, edit schema instead
```

### `check`

用于提供分层验证，而不是只给一个全量测试命令。

示例输出：

```text
checks:
  fast:
    - npm run lint -- src/pages/settings.tsx
    - npm test -- settings.test.tsx
  medium:
    - npm run typecheck
  slow:
    - npm test
```

### `observe_after_action`

用于告诉 agent 动作后发生了什么。

示例输出：

```text
material_change: true
files_changed:
  - src/pages/settings.tsx
checks_changed:
  lint: pass
  focused_test: fail
failure_kind: assertion
hint: behavior changed, but empty input case still fails
```

如果没有实质变化，也应该明确输出：

```text
material_change: false
reason: patch only changed formatting in unrelated file
hint: inspect target function and add focused test before retrying
```

## 5. 规则说明要写到什么程度

规则说明的目标不是塞满背景知识，而是阻止 agent 在关键机制上“脑补”。

游戏里必须说清：

- 已堆好的雪人和墙一样不可移动。
- 撞到不可移动物体会进入 holding/pushing 状态。
- 进入 holding/pushing 状态后，需要再按一次方向键解除，才能正常转向。
- 第一关开局默认已有中雪球和小雪球堆叠，不要把它当成单独雪球。
- 出口连接关卡，没有需要规划的大地图。

迁移到 coding 后，类似地必须说清：

- 哪些目录不能直接编辑。
- 哪些文件是生成文件，应该改源头。
- 哪些测试是快反馈，哪些测试很慢或不稳定。
- dev server、数据库、缓存、编译产物是否需要重启或清理。
- 如何区分“用户已有改动”和“agent 本轮改动”。
- 如何撤销 agent 自己刚做的错误尝试。
- 失败时先读日志、读 diff、跑小测试，而不是直接大范围重写。

这类说明不需要很长，但要靠近工具输出和 `AGENTS.md`。弱 agent 未必会主动读长 README，短而稳定的契约更有效。

## 6. 弱 Agent 与强 Agent 的不同收益

弱 agent 从 harness 得到的最大收益是减少自由度：

- 少猜状态。
- 少猜规则。
- 少走不可逆路径。
- 更容易发现自己没有推动任务。
- 能通过脚本提示回到正确轨道。

强 agent 从 harness 得到的最大收益是降低摩擦：

- 更快拿到可靠事实。
- 更快做局部验证。
- 更少被环境细节打断。
- 更容易保持对用户改动的尊重。
- 更容易把探索过程变成可复用工具。

但是，对强 agent 过度规定流程可能有害。强 agent 需要的是透明仪表盘和轻量 checkpoint，不是把每一步都改造成固定菜单。

因此通用 harness 应该满足：

- Raw facts 永远可见。
- Guidance 可以跳过。
- Policy 简短明确。
- Recovery 足够便宜。
- 检查命令分层，不强迫每次全量验证。

## 7. 反模式

这些做法会让 harness 变成限制，而不是能力放大器：

- 只给建议，不给原始状态。
- 把启发式写成硬规则。
- 输出太长，关键事实被淹没。
- 工具名和字段名含混，例如 `reset` 同时表示重置动作和重生坐标。
- 只关注成功路径，不提供 undo、checkpoint、重试和失败分类。
- 把慢检查、危险命令、会污染状态的脚本包装成普通步骤。
- 要求 agent 按固定菜单操作，导致强 agent 无法直接验证自己的假设。
- 文档只描述目标，不描述环境中的隐藏状态和阻挡关系。

## 8. 一个可迁移的最小 Harness

对 coding 任务来说，一个最小但有用的 harness 可以包含：

```text
scripts/
  repo_state.py        # 当前分支、dirty 文件、用户改动、agent 改动
  task_map.py          # 根据关键词或文件路径输出相关入口、测试、配置
  check.py             # 分层运行 lint/type/test，并分类失败
  checkpoint.py        # 创建 checkpoint，只恢复 agent 自己的改动
  material_change.py   # 对比改动前后，报告是否真的推进任务
AGENTS.md             # 短契约：边界、恢复、验证、禁止事项
```

这组工具的目标不是让弱 agent 自动变强，而是让它少摔在环境细节上。对强 agent 来说，它应该像一个低摩擦的工作台：能快速读状态、快速验证、快速回滚，但不挡住更灵活的推理。

## 9. 实践总结

游戏 harness 的关键经验可以概括为四句话：

1. 先让状态可读，再谈策略。
2. 先让动作后果可观测，再谈自动规划。
3. 先让失败可恢复，再谈长程任务。
4. 先把隐藏规则写清楚，再判断 agent 能力。

迁移到 coding 环境时，也应该先问：这个 agent 是真的不会写代码，还是它缺少状态、边界、反馈和恢复工具？

当这些工具补齐后，弱 agent 会更像一个能完成局部任务的实习生，强 agent 会更像一个拥有好仪表盘的资深工程师。
