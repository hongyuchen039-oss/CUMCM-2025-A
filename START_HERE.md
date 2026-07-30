# 项目驾驶舱

## 最终目标
完成 2025 CUMCM A 题 Q1–Q5 的可信建模、数值策略、result1/2/3.xlsx 与论文。

## 当前问题
Q3 — FY1 投放 3 枚烟幕干扰弹对 M1 的串接遮蔽策略（待写入 result1.xlsx）。

## 当前阶段
TASK_006 — Q3 THREE-BOMB MODEL CONTRACT + REAL EVALUATOR + BOUNDED PILOT — `TASK_006-P0/P1`。

- main HEAD = `007b93d301db73c9a73904337de34d1b4e13467e`（PR #12 TASK_GOV_003 已 merged）。
- 当前分支 `task/TASK_006-q3-three-bombs` 从 main 新建（基于 `007b93d3`）。
- PR #12（TASK_GOV_003）已合并；bounded verification Skill v0.1 已落地。
- 启动 Q3 三弹数学与工程合同；实现真实 Q3 evaluator；bounded pilot 测量成本并向 MAIN 提交正式预算建议。
- **本轮仅 P0/P1**：不执行 Q3 Formal Search；不生成 result1.xlsx；不进入 P2。

## 当前唯一任务
TASK_006-P0/P1 — Q3 Three-Bomb Model Contract + Real Evaluator + Bounded Pilot。

- branch: `task/TASK_006-q3-three-bombs`
- base SHA: `007b93d301db73c9a73904337de34d1b4e13467e`
- pre-wip head: `007b93d301db73c9a73904337de34d1b4e13467e`

### 本轮允许修改（仅 8 个文件 + PR body）

| 路径 | 用途 |
|---|---|
| `src/q3_three_bombs.py` | 三弹 evaluator + bounded pilot CLI |
| `tests/test_q3.py` | Q3 单元测试 |
| `outputs/q3/` | Q3 产物（`q3_pilot_summary.json`） |
| `START_HERE.md` | 当前页（本文） |
| `NEXT_TASK.md` | 当前唯一任务边界 |
| `MODEL.md` | Q3 数学与工程合同 |
| `RESULTS.md` | Pilot 结果（EXPERIMENTAL only） |
| `README.md` | 当前阶段同步 |

### 禁止修改
`src/q1_baseline.py`、`src/q1_cylinder.py`、`src/q2_single_bomb.py`、`src/q2_search.py`、
`outputs/q2/`、`outputs/submission/`、`problem/`、`scripts/`、`configs/`、`CLAUDE.md`、
`.claude/`、`.gitignore`、任何 `result*.xlsx`、Q1/Q2 单元测试。

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

## 当前 Pilot 预算

| 维度 | 上限 |
|---|---|
| 顶层 Q3 candidate evaluation（pilot cap） | 96 |
| 单弹 evaluator 调用次数 | 上限 96 × 3 = 288 |
| Pilot wall-clock | 900 s |
| 真实 TASK 测试 Q3 evaluation 数 | 3 |
| 总 expensive evaluation 上限 | 99 |
| 测试 wall-clock | 600 s |

任一达到上限都不得自动延长。

## 当前阻断
无。Pilot 完成后向 MAIN 提交正式预算建议；TASK_006-P2（Q3 Formal Search + result1.xlsx）需 MAIN 显式立项。

## 下一里程碑
合并本 TASK_006 后等待 MAIN 决定 Pilot 预算冻结；MAIN 基于实测 median / p90 决定：
- TASK_006-P2 正式 Q3 search 预算（evaluations / wall-clock / 验证集）
- 是否进入 result1.xlsx 生成阶段
- 是否启动 Q4 / Q5

## 尚未进入
- Q3 Formal Search；
- result1.xlsx 生成；
- Q4 / Q5；
- 论文；
- 进一步 formal search / refinement（bounded verification 预算未授权扩展）；
- Audit CC / Hermes 自动启动（MAIN 决定）。