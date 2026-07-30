# 项目驾驶舱

## 最终目标
完成 2025 CUMCM A 题 Q1–Q5 的可信建模、数值策略、result1/2/3.xlsx 与论文。

## 当前问题
Q2 单架 FY1 投放一枚烟幕弹的最优策略（已冻结为 canonical budget-limited best-known, 已合并入 main）。

## 当前阶段
TASK_GOV_003 — BOUNDED VERIFICATION SKILL v0.1 — DOC-ONLY PUSH READY。

- PR #11（TASK_005 doc-only canonical promotion）已合并入 main
  （main HEAD = `5604bb086668ac6a857fc2c5ad86b0b8eb2713ae`）。
- 当前分支 `task/TASK_GOV_003-bounded-verification` 已含
  `.claude/skills/bounded-verification/SKILL.md` 与
  `templates/task-contract.md`、`templates/final-report.md`，
  以及对 `CLAUDE.md` 的最低限度引用扩展。
- 不修改任何代码 / 测试 / result*.xlsx / MODEL.md / RESULTS.md / README.md。
- 不启动 Q3、不启动 TASK_006、不自动合并。
- 等待本任务的 Draft PR 接受 Hermes 只读核验 + MAIN / 用户决策。

## 当前唯一任务
Hermes 只读核验本 TASK_GOV_003 PR 的 Git / 文件 / push / PR 状态。
不修改本任务分支；不出 result*.xlsx；不启动 TASK_006。

## 当前 canonical Q2 result（已合并入 main）
等级：`FORMAL BUDGET-LIMITED BEST-KNOWN Q2 CANDIDATE / LOCAL CONVERGENCE NOT ESTABLISHED / NOT A PROVEN GLOBAL OPTIMUM`

参数：

| 变量 | 值 |
|---|---|
| heading_rad | 3.126767217560497 |
| speed_mps | 116.43351397802584 |
| release_time_s | 1.2672692031529031 |
| delay_s | 3.789202402720746 |
| total_duration_s | 4.260970878601073 |
| interval (s) | (5.089825368500298, 9.350796247101371) |

相对旧 formal-search candidate 的改善量：
- duration 改善 = 4.260970878601073 − 2.48275905609131 ≈ 1.778211822509763 s
- 相对改善 ≈ 71.6%

## 已验证维度（main HEAD 已含）
- identity verified (worktree-clean + HEAD identity + script sha256 + q2_search code identity + refinement_config_sha256 + parent candidate identity + checkpoint_source_head_sha 全通过)
- scan stability verified (0.02 / 0.010 / 0.005 三档 duration 完全一致)
- physical validity verified (speed ∈ [70, 140], release ≥ 0, delay 在落地约束内, heading ∈ [0, 2π))
- independent audit evaluator recomputation: 6/6 exact match

## 未建立维度（不冒充）
- local convergence: NOT ESTABLISHED
- global optimum: NOT A PROVEN GLOBAL OPTIMUM
- official answer: NOT

canonical promotion 仅基于独立 Audit 结论 B（doc-only P2 闭合后允许晋升），不基于本地梯度 / 局部极值 / 解析证明。

## 旧候选（已降级）
参数 `(3.121767217560497, 115.43351397802584, 1.7672692031529031, 3.889202402720746)`，duration `2.48275905609131 s`，已降级为 `HISTORICAL FORMAL-SEARCH CANDIDATE`，**不再**作为当前 canonical Q2 result。

旧 16 项扰动实测：5/16 改善 → 旧候选不是 16 项 one-var 邻域局部极值，因此触发 bounded refinement；bounded refinement 在固定预算内发现更优候选 4.260970878601073 s。

## 本轮 TASK_GOV_003 新增文件

| 路径 | 用途 |
|---|---|
| `.claude/skills/bounded-verification/SKILL.md` | bounded verification 治理 Skill v0.1 |
| `.claude/skills/bounded-verification/templates/task-contract.md` | expensive task 启动前必填的契约模板 |
| `.claude/skills/bounded-verification/templates/final-report.md` | 任务完成汇报模板 |
| `CLAUDE.md` | 在 §0 必读 Skill 列表中追加 bounded-verification；其他治理规则不动 |
| `START_HERE.md` | 替换为 TASK_GOV_003 阶段（本文） |
| `NEXT_TASK.md` | 替换为 TASK_GOV_003 Hermes handoff |

- 工作草案（不提交）:
  - `work/task006_readiness.md`（Q3 启动预案，gitignored）
  - `work/bounded_verification_skill_plan.md`（Skill 设计草稿，gitignored）

## 当前阻断
无。Hermes 只读核验完成后由 MAIN / 用户决定 Ready / merge。

## 下一里程碑
合并本 TASK_GOV_003 后立项 TASK_006（Q3 三弹串接 / result1.xlsx 提交物）；
TASK_006 启动前需先冻结 `work/task_context.json` 预算，并按
`templates/task-contract.md` 填写。

## 尚未进入
- Q3 三弹串接；
- result1.xlsx 生成；
- Q4 / Q5；
- 论文；
- 进一步 formal search / refinement（bounded verification 预算未授权扩展）；
- Audit CC / Hermes 自动启动（MAIN 决定）。
