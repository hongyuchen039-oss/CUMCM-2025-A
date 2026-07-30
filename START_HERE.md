# 项目驾驶舱

## 最终目标
完成 2025 CUMCM A 题 Q1–Q5 的可信建模、数值策略、result1/2/3.xlsx 与论文。

## 当前状态
**TASK_006-P3 COMPLETE** — Q3 RESULT1.XLSX GENERATED, round-trip VERIFIED.

- main HEAD = `007b93d301db73c9a73904337de34d1b4e13467e` (PR #12 TASK_GOV_003 已 merged).
- 当前分支 `task/TASK_006-q3-three-bombs` 从 main 新建 (基于 `007b93d3`).
- PR #13 = Open / Draft / Unmerged / Mergeable.

### 阶段门

| 阶段 | 状态 |
|---|---|
| P0/P1 (closure v2) | **COMPLETE** |
| P2 (Q3 formal bounded search) | **COMPLETE** (512 evals / 834.07 s) |
| P2C (Q3 candidate closure) | **COMPLETE** (32 evals / 290.54 s) |
| P3 (Q3 RESULT1.XLSX artifact generation) | **COMPLETE** (1 fine/0.005 reconstruction / 81.66 s) |
| result1.xlsx | **GENERATED** (5911 bytes, sheet `Sheet1`, A1:J6) |
| result1.xlsx round-trip | **PASS** (abs_tol=1e-10, rel_tol=1e-12) |
| result1 SHA | `b938a90b96181be14990d5bd3395c2cff72e93035828542617571ddc1d754847` |

### 当前 Gate

| 角色 | 状态 |
|---|---|
| Final Audit CC | **NOT STARTED** |
| Hermes | **NOT STARTED** |
| TASK_007 | **NOT STARTED** |
| Mark Ready | **NO** |
| Ordinary merge | **NO** |

### 当前 result level

- **BUDGET_LIMITED_BEST_KNOWN Q3 CANDIDATE WITH GENERATED AND ROUND-TRIP-VERIFIED RESULT1.XLSX**
- LOCAL CONVERGENCE NOT ESTABLISHED
- NOT A PROVEN GLOBAL OPTIMUM
- NOT FORMAL_RESULT_VERIFIED
- result2.xlsx = **NOT GENERATED**
- result3.xlsx = **NOT GENERATED**

## 身份链 (锁定)

| 字段 | SHA / Value |
|---|---|
| main HEAD | `007b93d301db73c9a73904337de34d1b4e13467e` |
| p3_starting_head (P2C VERIFIED) | `843b4a1e5791e67a09c377c2173f16a1105ab944` |
| p3_execution_head | `cb3dd83c834ec3b5f8c1e85213ddc63301e3d709` |
| p3_evidence_commit | `a04e158b7848d7d5a3d381ed9e5871961267ed37` |
| official_template_zip_sha256 | `f9879c0d36b7bdccb99fb330a8032e62851ab1a1f0a1636c92440a1cdaec658e` |
| official_template_member_sha256 | `d1773205296034c0f02ed7f848f8f1e66af633d1e6562938e059450a554b930e` |
| result1.xlsx output SHA | `b938a90b96181be14990d5bd3395c2cff72e93035828542617571ddc1d754847` |
| result1_run_identity_sha256 | `82065aa5fe4d4e6036691a053b38732b9ff1f50497083e3306e262e82a4bfc65` |

注: 历史过程 commit (`03ddda3` PLAN, `0597028` WORKING, `108d21b` headers-fix) 是 P3
身份链内的施工过程; 真实 `p3_execution_head` 仍是 `cb3dd83c`, 真实
`p3_evidence_commit` 仍是 `a04e158b`. 若有叙述把 `108d21b` 当作 execution-head,
属于 **HISTORICAL COMMIT ROLE REQUIRES FINAL AUDIT ANCESTRY CHECK** —
不由本 closeout 自行重定义, 不重跑 P3.

## 任务编号固定

| 编号 | 范围 |
|---|---|
| `TASK_006` | Q3 + result1.xlsx |
| `TASK_007` | Q4 + result2.xlsx |
| `TASK_008` | Q5 + result3.xlsx |
| `TASK_009` | unified recomputation / sensitivity / robustness / figures |
| `TASK_010` | paper / consistency / final package |

`TASK_006-P4` / `TASK_006-P5` 编号方案作废, 不得在当前 / 未来任务中使用.

## 冻结的 8-dimensional candidate (不再调整)

```
heading_rad       = 3.127613485137657
speed_mps         = 116.12799297398149
release_time_1_s  = 0.993241052387636
delay_1_s         = 3.720360704323356
release_time_2_s  = 4.88566490244013
delay_2_s         = 3.7704749980723404
release_time_3_s  = 10.157737577136487
delay_3_s         = 3.7180978311642083
```

## P3 双数值证据 (profile provenance)

| 数值 | profile | scan_step | 来源 |
|---|---|---|---|
| 4.478218820691105 s | coarse | 0.05 | P2C closure selection score (32 evals argmax, 历史证据) |
| 4.478204178810118 s | fine | 0.005 | P3 canonical reconstruction (1 real Q3 call, result1.xlsx 几何来源) |
| 1.4641880987653622e-05 s | — | — | absolute_profile_difference_s |

## 当前 canonical Q2 result (已合并入 main, 不冒充)

等级: `FORMAL BUDGET-LIMITED BEST-KNOWN Q2 CANDIDATE / LOCAL CONVERGENCE NOT ESTABLISHED / NOT A PROVEN GLOBAL OPTIMUM`

参数:

| 变量 | 值 |
|---|---|
| heading_rad | 3.126767217560497 |
| speed_mps | 116.43351397802584 |
| release_time_s | 1.2672692031529031 |
| delay_s | 3.789202402720746 |
| total_duration_s | 4.260970878601073 |
| interval (s) | (5.089825368500298, 9.350796247101371) |

## Pilot 证据 (P0/P1 closure v2, 锁定)

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

## P2 / P2C 证据 (锁定, 不重跑)

| 字段 | P2 | P2C |
|---|---|---|
| evidence_commit | `dc970a483ab9e05d76467decf63f61dff70f0862` | `843b4a1e5791e67a09c377c2173f16a1105ab944` |
| execution_head | `70a4dd767f057edded65bd2011ac544347f661dc` | `843b4a1e5791e67a09c377c2173f16a1105ab944` |
| top-level Q3 evals | 512 | 32 |
| single-bomb subcall | 1536 | 96 |
| run wall-clock | 834.07 s | 290.54 s |
| best duration | 4.469013137817385 s | 4.478218820691105 s |

## 当前唯一门

TASK_006 FINAL AUDIT AND HERMES GATE — 详见 [NEXT_TASK.md](./NEXT_TASK.md).

- Audit CC read-only 不调用 evaluator.
- Hermes read-only 不调用 evaluator.
- Audit + Hermes PASS 后由 MAIN 最终裁决; 用户明确授权后才允许 Mark Ready / ordinary merge.
- 合并并重新核验 main 后, 才允许启动 TASK_007.

## 尚未进入

- Final Audit / Hermes (MAIN 决定启动)
- TASK_007 / TASK_008 (Q4 / Q5)
- result2.xlsx / result3.xlsx
- 修改 Q1 / Q2 / q3_three_bombs foundation
- 重跑 Pilot / P2 512 / P2C 32 / P3 reconstruction
- 声称 FORMAL_RESULT_VERIFIED / local convergence / global optimum / 官方答案