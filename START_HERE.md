# 项目驾驶舱

## 最终目标
完成 2025 CUMCM A 题 Q1–Q5 的可信建模、数值策略、result1/2/3.xlsx 与论文。

## 当前问题
Q3 — FY1 投放 3 枚烟幕干扰弹对 M1 的串接遮蔽策略（待写入 result1.xlsx）。

## 当前阶段
TASK_006 — Q3 THREE-BOMB FORMAL BOUNDED SEARCH — `TASK_006-P2`。

- main HEAD = `007b93d301db73c9a73904337de34d1b4e13467e`（PR #12 TASK_GOV_003 已 merged）。
- 当前分支 `task/TASK_006-q3-three-bombs` 从 main 新建（基于 `007b93d3`）。
- Pilot P0/P1 已 closure v2 完成（94-evaluation Pilot evidence 保留；commit `59999f9a`）；
  closure v2 FIX=`a139988` + VERIFIED=`31ddb7b`。
- **本轮 P2**：Q3 三弹正式 bounded search（512 evaluations / 1200 s）。
- 目标 acceptance level：`BUDGET_LIMITED_BEST_KNOWN Q3 CANDIDATE`。
- **不**重新 Pilot；**不**修改 foundation（Q1 / Q2 / q3_three_bombs）；
  **不**生成 result1.xlsx；**不**启动 P3 / Q4 / Q5；
  **不**自动启动 Audit / Hermes；**不**自动 Ready / merge。

## 当前唯一任务
TASK_006-P2 — Q3 Three-Bomb Formal Bounded Search。

- branch: `task/TASK_006-q3-three-bombs`
- base SHA: `007b93d301db73c9a73904337de34d1b4e13467e`
- pre-wip head: `31ddb7b516e05eb6c20ac465e13b339b6ab70dbc`
- phase: `TASK_006-P2` / contract_version: 3
- target_acceptance_level: `BUDGET_LIMITED_BEST_KNOWN`

### 本轮允许修改（仅 5 个 tracked 路径 + PR body）

| 路径 | 用途 |
|---|---|
| `src/q3_search.py` (NEW) | Q3 正式 bounded search 模块（5 阶段 / 512 evals） |
| `outputs/q3/q3_formal_search_summary.json` (NEW) | 正式搜索最终摘要 |
| `tests/test_q3.py` | 搜索模块测试（≥ 20 cases，含 FakeEvaluator） |
| `START_HERE.md` | 当前页（本文） |
| `NEXT_TASK.md` | 当前唯一任务边界 |
| `MODEL.md` | Q3 正式搜索合同 |
| `RESULTS.md` | Q3 正式搜索结果（BUDGET_LIMITED_BEST_KNOWN） |
| `README.md` | 当前阶段同步 |

### 禁止修改
`src/q1_baseline.py`、`src/q1_cylinder.py`、`src/q2_single_bomb.py`、`src/q2_search.py`、
`src/q3_three_bombs.py`、`outputs/q2/`、`outputs/submission/`、`problem/`、`scripts/`、
`configs/`、`CLAUDE.md`、`.claude/`、`.gitignore`、任何 `result*.xlsx`、
Q1 / Q2 / q3_three_bombs 单元测试、Pilot 已有日志 / checkpoint。

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

## 当前正式搜索预算（P2 实测）

| 维度 | 上限 | 实测 |
|---|---|---|
| 顶层 Q3 candidate evaluation | **512** | **512** |
| Run wall-clock | **1200 s** | **834.07 s** |
| Test wall-clock | 300 s | ≤ 60 s (dry-run) |
| Test Q3 evaluation 数（fake eval only） | ≤ 20 | **0** (real eval) |
| Single-bomb subcall | 1536 | **1536** |

| 阶段 | 分配 | 实测 | Profile |
|---|---|---|---|
| Stage A — structured coarse exploration | 360 | 360 | coarse (0.05) |
| Stage B — bounded coarse refinement | 120 | 120 | coarse (0.05) |
| Stage C — medium finalist recheck | 24 | 24 | medium (0.02) |
| Stage D — fine finalist recheck | 6 | 6 | fine (0.01) |
| Stage E — high-resolution verification | 2 | 2 | fine (0.005) |
| **总计** | **512** | **512** | |

seeds = `[2025, 2026, 2027]`。任一达到上限不自动延长。**结果**：
- best_total_union_duration_s = **4.469013137817385 s**
- best candidate source = `stage_E_high_resolution_verification_rank_1` (Stage E top-1, scan_step=0.005)
- 改善 (相对 Pilot 3.788169 s) = **+0.680844 s (+17.97%)**

## 当前阻断
无。Pilot 已 closure；P2 立项已 MAIN 显式批准；Audit PASS 已获。
P2 必须基于冻结的 Q2 / Q3 foundation 跑 512 evals / 1200 s，不得修改 foundation。

## 下一里程碑
- 合并本 TASK_006-P2 后等待 MAIN 决定 result1.xlsx 生成阶段；
- MAIN 决定是否启动 Q4 / Q5；
- 论文编写。

## 尚未进入
- result1.xlsx 生成；
- TASK_006-P3 / Q4 / Q5；
- 论文；
- Audit CC / Hermes 自动启动（MAIN 决定）；
- 修改 Q1 / Q2 / q3_three_bombs foundation；
- 重跑 Pilot；
- 声称 FORMAL_RESULT_VERIFIED / local convergence / global optimum。
