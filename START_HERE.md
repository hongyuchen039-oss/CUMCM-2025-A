# 项目驾驶舱

## 最终目标
完成 2025 CUMCM A 题 Q1–Q5 的可信建模、数值策略、result1/2/3.xlsx 与论文。

## 当前问题
Q3 — FY1 投放 3 枚烟幕干扰弹对 M1 的串接遮蔽策略（待写入 result1.xlsx）。

## 当前阶段
TASK_006 — Q3 THREE-BOMB FORMAL BOUNDED SEARCH — **`TASK_006-P2C`（CANDIDATE CLOSURE）已闭合**。

- main HEAD = `007b93d301db73c9a73904337de34d1b4e13467e`（PR #12 TASK_GOV_003 已 merged）。
- 当前分支 `task/TASK_006-q3-three-bombs` 从 main 新建（基于 `007b93d3`）。
- Pilot P0/P1 已 closure v2 完成（94-evaluation Pilot evidence 保留；commit `59999f9a`）；
  closure v2 FIX=`a139988` + VERIFIED=`31ddb7b`。
- **P2 已完成**：Q3 三弹正式 bounded search（512 evaluations / 834.07 s）；
  best `total_union_duration_s = 4.469013137817385 s`，HEAD `70a4dd767f057edded65bd2011ac544347f661dc`。
- **P2C 已闭合（CANDIDATE CLOSURE）**：基于 P2 stage E top-1 候选，做 32-evaluation
  bounded closure（F1=16 one-var perturbations / F2=8 coordinate combinations /
  F3=4 medium recheck / F4=2 fine recheck / F5=2 high-resolution verification），
  墙钟 290.54 s ≤ 600 s。closure best = 4.478218820691105 s（vs P2 incumbent 4.469013137817385 s,
  绝对改善 +0.009206 s / 相对 +0.21%）。原 P2 512/834.07 s 证据保留，
  HEAD=`70a4dd767f057edded65bd2011ac544347f661dc` 不变。
- 目标 acceptance level：`BUDGET_LIMITED_BEST_KNOWN Q3 CANDIDATE`。
- **不**重新 Pilot；**不**修改 foundation（Q1 / Q2 / q3_three_bombs）；
  **不**生成 result1.xlsx；**不**启动 P3 / Q4 / Q5；
  **不**自动启动 Audit / Hermes；**不**自动 Ready / merge。

## 当前唯一任务
TASK_006-P2C — Q3 Candidate Closure (F1=16 / F2=8 / F3=4 / F4=2 / F5=2)。

- branch: `task/TASK_006-q3-three-bombs`
- base SHA: `007b93d301db73c9a73904337de34d1b4e13467e`
- pre-wip head: `31ddb7b516e05eb6c20ac465e13b339b6ab70dbc`
- p2 evidence commit: `dc970a483ab9e05d76467decf63f61dff70f0862` (HEAD=70a4dd7, 512 evals / 834.07 s)
- p2c working commit: `def084d9bc38bf92cd714d24676016fa8911a83c` (FIX commit; closure 32 evals / 290.54 s)
- phase: `TASK_006-P2C` / contract_version: 4 (P2 v3 → P2C v4, sequential stage propagation + cumulative wall-clock + 8-field resume identity)
- target_acceptance_level: `BUDGET_LIMITED_BEST_KNOWN Q3 CANDIDATE` (P2C 沿用 P2 等级)

### 本轮允许修改（P2C 阶段扩展：8 个 tracked 路径 + PR body + work/）

| 路径 | 用途 |
|---|---|
| `src/q3_search.py` | Q3 正式 bounded search 模块（P2 5 阶段 + P2C F1-F5 closure） |
| `outputs/q3/q3_formal_search_summary.json` | P2 正式搜索最终摘要（已加 evidence_closure 块） |
| `outputs/q3/q3_candidate_closure_summary.json` (NEW) | P2C candidate closure 摘要 |
| `tests/test_q3.py` | 搜索模块测试（≥ 52 P2 + 36 P2C = ≥ 88 cases，含 FakeEvaluator） |
| `START_HERE.md` | 当前页（本文） |
| `NEXT_TASK.md` | 当前唯一任务边界 |
| `MODEL.md` | Q3 正式搜索合同（P2 + P2C closure 算法合同） |
| `RESULTS.md` | Q3 正式搜索结果（P2 512 evals + P2C 32 evals） |
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

### P2C candidate closure（32 evals / 600 s, F1-F5 pipeline）

| 维度 | 上限 | 实测 |
|---|---|---|
| 顶层 Q3 candidate evaluation | **32** | **32** |
| Run wall-clock | **600 s** | **290.54 s** |
| Single-bomb subcall | 96 | **96** (= 32 × 3) |
| Test Q3 evaluation 数（fake eval only） | 0 | **0** (real eval) |
| system_error_count | 0 | **0** |

| 阶段 | 分配 | Profile | 说明 |
|---|---|---|---|
| F1 — one-variable perturbation | **16** | coarse (0.05) | 8 变量 × 2 方向，步长 heading ±0.002 rad / speed ±0.5 m/s / release ±0.10 s / delay ±0.05 s |
| F2 — coordinate combinations | **8** | coarse (0.05) | heading+speed / release_1+delay_1 / release_2+delay_2 / release_3+delay_3 / heading+speed+release_1+delay_1 / release_2+delay_2+release_3+delay_3 / all_release_delay / all_eight |
| F3 — medium recheck | **4** | medium (0.02) | parents = incumbent + best-of-previous-stage challengers, top-3 selection |
| F4 — fine recheck | **2** | fine (0.01) | parents = F3 完成后 top-k |
| F5 — high-resolution verification | **2** | fine (0.005) | final canonical selection, tie-break on evaluation_id within ε=1e-12 s |
| **总计** | **32** | | |

**P2C 闭包结果**：
- closure `best_total_union_duration_s` = **4.478218820691105 s**
- closure canonical source = `TASK_006-P2C F5 high-resolution verification`
- vs P2 incumbent 4.469013137817385 s：
  - 绝对改善 = **+0.009206 s**
  - 相对改善 ≈ **+0.21%**（F1 16 项扰动中部分挑战者改善，但 F5 high-resolution 复评后差异由浮点精度和候选结构共同决定）
- 原 P2 512/834.07 s 证据保留不变（HEAD=`70a4dd767f057edded65bd2011ac544347f661dc`、evidence=`dc970a483ab9e05d76467decf63f61dff70f0862`）。
- 等级仍为 `BUDGET_LIMITED_BEST_KNOWN Q3 CANDIDATE / LOCAL CONVERGENCE NOT ESTABLISHED / NOT A PROVEN GLOBAL OPTIMUM / RESULT1.XLSX NOT GENERATED`。

## 当前阻断
无。Pilot 已 closure；P2 已完成 512 evals；P2C 已闭合 32 evals。
P2C 必须基于 P2 stage E top-1 候选做 bounded refinement，不得修改 foundation。

## 下一里程碑
- 合并本 TASK_006-P2C 后等待 MAIN 决定 result1.xlsx 生成阶段；
- MAIN 决定是否启动 Q4 / Q5；
- 论文编写。

## 尚未进入
- result1.xlsx 生成；
- TASK_006-P3 / Q4 / Q5；
- 论文；
- Audit CC / Hermes 自动启动（MAIN 决定）；
- 修改 Q1 / Q2 / q3_three_bombs foundation；
- 重跑 Pilot / 重跑 P2 512 evals；
- 声称 FORMAL_RESULT_VERIFIED / local convergence / global optimum。
