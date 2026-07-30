# 项目驾驶舱

## 最终目标
完成 2025 CUMCM A 题 Q1–Q5 的可信建模、数值策略、result1/2/3.xlsx 与论文。

## 当前问题
Q3 — FY1 投放 3 枚烟幕干扰弹对 M1 的串接遮蔽策略（待写入 result1.xlsx）。

## 当前阶段
TASK_006 — Q3 THREE-BOMB FORMAL BOUNDED SEARCH — **`TASK_006-P3`（RESULT1.XLSX ARTIFACT GENERATION）PLAN 冻结**。

- main HEAD = `007b93d301db73c9a73904337de34d1b4e13467e`（PR #12 TASK_GOV_003 已 merged）。
- 当前分支 `task/TASK_006-q3-three-bombs` 从 main 新建（基于 `007b93d3`）。
- Pilot P0/P1 已 closure v2 完成（94-evaluation Pilot evidence 保留；commit `59999f9a`）；
  closure v2 FIX=`a139988` + VERIFIED=`31ddb7b`。
- **P2 已完成**：Q3 三弹正式 bounded search（512 evaluations / 834.07 s）；
  best `total_union_duration_s = 4.469013137817817385 s`，HEAD `70a4dd767f057edded65bd2011ac544347f661dc`。
- **P2C 已闭合（CANDIDATE CLOSURE）**：基于 P2 stage E top-1 候选，做 32-evaluation
  bounded closure，墙钟 290.54 s ≤ 600 s。closure best = 4.478218820691105 s（vs P2 incumbent 4.469013137817385 s）。
- **P3 当前阶段**：对已冻结 Q3 候选执行一次高精度重建，并从官方空白模板生成、回读和核验 result1.xlsx。
  本轮不是搜索、refinement 或 optimization。
  冻结的 8 维 candidate 见 NEXT_TASK.md / RESULTS.md / MODEL.md。
- 目标 acceptance level：`BUDGET_LIMITED_BEST_KNOWN`（P3 沿用 P2C 等级；生成 + 回读核验后冻结 RESULT1）。
- **不**重跑 P2 512 / P2C 32 / 调整任何决策变量 / 产生 challenger；
  **不**修改 foundation（Q1 / Q2 / q3_three_bombs）；
  **不**修改官方模板 ZIP；
  **不**生成 result2.xlsx / result3.xlsx；
  **不**启动 Audit / Hermes / Q4 / Q5 / Ready / merge。

## 当前唯一任务
TASK_006-P3 — Q3 RESULT1.XLSX ARTIFACT GENERATION（基于 P2C 冻结候选的高精度重建 + 官方模板生成 + 回读核验）。

- branch: `task/TASK_006-q3-three-bombs`
- base SHA: `007b93d301db73c9a73904337de34d1b4e13467e`
- pre-wip head: `843b4a1e5791e67a09c377c2173f16a1105ab944` (P2C VERIFIED)
- p2 evidence commit: `dc970a483ab9e05d76467decf63f61dff70f0862` (HEAD=70a4dd7, 512 evals / 834.07 s)
- p2c evidence commit: `843b4a1e5791e67a09c377c2173f16a1105ab944` (HEAD=843b4a1, 32 evals / 290.54 s)
- phase: `TASK_006-P3` / contract_version: 5 (P2C v4 → P3 v5, 7-field resume identity + canonical reconstruction + result1.xlsx round-trip)
- target_acceptance_level: `BUDGET_LIMITED_BEST_KNOWN Q3 CANDIDATE WITH GENERATED AND ROUND-TRIP-VERIFIED RESULT1.XLSX` (P3 沿用 P2C 等级)
- frozen 8-dim candidate (不允许改变):
  `heading_rad=3.127613485137657, speed_mps=116.12799297398149, release_time_1_s=0.993241052387636, delay_1_s=3.720360704323356, release_time_2_s=4.88566490244013, delay_2_s=3.7704749980723404, release_time_3_s=10.157737577136487, delay_3_s=3.7180978311642083`
- reference_total_union_duration_s: **4.478218820691105**（P2C canonical unchanged）
- reconstruction profile: **fine / scan_step=0.005**
- reconstruction mismatch tolerance: **1e-12**

### 本轮允许修改（P3 阶段：10 个 tracked 路径 + PR body + work/）

| 路径 | 用途 |
|---|---|
| `scripts/build_result1.py` (NEW) | result1.xlsx 生成器（ZIP 内 official template → in-memory edit → write outputs/submission/result1.xlsx） |
| `outputs/q3/q3_result1_artifact_summary.json` (NEW) | P3 artifact summary（identity / contract / canonical_candidate / canonical_reconstruction / workbook / status / result_level） |
| `outputs/q3/q3_candidate_closure_summary.json` | P2C candidate closure 摘要（P3 沿用） |
| `outputs/submission/result1.xlsx` (NEW) | 官方模板填充后的最终 result1.xlsx（来自 `题目及模板/..._结果模板.zip` 内 result1.xlsx） |
| `tests/test_q3.py` | 搜索模块 + result1 模块测试（117 P0/P1/P2/P2C + ≥ 22 P3 = ≥ 139 cases，含 FakeEvaluator + temporary workbook，**不**调用真实 Q3 evaluator） |
| `START_HERE.md` | 当前页（本文） |
| `NEXT_TASK.md` | 当前唯一任务边界 |
| `MODEL.md` | Q3 P3 artifact generation 合同 |
| `RESULTS.md` | Q3 P3 artifact generation 结果（result1.xlsx round-trip） |
| `README.md` | 当前阶段同步 |

### 禁止修改
`src/q1_baseline.py`、`src/q1_cylinder.py`、`src/q2_single_bomb.py`、`src/q2_search.py`、
`src/q3_three_bombs.py`、`src/q3_search.py`、`outputs/q2/`、`outputs/submission/result2.xlsx`、
`outputs/submission/result3.xlsx`、`problem/`、`scripts/build_result1.py` 之外的 `scripts/` 内容、
`configs/`、`题目及模板/`、`CLAUDE.md`、`.claude/`、`.gitignore`、
任何其它 `result*.xlsx`、Q1 / Q2 / q3_three_bombs 单元测试、Pilot / P2 / P2C 已有日志 / checkpoint。

## 当前 canonical Q2 result（已合并入 main，不冒充）
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

## 当前 Pilot 证据（P0/P1 closure v2 锁定）

| 字段 | 值 |
|---|---|
| original_pilot_execution_head | `4d442a7a16127ca0166d1114656b5fe4d5546b4d` |
| original_evidence_commit | `59999f9aba063e90d8428f5f783d8cc4abf10d62` |
| closure_code_head | `a139988` |
| closure_evidence_head | `31ddb7b516e05eb6c20ac465e13b339b6ab70dbc` |
| q3_candidate_evaluations | 94 |
| single_bomb_evaluator_calls | 282 |
| total_wall_clock_seconds | 243.124 |
| best_pilot_total_union_duration_s | 3.7881687521934495 |

## 当前正式搜索预算（P2 实测，保留）

| 维度 | 上限 | 实测 |
|---|---|---|
| 顶层 Q3 candidate evaluation | **512** | **512** |
| Run wall-clock | **1200 s** | **834.07 s** |
| Single-bomb subcall | 1536 | **1536** |

| 阶段 | 分配 | 实测 | Profile |
|---|---|---|---|
| Stage A — structured coarse exploration | 360 | 360 | coarse (0.05) |
| Stage B — bounded coarse refinement | 120 | 120 | coarse (0.05) |
| Stage C — medium finalist recheck | 24 | 24 | medium (0.02) |
| Stage D — fine finalist recheck | 6 | 6 | fine (0.01) |
| Stage E — high-resolution verification | 2 | 2 | fine (0.005) |
| **总计** | **512** | **512** | |

seeds = `[2025, 2026, 2027]`。任一达到上限不自动延长。
- best_total_union_duration_s = **4.469013137817385 s** (P2 阶段)
- best candidate source = `stage_E_high_resolution_verification_rank_1`

### P2C candidate closure（32 evals / 600 s, F1-F5 pipeline, 保留）

| 维度 | 上限 | 实测 |
|---|---|---|
| 顶层 Q3 candidate evaluation | **32** | **32** |
| Run wall-clock | **600 s** | **290.54 s** |
| Single-bomb subcall | 96 | **96** (= 32 × 3) |
| Test Q3 evaluation 数（fake eval only） | 0 | **0** (real eval) |
| system_error_count | 0 | **0** |

| 阶段 | 分配 | Profile |
|---|---|---|
| F1 — one-variable perturbation | **16** | coarse (0.05) |
| F2 — coordinate combinations | **8** | coarse (0.05) |
| F3 — medium recheck | **4** | medium (0.02) |
| F4 — fine recheck | **2** | fine (0.01) |
| F5 — high-resolution verification | **2** | fine (0.005) |
| **总计** | **32** | |

**P2C 闭包结果**（保留）：
- closure `best_total_union_duration_s` = **4.478218820691105 s**
- closure canonical source = `TASK_006-P2C F5 high-resolution verification`
- vs P2 incumbent 4.469013137817385 s：绝对改善 = **+0.009206 s**，相对改善 ≈ **+0.21%**
- 原 P2 512/834.07 s 证据保留不变（HEAD=`70a4dd7`、evidence=`dc970a48`）
- 等级仍为 `BUDGET_LIMITED_BEST_KNOWN Q3 CANDIDATE / LOCAL CONVERGENCE NOT ESTABLISHED / NOT A PROVEN GLOBAL OPTIMUM`，但 P2C 完成后 result1.xlsx 生成已具备条件。

### P3 当前阶段（canonical reconstruction + result1.xlsx）

| 维度 | 上限 | 实测（待 WORKING 完成后填） |
|---|---|---|
| 顶层 Q3 canonical reconstruction | **1** | **1**（一次 fine / scan_step=0.005 重建） |
| Run wall-clock | **300 s** | TBD |
| Single-bomb subcall | **3** | TBD (= 1 × 3) |
| Test Q3 evaluation 数（fake eval only） | 0 | **0** (real eval) |
| system_error_count | 0 | **0** |
| Reconstructed total_union_duration_s 与 reference（4.478218820691105）的差 | **≤ 1e-12** | TBD |

P3 单次重建调用：
- 同一 8 维 candidate, 同一 `sample_level=fine`, 同一 `scan_step=0.005`,
  同一 `src/q3_three_bombs.evaluate_three_bomb_strategy`;
- 必须输出 `bomb_evaluations` (3 items) + `union_intervals` + `total_union_duration_s`;
- 期望 `total_union_duration_s ≈ 4.478218820691105`（P2C F5 冻结候选）。

### result1.xlsx 写入合同（P3）

| 列 | 写入值 |
|---|---|
| A | `heading_deg = degrees(heading_rad) % 360`, 0 ≤ heading_deg < 360, **三行相同** |
| B | `speed_mps`, **三行相同** |
| C | 1, 2, 3 (顺序) |
| D | bomb i release_point x |
| E | bomb i release_point y |
| F | bomb i release_point z |
| G | bomb i detonation_point x |
| H | bomb i detonation_point y |
| I | bomb i detonation_point z |
| J | bomb i own `total_duration_s`（**逐弹自身 duration**，**不是 union**） |

- 三弹 union 总时长 4.478218820691105 **不**写入 J 列；仅写入
  `q3_result1_artifact_summary.json` 与 `RESULTS.md` 与 PR body。
- 表头、附注、merged-cell、freeze panes 全部保留原样。
- 所有 Excel 单元格必须为数值类型；不得写带单位字符串、公式、JSON、NaN、Inf、None。

### result1.xlsx 回读核验（P3）

- 关闭 workbook 后从磁盘重新打开；
- 逐格读取三行 A:J；
- abs_tol = 1e-10；rel_tol = 1e-12；
- 模板 fingerprint 保留：sheet names, active sheet, sheet dimensions, merged-cell ranges, freeze panes, header values, annotation / footer text, row heights, column widths, non-data cell values/formulas/style_id, number formats, print settings。
- 任意非 A:J 数据 cell 改变 → FAIL。

## 当前阻断
无。Pilot 已 closure；P2 已完成 512 evals；P2C 已闭合 32 evals；P3 PLAN 已冻结。
P3 仅执行一次高精度重建 + 模板写入 + 回读核验，不修改 foundation。

## 下一里程碑
- 本轮（P3）完成后等待 Final Audit + Hermes（MAIN 决定启动）；
- 合并 PR #13 后进入 Q4 / Q5（MAIN 决定）；
- 论文编写。

## 尚未进入
- Final Audit / Hermes（MAIN 决定启动）；
- Q4 / Q5；
- result2.xlsx / result3.xlsx；
- 修改 Q1 / Q2 / q3_three_bombs foundation；
- 重跑 Pilot / 重跑 P2 512 evals / 重跑 P2C 32 evals；
- 声称 FORMAL_RESULT_VERIFIED / local convergence / global optimum / 官方答案。
