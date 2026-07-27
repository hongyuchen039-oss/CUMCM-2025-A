---
name: project-mainline-governance
description: Keep AI-assisted engineering and mathematical-modeling projects on the main delivery path. Prevent premature phase starts, unnecessary CI, role proliferation, design-review loops, fake progress, unsupported PASS claims, and cross-worktree contamination. Use at every new project start and every phase transition.
---

# 项目主线治理 Skill

## 1. 根本目标

本 Skill 的目标不是建设一套漂亮的 DevOps、审批或多 Agent 体系，而是让项目尽快形成最终可交付成果。

对数学建模项目，主成果通常是：

```text
可信模型
→ 可复现实验
→ Q1～Qn 数值结果
→ 官方格式结果文件
→ 图表
→ 论文
```

任何流程、CI、Agent、报告、分支和审核，只有在能提高这些成果的正确性或交付速度时才值得存在。

核心原则：

> 一个活跃阶段、一个当前任务、一个主施工者、一个审核对象。

> 少开角色，少开支路，少做无产出的治理；优先产生代码、数据、结果文件和论文。

---

## 2. 每个新项目启动时必须执行

### 2.1 先定义最终交付

写出一句话：

> 项目完成的标准是：__________ 已生成、可复现、可独立验收。

不得把“CI 全绿”“PR 很整洁”“Agent 很多”当作项目最终目标。

### 2.2 只规划 3～7 个粗阶段

例如：

```text
事实核验
→ 模型基础
→ 优化求解
→ 多主体扩展
→ 结果文件
→ 论文
```

路线图中存在某个阶段，不代表该阶段已经获准启动。

### 2.3 永远只激活一个当前任务

当前任务必须明确：

- 目的；
- 允许修改文件；
- 禁止修改文件；
- 验收证据；
- 停止条件；
- 下一阶段进入条件。

当前阶段未关闭时，不得提前启动下游施工角色。

### 2.4 先验证施工能力，再发施工 Prompt

必须真实验证当前施工会话具备：

- Bash / PowerShell / Terminal；
- Write / Edit / Delete；
- 仓库读写；
- 测试执行；
- 必要时 commit / push。

若会话只有只读能力：

- 只能承担研究、审查、监督；
- 不得提交“实现完成”报告；
- 不得使用占位 SHA、占位 benchmark 或未运行测试的 PASS。

---

## 3. Agent / CC 最小化原则

### 3.1 默认角色只有两个

- **MAIN**：总览主线、冻结当前任务、作最终决策；
- **BUILD CC**：当前任务唯一写入者。

### 3.2 按需启用两个只读角色

- **只读监管 / Audit CC**：在真实 artifact 出现后审 P0/P1；
- **Hermes**：只核验 branch、SHA、changed files、push、PR、GitHub 状态。

Audit 与 Hermes 默认只读，不得成为第二施工者。

### 3.3 非必要不得新开 CC

创建新 CC 前必须同时满足：

1. 它拥有与现有角色不同的明确 artifact；
2. 现有角色无法合理完成；
3. 新角色具备完成任务所需工具；
4. 它降低的风险大于新增沟通成本；
5. 有明确停止条件；
6. 用户或 MAIN 明确批准。

以下理由不足以新建 CC：

- “以后可能用到”；
- “这个阶段名字不同”；
- “想让多个 Agent 看起来并行”；
- “可以提前设计”；
- “Audit 可能还能再发现问题”。

优先复用现有 MAIN、BUILD、只读监管和 Hermes。

### 3.4 禁止把阶段错误拆成角色群

不得因为存在 Search、论文、可视化等阶段，就自动创建：

```text
Search CC
Search MAIN
Search Audit
Search Hermes
```

阶段只有在进入 Gate 满足后才激活；激活后仍优先由现有 BUILD CC 施工。

---

## 4. CI 降级原则：默认非必要不用 CI

### 4.1 CI 的默认地位

对以最终建模产出为目的的项目：

```text
CI_REQUIRED = NO
```

除非有明确理由，否则不创建、不扩建、不把 CI 作为阶段硬门槛。

CI 只是自动报警器，不是数学正确性的主要证据，也不是项目成果。

### 4.2 数学建模项目的首选替代方案

默认采用：

```text
本地真实验证
+ 只读监管 CC 独立复核
+ Hermes 核验 Git / GitHub 状态
+ 关键里程碑全量回归
```

其中：

- BUILD CC 运行真实测试、收敛、benchmark、结果生成；
- Audit CC 只读检查代码、测试输出、数学合同和结果；
- Hermes 检查 SHA、分支、changed files、push、PR；
- MAIN 决定是否接受和进入下一阶段。

### 4.3 只有以下情况才考虑 CI

至少满足一项，并写明理由：

- 多人频繁向同一主分支合并；
- 项目需要部署、发布或长期维护；
- 轻量测试可在约 5 分钟内完成；
- 回归错误很容易由普通提交引入；
- 分支保护或外部平台明确要求；
- 用户明确要求 CI；
- 结果文件自动生成具有高误写风险，且 CI 能有效阻止。

### 4.4 使用 CI 时必须保持轻量

建模项目 CI 默认只做：

- `py_compile` / import；
- 快速单元测试；
- 一个真实 smoke；
- 明显文件边界检查。

昂贵内容默认放在本地里程碑验收：

- 全量数值回归；
- 空间收敛；
- 时间收敛；
- 真实 profile benchmark；
- 正式优化搜索；
- Excel 生成与回读；
- 论文数值一致性。

不得为了 CI：

- 删除真实测试；
- 放宽数学断言；
- 把所有真实验证改成 mock；
- 长期调试 workflow 而不推进模型；
- 将 timeout 等同于数学失败。

### 4.5 CI timeout 的处理

若满足：

- 本地全量测试真实通过；
- 无 assertion failure；
- 模型与结果可复现；
- 只读监管复核通过；
- Hermes 已核验 commit / push / PR；

则单纯 CI timeout、cancelled 或运行速度问题原则上属于 P2/P3，不得自动阻断建模主线。

只有当 timeout 隐藏真实失败、无法确认测试完整性、或项目有部署/多人协作硬要求时，才升级为 P1。

### 4.6 CI 投入上限

除非用户明确要求，CI 及 workflow 治理不应占用超过项目工程时间的约 5%～10%。

一旦 CI 调试开始超过模型、结果或论文推进成本，MAIN 必须降级或取消 CI。

---

## 5. 设计与审核不得形成版本循环

失败模式：

```text
V1 → V2 → V3 → V4 → V5 → V5.1 → V5.2
```

每个版本只修表格、命名、字段或排版，却没有代码和测试。

默认最多允许：

1. 一次设计；
2. 一次 P0/P1 定向修订；
3. 进入实现与测试；
4. 一次代码审核；
5. 一次 P0/P1 修复。

设计已经可执行后，剩余细节应：

```text
ACCEPT WITH BINDING IMPLEMENTATION AMENDMENTS
```

然后由代码和测试证明。

以下问题不得单独开启新 Gate：

- Markdown 表格形式；
- 章节顺序；
- 标签名称；
- 可以由 schema / fixture / unit test 冻结的细节；
- 普通 P2 可读性问题。

---

## 6. 只审核真实产物

Audit 只在以下 artifact 存在后启动：

- 真实设计合同；
- 代码 diff；
- commit；
- 测试输出；
- benchmark 原始数据；
- 正式结果文件；
- 论文草稿。

没有真实 artifact 时，不得持续开启 Audit 审核假实施。

Audit 只阻断：

- P0：数学、数据、安全或结果根本错误；
- P1：会让当前正式交付错误或不可复现的问题。

P2 默认记录后继续，不得无限扩大审核范围。

---

## 7. 证据优先，禁止假进度

必须区分：

- `AGENT SELF-REPORTED`：Agent 自报；
- `LOCAL OBSERVED`：本地命令真实看到；
- `REMOTE OBSERVED`：远程分支可见；
- `GITHUB VERIFIED`：GitHub API / PR / CI 直接核验。

不得接受：

- 无 changed files 的“已实现”；
- 无真实 SHA 的“已 commit”；
- 无 remote SHA 的“已 push”；
- 无命令输出的“PASS”；
- 无原始时间数据的“benchmark 完成”；
- cancelled / timeout / old SHA 的“CI 通过”；
- PR 描述代替测试证据；
- 占位 fixture、占位 SHA、占位结果。

状态词必须严格使用：

- `PLANNED`；
- `IMPLEMENTED LOCALLY`；
- `TESTED LOCALLY`；
- `COMMITTED`；
- `PUSHED`；
- `GITHUB VERIFIED`；
- `REVIEWED`；
- `ACCEPTED`；
- `MERGED`；
- `FINAL`。

不得用一个模糊的“完成”覆盖全部阶段。

---

## 8. 阶段进入与退出 Gate

### 8.1 进入下一阶段前

必须满足：

- 上一阶段核心 artifact 已存在；
- 阻断性 P0/P1 已关闭或由用户明确接受；
- 必要的本地验证已完成；
- 施工会话具备工具；
- MAIN 明确授权；
- 若项目明确要求 CI，则所需 CI 已通过；
- 若项目不要求 CI，不得临时把 CI 变成硬门槛。

### 8.2 当前阶段结束前

必须有：

- 授权范围内的文件；
- 真实测试 / 验证输出；
- commit SHA；
- push 证据；
- Hermes 对分支与 changed files 的核验；
- 只读监管对 P0/P1 的结论；
- MAIN 的接受决定；
- 明确停止，不自动进入下一任务。

---

## 9. 主线健康检查

任何时候觉得“很忙但没进展”，立即回答：

1. 当前唯一任务是什么？
2. 上一轮之后，哪个真实 artifact 发生了变化？
3. 当前唯一施工者是否真的能写文件和运行命令？
4. 我们是在审核代码/结果，还是审核又一份计划？
5. 是否提前启动了下游阶段？
6. 是否把 CI、格式或 P2 变成了阻断？
7. 是否存在多个 CC 重复同一判断？
8. 是否可以改用现有只读监管和 Hermes，而不是新建 CC？
9. GitHub 状态是否对应当前 SHA？
10. 下一步最近的“可产生不可伪造证据”的动作是什么？

若第 2 或第 10 项为空：

```text
停止治理扩张
冻结次要角色
回到当前主线施工
```

---

## 10. 必须立即纠偏的红旗

- 连续两轮以上纯设计返工；
- 施工 CC 没有 Bash / Write / Edit；
- 新 CC 没有独立 artifact；
- Foundation 未关闭却启动 Search / 论文 / 下游施工；
- placeholder SHA / benchmark / fixture；
- 未运行测试却写 PASS；
- Audit 审核不存在的 commit；
- 格式问题开启新 Gate；
- 两个写入者操作同一 worktree；
- CI timeout 被直接描述为数学失败；
- workflow 调试时间超过模型推进；
- 状态报告数量增长快于代码、结果和论文。

纠偏动作固定为：

1. 暂停所有非当前任务角色；
2. 只保留 MAIN、一个 BUILD CC；
3. 按需启用只读监管和 Hermes；
4. 明确最近的证据产出动作；
5. 发一个施工 Prompt；
6. 只审核施工产物。

---

## 11. 本项目已经犯过的典型错误

本 Skill 特别防止以下历史重演：

1. Foundation PR 尚未合并，就提前激活 Search；
2. 把 Search 阶段拆成 Search CC、Search MAIN、Search Audit、Hermes 多条支路；
3. 未先检查施工会话是否具备 Bash / Write / Edit；
4. 没有代码，却连续审核 V3、V4、V5、V5.1、V5.2；
5. 把表格形式、字段命名和实现细节拆成独立 Gate；
6. 用报告版本数替代真实仓库进展；
7. 出现占位 commit、未生成 fixture、未跑测试却写 PASS；
8. 将 CI timeout 提升成比模型和结果更重要的硬阻断；
9. 让治理角色和报告数量超过工程与建模产出；
10. 最终不得不退回 Foundation 主线重新收口。

永久修正：

- 路线图存在不等于阶段已授权；
- 下游角色只在进入 Gate 后激活；
- CI 默认非必要；
- 施工能力先验证；
- 一次设计修订后转代码与测试；
- 只读监管和 Hermes 优先于新建 CC；
- MAIN 必须主动结束不再产生价值的支路。

---

## 12. 最终操作口令

永远优先：

```text
一个任务
→ 一个施工者
→ 一个真实 artifact
→ 一次真实验证
→ 一次只读审核
→ 一次 MAIN 决策
```

避免：

```text
多个 CC
→ 多个报告
→ 多个 Gate
→ 大量 CI 治理
→ 没有模型、结果和论文
```

当流程与最终建模产出发生冲突时，在不牺牲数学正确性、可复现性和安全底线的前提下，优先最终建模产出。
