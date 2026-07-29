# 项目驾驶舱

## 最终目标
完成 2025 CUMCM A 题 Q1–Q5 的可信建模、数值策略、result1/2/3.xlsx 与论文。

## 当前问题
Q2 单架 FY1 投放一枚烟幕弹的最优策略（已冻结为 canonical budget-limited best-known, 待 Hermes / 用户合并决策）。

## 当前阶段
TASK_005 DOC-ONLY AUDIT CLOSURE COMPLETE — WAITING FOR HERMES / USER MERGE DECISION。

独立 Audit 结论：**B. AUDIT PASSED WITH DOC-ONLY P2 — PROMOTE AFTER ONE SMALL DOCUMENTATION COMMIT**。
- 无 P0
- 无 P1
- 身份链全部通过
- 独立数学复算 6/6 精确一致
- system_error = 0
- 不需要重跑 3×1000
- 不需要重跑完整 16 项扰动
- 不需要重跑全量测试
- 仅需一个 doc-only commit 闭合 P2

本轮已完成 P2 doc-only commit。本仓库当前任务**已停**，等 Hermes 只读核验最终 SHA / 改文件 / push / PR 状态，然后由 MAIN / 用户决定 Ready / merge。Q3 尚未启动。

## 当前唯一任务
Hermes 只读核验最终仓库和 PR 事实。不修改本任务分支；不出 result*.xlsx；不启动 TASK_006。

## 当前 canonical Q2 result
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

## 已验证维度
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

旧 16 项扰动实测：5/16 改善（speed_mps −1 / release_time_s −1 / delay_s +0.1）→ 旧候选不是 16 项 one-var 邻域局部极值，因此触发 bounded refinement；bounded refinement 在固定预算内发现更优候选 4.260970878601073 s。

## 证据分层
| 阶段 | 范围 | 测试 |
|---|---|---|
| formal P1 closure | 3 seeds × 1000 + 16 项扰动 | 473/473 full regression PASS |
| bounded refinement | 32 evaluations, 3 levels, ≤2100s | 210/210 tests.test_q2_search PASS |
| clean-head verification identity closure | 5 evaluator calls (2 delay ±0.025 + 3 stability) | 不重跑测试 |
| independent Audit | 6 evaluator calls, exact match | 不重跑测试 |

## 当前最大不确定性
- local convergence 未建立：新候选未在 clean HEAD 上重跑完整 16 项扰动（按 Audit 结论 B 不需要重跑）。
- global optimum 未证明：bounded refinement 预算耗尽于 32/32 evaluations（budget exhausted ≠ code failed）。
- checkpoint 顶层 head_sha 在 verify_done_clean_head 状态下写入 4a1cbd9（与 refinement_config / parent identity 严格匹配），已知 nonblocking P2 不修改。

## 当前阻断
无。Hermes 只读核验完成后由 MAIN / 用户决定 Ready / merge。

## 下一里程碑
合并后立项 TASK_006（Q3 三弹串接 / result1.xlsx 提交物）；TASK_GOV_003 bounded-verification Skill 计划在 TASK_006 启动前可选规划。

## 尚未进入
- Q3 三弹串接；
- result1.xlsx 生成；
- Q4 / Q5；
- 论文；
- 进一步 formal search / refinement（bounded verification 预算未授权扩展）；
- Audit CC / Hermes 自动启动（MAIN 决定）。