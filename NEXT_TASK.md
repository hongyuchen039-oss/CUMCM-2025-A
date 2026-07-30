# TASK_006 FINAL AUDIT AND HERMES GATE

> 关闭 TASK_006-P3 后, **唯一** 下一门是 Final Audit CC + Hermes.
> 本文档是 P3 之后的真实当前任务边界, 不再展开 P3 施工细节.

## 阶段状态

| 阶段 | 状态 |
|---|---|
| P0/P1 (closure v2) | **COMPLETE** |
| P2 (Q3 formal bounded search) | **COMPLETE** |
| P2C (Q3 candidate closure) | **COMPLETE** |
| P3 (Q3 RESULT1.XLSX artifact generation) | **COMPLETE** |

- result1.xlsx **GENERATED** (官方模板 in-memory edit, 5911 bytes)
- round-trip **VERIFIED** (abs_tol=1e-10, rel_tol=1e-12, 12-field fingerprint preserved)
- frozen 8-dimensional candidate **不再调整**
- 不再允许任何 Q3 expensive evaluation / 任何 evaluator rerun

## 身份链 (锁定)

| 字段 | SHA |
|---|---|
| main HEAD | `007b93d301db73c9a73904337de34d1b4e13467e` |
| p3_starting_head (P2C VERIFIED, pre-P3 base) | `843b4a1e5791e67a09c377c2173f16a1105ab944` |
| p3_execution_head (P3 PLAN+WORKING clean HEAD) | `cb3dd83c834ec3b5f8c1e85213ddc63301e3d709` |
| p3_evidence_commit (P3 VERIFIED) | `a04e158b7848d7d5a3d381ed9e5871961267ed37` |
| official_template_zip_sha256 | `f9879c0d36b7bdccb99fb330a8032e62851ab1a1f0a1636c92440a1cdaec658e` |
| official_template_member_sha256 | `d1773205296034c0f02ed7f848f8f1e66af633d1e6562938e059450a554b930e` |
| result1.xlsx output SHA | `b938a90b96181be14990d5bd3395c2cff72e93035828542617571ddc1d754847` |
| result1_run_identity_sha256 | `82065aa5fe4d4e6036691a053b38732b9ff1f50497083e3306e262e82a4bfc65` |

注: 历史施工记录 (`03ddda3` PLAN / `0597028` WORKING / `108d21b` headers-fix) 在 P3 身份
链内属于过程 commit, 真实 `p3_execution_head` 仍是 `cb3dd83c`, 真实
`p3_evidence_commit` 仍是 `a04e158b`. 若任何叙述把 `108d21b` 当作 execution-head,
属于 **HISTORICAL COMMIT ROLE REQUIRES FINAL AUDIT ANCESTRY CHECK**,
不由本 closeout 自行重定义, 也不重跑 P3.

## 当前 Gate

| 角色 | 状态 |
|---|---|
| Final Audit CC (read-only) | **NOT STARTED** |
| Hermes (read-only) | **NOT STARTED** |
| MAIN 最终裁决 | **PENDING** |
| Mark Ready | **NO** (MAIN 决定) |
| Ordinary merge | **NO** (MAIN 决定) |
| TASK_007 | **NOT STARTED** |

任务编号固定:

- `TASK_006` = Q3 + result1.xlsx
- `TASK_007` = Q4 + result2.xlsx
- `TASK_008` = Q5 + result3.xlsx
- `TASK_009` = unified recomputation / sensitivity / robustness / figures
- `TASK_010` = paper / consistency / final package

## 当前 result level

- `BUDGET_LIMITED_BEST_KNOWN Q3 CANDIDATE WITH GENERATED AND ROUND-TRIP-VERIFIED RESULT1.XLSX`
- `LOCAL CONVERGENCE NOT ESTABLISHED`
- `NOT A PROVEN GLOBAL OPTIMUM`
- `NOT FORMAL_RESULT_VERIFIED`

## P3 双数值证据 (profile provenance)

| 数值 | profile | scan_step | 来源 |
|---|---|---|---|
| 4.478218820691105 s | coarse | 0.05 | P2C closure selection score (32 evals argmax; 历史证据) |
| 4.478204178810118 s | fine | 0.005 | P3 canonical reconstruction (1 real Q3 call; result1.xlsx 几何来源) |
| 1.4641880987653622e-05 s | — | — | absolute_profile_difference_s |

## result1.xlsx 生成合同 (冻结)

| 列 | 写入值 |
|---|---|
| A | `179.1990526465902` (degrees(heading_rad) % 360, 三行相同) |
| B | `116.1279929739815` (三行相同) |
| C | 1, 2, 3 |
| D-F | release_point i xyz (bomb i 投放点) |
| G-I | detonation_point i xyz (bomb i 起爆点) |
| J | bomb i own `total_duration_s` (逐弹自身 duration, **不是 union**) |

- 三弹 union 4.478204178810118 (fine/0.005) **不**写入 J 列
- 三弹 union 4.478218820691105 (coarse/0.05) **不**写入 J 列
- 模板 fingerprint (sheet names / merged cells / freeze panes / header / A6 附注 /
  row heights / column widths) **全部保留原样**
- 所有 cell 均为数值类型

## 关闭条件 (本门)

- Audit CC PASS
- Hermes PASS
- MAIN 最终裁决
- 用户明确授权: `git merge ...`
- 合并 + 重新核验 main 之后, 才允许启动 TASK_007

不自动:

- 启动 Final Audit CC
- 启动 Hermes
- Mark Ready
- merge
- 启动 TASK_007
- 声称 FORMAL_RESULT_VERIFIED