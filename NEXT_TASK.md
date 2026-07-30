# TASK_006 — Q3 THREE-BOMB FORMAL BOUNDED SEARCH — P3 (RESULT1.XLSX ARTIFACT GENERATION)

> 本轮 (TASK_006-P3) 目标:
>
> 1. ✅ **不重跑** 94-evaluation Pilot；
> 2. ✅ **不重跑** P2 512-evaluation 正式搜索；
> 3. ✅ **不重跑** P2C 32-evaluation candidate closure；
> 4. ✅ **不修改** Q1 / Q2 / q3_three_bombs foundation；
> 5. ✅ **不修改** 官方空白模板 ZIP 与内含 result1.xlsx；
> 6. ✅ 对 P2C 冻结候选执行一次 high-resolution canonical reconstruction（fine / scan_step=0.005）；
> 7. ✅ 重建后核验 `abs(reconstructed - 4.478218820691105) <= 1e-12`；
> 8. ✅ 从官方模板生成 `outputs/submission/result1.xlsx`；
> 9. ✅ 程序从磁盘回读 + 逐格核验 A:J；
> 10. ✅ 输出 `outputs/q3/q3_result1_artifact_summary.json`；
> 11. ✅ 5 docs 同步；
> 12. ✅ 等待 Final Audit + Hermes。
>
> 最终结果等级：`BUDGET_LIMITED_BEST_KNOWN`（沿用 P2C 等级，result1.xlsx 生成 + 回读 PASS 后冻结）。

## P3 重建 profile

| 维度 | 值 |
|---|---|
| sample_level | **fine** |
| scan_step_s | **0.005** |
| Q3 evaluation 数 | 1 |
| Single-bomb evaluator calls | 3 (1 × 3) |
| Wall-clock cap | 300 s |
| Wall-clock gate | elapsed >= 300 → stop |

## P3 result1.xlsx 写入合同

| 列 | 写入值 | 说明 |
|---|---|---|
| A | heading_deg | degrees(heading_rad) modulo 360, 0 <= heading_deg < 360, 三行相同 |
| B | speed_mps | 三行相同 |
| C | i ∈ {1, 2, 3} | 烟幕干扰弹编号 |
| D-F | release_point i xyz | bomb i 投放点 |
| G-I | detonation_point i xyz | bomb i 起爆点 |
| J | bomb i own total_duration_s | **逐弹自身有效干扰时长**（**不是 union**） |

- 所有 Excel 单元格必须为数值类型，不得写带单位字符串、公式、JSON、NaN、Inf、None。
- 三弹 union 总时长 4.478218820691105 **不**写入 J 列；仅写入 `q3_result1_artifact_summary.json` 与 RESULTS.md 与 PR body。
- 表头、附注、sheet 结构、merged-cell、freeze panes 全部保留原样。

## P3 回读核验

- 关闭 workbook 后从磁盘重新打开；
- 逐格读取三行 A:J；
- abs_tol = 1e-10；rel_tol = 1e-12；
- 必须验证：workbook 可打开、sheet 正确、10 列、3 行、A/B 三行相同、C = [1, 2, 3]、D-F 与 release_points 对应、G-I 与 detonation_points 对应、J 与 per_bomb_duration_s 对应、所有数据均有限数值、无第四条意外 Q3 数据、表头未改、附注未改、原模板文件 SHA 不变、输出文件 SHA-256 已记录。

## P3 Resume identity (7 fields)

- 路径：`work/q3_result1/checkpoint.json`
- **checkpoint_schema_version = 5**
- 7 字段（任一 mismatch → BLOCKED）：
  1. `execution_head_sha`
  2. `contract_snapshot_sha256`
  3. `q2_single_bomb_code_sha256`
  4. `q3_three_bombs_code_sha256`
  5. `result1_builder_code_sha256`
  6. `canonical_candidate_sha256`
  7. `official_template_sha256`

## 停止条件

本轮（TASK_006-P3）完成后立即停止。

不自动：
- 启动 Audit CC；
- 启动 Hermes；
- 开始 Q4 / Q5；
- Ready；
- merge。

由 MAIN / 用户显式决定 Final Audit + Hermes 启动与是否进入 Q4 / Q5。

## 验收 Gate (P3 必须全部满足)

- [ ] 冻结的 8 维变量未改变；
- [ ] real Q3 calls = exactly 1；
- [ ] reconstructed duration 与 4.478218820691105 在 1e-12 内一致；
- [ ] 三枚逐弹证据完整（intervals / duration / release_point / detonation_point）；
- [ ] union 测度一致；
- [ ] official template 原件未改（SHA 不变）；
- [ ] result1.xlsx 来自官方模板（basename = `result1.xlsx`）；
- [ ] A/B/C/D/E/F/G/H/I/J 映射正确；
- [ ] J 为逐弹 duration（非 union）；
- [ ] workbook 可重新打开；
- [ ] round-trip PASS；
- [ ] workbook SHA recorded；
- [ ] FAST PASS；
- [ ] TASK PASS（117 P0/P1/P2 + ≥ 22 P3 = ≥ 139 tests）；
- [ ] milestone regression PASS（tests.test_q1_baseline + tests.test_q1_cylinder + tests.test_q2_search + tests.test_q3）；
- [ ] result1.xlsx tracked；
- [ ] result2.xlsx / result3.xlsx 不存在；
- [ ] Q1/Q2/Q3 evaluator 未改；
- [ ] PR #13 保持 Draft / unmerged；
- [ ] Audit / Hermes 未启动；
- [ ] Q4 / Q5 未启动。

## 当前任务边界 (P3)

- Base: `main` = `007b93d301db73c9a73904337de34d1b4e13467e`
- Branch: `task/TASK_006-q3-three-bombs`
- Phase: `TASK_006-P3`（RESULT1.XLSX ARTIFACT GENERATION）
- Contract version: 5 (v5 snapshot: `work/task_contracts/TASK_006-P3-v5.json`, untracked)
  - previous: TASK_006-P2C v4 (`work/task_contracts/TASK_006-P2C-v4.json`, untracked)
  - previous: TASK_006-P2 v3 (`work/task_contracts/TASK_006-P2-v3.json`, untracked)
- 启动 Harness `work/task_context.json` (gitignored)
  - expected_head = `843b4a1e5791e67a09c377c2173f16a1105ab944` (P2C VERIFIED commit)
  - HEAD on PLAN commit will become `PLAN: freeze Q3 result1 artifact contract` SHA
- P2C evidence commit (predecessor): `843b4a1e5791e67a09c377c2173f16a1105ab944` (32 evals / 290.54 s, preserved)
- P2 evidence commit (predecessor): `dc970a483ab9e05d76467decf63f61dff70f0862` (512 evals / 834.07 s, preserved)

### 冻结的 8 维 candidate (本轮不得改变)

| 变量 | 值 |
|---|---|
| heading_rad | 3.127613485137657 |
| speed_mps | 116.12799297398149 |
| release_time_1_s | 0.993241052387636 |
| delay_1_s | 3.720360704323356 |
| release_time_2_s | 4.88566490244013 |
| delay_2_s | 3.7704749980723404 |
| release_time_3_s | 10.157737577136487 |
| delay_3_s | 3.7180978311642083 |
| reference_total_union_duration_s | **4.478218820691105** |

### 本轮允许修改（仅 5 个 tracked 路径 + PR body + work/）

| 路径 | 用途 |
|---|---|
| `scripts/build_result1.py` (NEW) | Q3 result1 模板加载 / 表头识别 / 写入 / 回读核验 / fingerprint |
| `outputs/q3/q3_result1_artifact_summary.json` (NEW) | P3 artifact 摘要 |
| `outputs/q3/q3_candidate_closure_summary.json` | 仅允许增加 P3 reconstruction pointer，不得篡改 P2C 原始计数或结果 |
| `outputs/submission/result1.xlsx` (NEW) | 从官方模板生成 |
| `tests/test_q3.py` | 增加 P3 测试（fake evaluator + temporary workbook，0 real Q3 eval in tests） |
| `START_HERE.md` / `NEXT_TASK.md` / `MODEL.md` / `RESULTS.md` / `README.md` | P3 sync |
| `work/` | gitignored — checkpoint / contract snapshot / logs |

### 禁止修改 (P3)

`src/q1_baseline.py`、`src/q1_cylinder.py`、`src/q2_single_bomb.py`、`src/q2_search.py`、
`src/q3_three_bombs.py`、`src/q3_search.py`、`problem/`、`scripts/`（除 `scripts/build_result1.py`）、
`configs/`、`CLAUDE.md`、`.claude/`、`.gitignore`、
`outputs/q2/`、`outputs/submission/result2.xlsx`、`outputs/submission/result3.xlsx`、
`题目及模板/`（含 ZIP 内文件）。

### 禁止动作 (P3)

- 重跑 P2 512-evaluation 正式搜索
- 重跑 P2C 32-evaluation candidate closure
- 产生 challenger
- 调整 speed / heading / release / delay 任一变量
- 自动修正候选
- 启动 Q4 / Q5
- 生成 result2.xlsx / result3.xlsx
- 修改官方空白模板原件
- 覆盖模板 ZIP
- 启动 Audit CC
- 启动 Hermes
- Ready
- merge
- 修改 main
- 声称全局最优 / 局部收敛 / 官方答案 / FORMAL_RESULT_VERIFIED

### 本轮允许修改（仅 5 个 tracked 路径 + PR body + work/）

| 路径 | 用途 |
|---|---|
| `src/q3_search.py` | Q3 正式 bounded search 模块（P2 5 阶段 / 512 evals + P2C F1-F5 closure / 32 evals） |
| `outputs/q3/q3_formal_search_summary.json` | P2 正式搜索最终摘要（已加 evidence_closure 块 + formal_schedule_complete + pilot_complete_legacy_field） |
| `outputs/q3/q3_candidate_closure_summary.json` (NEW) | P2C closure 摘要 |
| `tests/test_q3.py` | 搜索模块测试（52 P0/P1 + 29 P2 + 36 P2C，含 FakeEvaluator） |
| `START_HERE.md` | 当前页（本文） |
| `NEXT_TASK.md` | 当前唯一任务边界 |
| `MODEL.md` | Q3 正式搜索合同（P2 + P2C closure 算法合同） |
| `RESULTS.md` | Q3 正式搜索结果（P2 512 evals + P2C 32 evals） |
| `README.md` | 当前阶段同步 |
| `work/` | gitignored — checkpoint / contract snapshot / logs |

### 禁止修改 (P2C)

`src/q1_baseline.py`、`src/q1_cylinder.py`、`src/q2_single_bomb.py`、`src/q2_search.py`、
`src/q3_three_bombs.py`、`outputs/q2/`、`outputs/submission/`、`problem/`、`scripts/`、
`configs/`、`CLAUDE.md`、`.claude/`、`.gitignore`、任何 `result*.xlsx`、
Q1 / Q2 / q3_three_bombs 单元测试、Pilot / P2 已有日志 / checkpoint。

### Pilot 证据保留（P2 / P2C 锁定）

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

### P2 证据保留（P2C 锁定，不重跑）

| 字段 | 值 |
|---|---|
| original_p2_execution_head | `70a4dd767f057edded65bd2011ac544347f661dc` |
| original_p2_evidence_commit | `dc970a483ab9e05d76467decf63f61dff70f0862` |
| q3_candidate_evaluations | 512 |
| single_bomb_evaluator_calls | 1536 |
| total_wall_clock_seconds | 834.0665795999812 |
| best_p2_total_union_duration_s | 4.469013137817385 |
| p2_search_rerun_performed | false |

## P2 预算（精确分配，512 Q3 evaluations / 1200 s wall-clock, 已完成）

| 维度 | 上限 |
|---|---|
| 顶层 Q3 candidate evaluation（总开销） | **512** |
| Run wall-clock | **1200 s** |
| Test wall-clock | 300 s |
| Single-bomb subcall 上限 | 512 × 3 = 1536 |
| Test 阶段 real Q3 evaluation 数 | 0（FakeEvaluator only） |

### P2 阶段分配（必须总和 = 512）

| 阶段 | 分配 | Profile | 解释 |
|---|---|---|---|
| Stage A — structured coarse exploration | **360** | coarse (0.05) | 3 seeds × 120 = 360 |
| Stage B — bounded coarse refinement | **120** | coarse (0.05) | 12 parents × 10 perturbations = 120 |
| Stage C — medium finalist recheck | **24** | medium (0.02) | 12 parents × 2 perturbation sets |
| Stage D — fine finalist recheck | **6** | fine (0.01) | top-6 finalists |
| Stage E — high-resolution verification | **2** | fine (0.005) | final top-2 验证 / tie-break |
| **总计** | **512** | | |

### P2 Stage A 子分配（每 seed 120 = 60 + 40 + 20）

| 子块 | 每 seed | 总 | 说明 |
|---|---|---|---|
| A1 staggered canonical family | 20 | 60 | 三枚弹在 r1 ~ best_pilot_r1 + 4s / 8s；delay near best_pilot ± small noise |
| A2 compensated release chain | 13 | 40 | release_time_i = best_pilot_r1 + sum(j<i, best_pilot_delay_j / 2) |
| A3 bounded directional diversity | 7 | 20 | heading ± 0.05 rad / speed ± 2 m/s 围绕 best_pilot |

## P2 Checkpoint / Resume

- 路径：`work/q3_formal/checkpoint.json`
- **checkpoint_schema_version = 3**
- 每 Q3 candidate evaluation 后原子写入（temp + flush + fsync + os.replace）
- resume 强制校验 **7 字段**（任一不匹配立即停止，exit 2，**不静默 fallback**）：
  1. `execution_head_sha`
  2. `contract_snapshot_sha256`
  3. `q2_single_bomb_code_sha256`
  4. `q3_three_bombs_code_sha256`
  5. `q3_search_code_sha256`
  6. `formal_config_sha256`
  7. `candidate_schema_version`
- corrupt / load error → `status = CHECKPOINT_LOAD_ERROR`, exit 2
- identity mismatch → `status = RESUME_IDENTITY_MISMATCH`, exit 2

## P2C 预算（精确分配，32 Q3 evaluations / 600 s wall-clock, 已完成）

| 维度 | 上限 |
|---|---|
| 顶层 Q3 candidate evaluation（总开销） | **32** |
| Run wall-clock | **600 s** |
| Single-bomb subcall 上限 | 32 × 3 = 96 |
| Test 阶段 real Q3 evaluation 数 | 0（FakeEvaluator only） |
| system_error_count | 0 |

### P2C 阶段分配（必须总和 = 32）

| 阶段 | 分配 | Profile | 解释 |
|---|---|---|---|
| F1 — one-variable perturbation | **16** | coarse (0.05) | 8 变量 × 2 方向（+/-）= 16 候选；步长 heading ±0.002 rad / speed ±0.5 m/s / release_time ±0.10 s / delay ±0.05 s；带 fallback scales [0.5, 0.25] |
| F2 — coordinate combinations | **8** | coarse (0.05) | heading+speed / release_1+delay_1 / release_2+delay_2 / release_3+delay_3 / heading+speed+release_1+delay_1 / release_2+delay_2+release_3+delay_3 / all_release_delay / all_eight |
| F3 — medium recheck | **4** | medium (0.02) | parents = incumbent + best-of-previous-stage challengers, top-3 selection |
| F4 — fine recheck | **2** | fine (0.01) | parents = F3 完成后 top-k |
| F5 — high-resolution verification | **2** | fine (0.005) | final canonical selection, tie-break on evaluation_id within ε=1e-12 s |
| **总计** | **32** | | |

### P2C Schedule SHA256

- `closure_schedule_sha256` = SHA-256 of canonical JSON representation of
  `{F1_records, F2_records}` (F3/F4/F5 records built at runtime from real previous-stage results).
- F1 16 records = 8 vars × 2 signs (heading, speed, release_1, delay_1, release_2, delay_2, release_3, delay_3)。
- F2 8 records = 8 fixed combinations。
- F3/F4/F5 parents = `{incumbent_candidate} ∪ {best-of-previous-stage challengers up to top_k=3}`。
- selection_rule: `max total_union_duration_s; tie-break on evaluation_id lexicographic only when abs(duration_a - duration_b) <= 1e-12`。

### P2C Sequential Propagation

- 不再 pre-build all stages at once；改为 sequential propagation：
  `F1 records (deterministic) → execute F1 → build F3 records from F1 real results → execute F3 → build F4 records from F3 real results → execute F4 → build F5 records from F4 real results → execute F5`。
- F2 records 与 F1 records 同时 pre-build（不依赖 F1 执行结果；只依赖 incumbent）。
- F3/F4/F5 records 在前驱阶段执行完成后才能构建。
- per-stage schedule immutable after construction。

### P2C Cumulative Wall-Clock

- `elapsed_seconds_total = previous_elapsed_seconds_total + current_process_elapsed_seconds`。
- On resume: previous_elapsed 必须从 checkpoint 加载，**不**reset to 0。
- Wall-clock gate: `cumulative_elapsed >= wall_clock_cap` → stop, write checkpoint, no auto extension。
- Heartbeat 输出 cumulative elapsed。

## P2C Checkpoint / Resume (8-field identity)

- 路径：`work/q3_candidate_closure/checkpoint.json`
- **checkpoint_schema_version = 4**
- resume 强制校验 **8 字段**（任一不匹配立即停止，exit 2，**不静默 fallback**）：
  1. `execution_head_sha`
  2. `contract_snapshot_sha256`
  3. `q2_single_bomb_code_sha256`
  4. `q3_three_bombs_code_sha256`
  5. `q3_search_code_sha256`
  6. `closure_config_sha256`
  7. `candidate_schema_version`
  8. `closure_schedule_sha256`（新增）
- corrupt / load error → `status = CHECKPOINT_LOAD_ERROR`, exit 2
- identity mismatch → `status = RESUME_IDENTITY_MISMATCH`, exit 2

## P2C Summary Schema (canonical)

`outputs/q3/q3_candidate_closure_summary.json` 至少含：
- `phase_id = "TASK_006-P2C"`
- `contract_version = 4`
- `result_level.declared_level = "BUDGET_LIMITED_BEST_KNOWN"`
- `result_level.not_a_proven_global_optimum = true`
- `result_level.local_convergence_established = false`
- `result_level.not_a_formal_q3_result = true`
- `result_level.result1_xlsx_generated = false`
- `stage_counts`: {A, B, C, D, E (all 0), F1=16, F2=8, F3=4, F4=2, F5=2, total=32}
- `counts`: {completed_q3_evaluations=32, single_bomb_evaluator_calls=96, system_error_count=0, unique_q3_evaluation_ids=32}
- `canonical_q3_candidate`: 8 维 canonical candidate
- `canonical_q3_evidence`: {rehydrated_from_completed_records: true, total_union_duration_s}
- `canonical_total_union_duration_s`: 4.478218820691105
- `comparison`: {incumbent_reference_total_union_duration_s=4.469013137817385, absolute_improvement_s=0.009205682873719923, relative_improvement=0.0020598916561287784}
- `incumbent_high_resolution`: {candidate (8 维), p2_evidence_commit, p2_execution_head, reference_total_union_duration_s, source}
- `original_p2_evidence_preservation`: {original_p2_execution_head, original_p2_evidence_commit, original_512_evaluations_preserved=true, original_834_07s_wall_clock_preserved=true, p2_search_rerun_performed=false}
- `identity`: 8-field + closure_run_identity_sha256
- `p2c_contract_snapshot_path`: `work/task_contracts/TASK_006-P2C-v4.json`
- `status`: {pilot_complete: true, evaluation_budget_exhausted: false, wall_clock_gate_hit: false, run_system_error: false, checkpoint_load_error: false, resume_identity_mismatch: false}

## 测试分级 (P2)

### FAST（≤30 s）
- py_compile (q3_search, tests)
- candidate generation (A1 / A2 / A3 deterministic, seed-locked)
- budget arithmetic (Stage A + B + C + D + E = 512)
- resume identity 7 fields presence
- FakeEvaluator + dry-run path
- empty / single-result selection logic

### TASK（≤300 s, 真实 Q3 evaluation = 0）
- 仅 FakeEvaluator 测试；**不**调用 `src.q3_three_bombs.evaluate_three_bomb_strategy`
- scheduler, parent selection, perturbation generation, stage budget enforcement
- checkpoint / resume path synthetic
- search summary JSON schema validation

Q3 real-eval budget in tests = 0, ≤ cap.

### FULL

**SKIPPED**. MAIN 未授权 FULL；Q3 Formal Search is bounded only.

## 提交序列 (P2)

1. **PLAN**: `work/task_contracts/TASK_006-P2-v3.json` + `work/task_context.json` + 4 docs (`START_HERE.md` / `NEXT_TASK.md` / `MODEL.md` / `RESULTS.md` / `README.md`)。不 amend, 不 force push.
2. **WORKING**: `src/q3_search.py` (NEW) + `tests/test_q3.py` (search tests)。Harness + FAST + TASK pass.
3. **VERIFIED**: `outputs/q3/q3_formal_search_summary.json` (after formal search) + 5 docs sync.
4. **Push + PR body**: `task/TASK_006-q3-three-bombs`, push 后更新 PR #13 body 保留 P0/P1 identity + 追加 P2 identity.

## Draft PR (P2)

- Title: `TASK_006: Q3 three-bomb formal bounded search (P2)`
- base: `main`
- PR body 必须包含：
  - **6-field P0/P1 identity 拆分**（保留）
  - **P2 identity 拆分**（新增）：
    - **p2_base_sha** = `007b93d301db73c9a73904337de34d1b4e13467e`
    - **p2_closure_evidence_head** = `31ddb7b516e05eb6c20ac465e13b339b6ab70dbc`
    - **p2_plan_commit** = PLAN SHA
    - **p2_working_commit** = WORKING SHA
    - **p2_verified_commit** = VERIFIED SHA
    - **p2_current_pr_head** = current PR head SHA (after push)
  - 5 阶段 / 512 evals / 1200 s 严格说明
  - 测试分级（≥ 20 tests，0 real Q3 eval in tests）
  - 真实 evaluator counts: search 512 + tests 0 = 512
  - single-bomb subcall counts: 512 × 3 = 1536
  - declared_level = `BUDGET_LIMITED_BEST_KNOWN`
  - **NOT** FORMAL_RESULT_VERIFIED
  - **NOT** local convergence established
  - **NOT** global optimum
  - result1.xlsx NOT generated
  - Pilot NOT rerun
  - Q1 / Q2 / q3_three_bombs NOT modified
  - v1 / v2 contract snapshots preserved
  - original Pilot log / checkpoint preserved
  - audit / hermes / P3 / Q4 / Q5 NOT STARTED

PR 保持 Draft. 不 Ready. 不 merge.

## 验收 Gate (P2 + P2C 必须全部满足)

### P2 (已通过)

- [x] `src/q3_search.py` 实现：5 阶段 / 512 evals / 1200 s gate
- [x] `build_formal_schedule(seeds=[2025,2026,2027])` 产出 **360 + 120 + 24 + 6 + 2 = 512** records
- [x] 每 record 含 `schedule_index / stage / profile / candidate_source / candidate / expected_q3_evaluation_id`
- [x] 每 Q3 evaluation 后原子写 `work/q3_formal/checkpoint.json`
- [x] Resume 校验 7 字段（任一 mismatch → fail-closed, exit 2）
- [x] 真实 Q3 evaluation 数 = 512（= hard cap）
- [x] Real run wall-clock = 834.0666 s ≤ 1200 s hard cap
- [x] Wall-clock gate hit → 原子写 checkpoint + 不自动延长 + 状态 `WALL_CLOCK_GATE_HIT`
- [x] Evaluation budget exhausted → 原子写 checkpoint + 状态 `EVALUATION_BUDGET_EXHAUSTED`
- [x] System error → 状态 `RUN_SYSTEM_ERROR` + 不冒充 0
- [x] Stage A / B / C / D / E selection rules 正确实现
- [x] Stage E 复评 top-2 finalists；tie-break on union duration
- [x] Multi-seed：每 seed 独立 dispatch，结果聚合
- [x] 输出 `outputs/q3/q3_formal_search_summary.json` 含全部 canonical 字段
- [x] 单元测试 ≥ 81 cases (52 P0/P1 + 29 P2)，全部 PASS
- [x] RESULT1.XLSX NOT GENERATED
- [x] Q1 / Q2 / q3_three_bombs NOT modified
- [x] v1 / v2 contract snapshots preserved
- [x] original Pilot log / checkpoint preserved
- [x] TASK_006-P3 / Q4 / Q5 NOT STARTED
- [x] audit / hermes NOT STARTED

### P2C (本轮, 已通过)

- [x] sequential stage propagation：F1 → execute → build F3 → execute → build F4 → execute → build F5 → execute
- [x] cumulative wall-clock：`previous_elapsed + current_process_elapsed = elapsed_total`，on resume 不 reset
- [x] 8-field resume identity（含 `closure_schedule_sha256`）
- [x] F1=16 + F2=8 + F3=4 + F4=2 + F5=2 = **32** Q3 evaluations（实测 = 32）
- [x] wall-clock 290.54 s ≤ 600 s hard cap
- [x] F1/F2/F3/F4/F5 selection rules 正确实现（F3 top-3 选 F1+F2 challengers + incumbent；F4/F5 top-k）
- [x] canonical selection: max total_union_duration_s; tie-break on evaluation_id within ε=1e-12
- [x] 单弹 evaluator calls = 32 × 3 = 96（实测 = 96）
- [x] system_error_count = 0（实测 = 0）
- [x] 输出 `outputs/q3/q3_candidate_closure_summary.json` 含全部 canonical 字段（含 `original_p2_evidence_preservation` 块）
- [x] `outputs/q3/q3_formal_search_summary.json` 增加 `evidence_closure` 块 + `formal_schedule_complete: true` + `pilot_complete_legacy_field: true`
- [x] `git rm --cached work/task_contracts/TASK_006-P2-v3.json`（local file preserved）
- [x] 单元测试 ≥ 117 cases (52 P0/P1 + 29 P2 + 36 P2C)，全部 PASS
- [x] 0 real Q3 eval in tests（仅 FakeEvaluator）
- [x] RESULT1.XLSX NOT GENERATED
- [x] Q1 / Q2 / q3_three_bombs NOT modified
- [x] original Pilot / P2 log / checkpoint preserved (HEAD=70a4dd7, evidence=dc970a48)
- [x] TASK_006-P3 / Q4 / Q5 NOT STARTED
- [x] audit / hermes NOT STARTED

## 停止条件

本轮（`TASK_006-P2C`）完成后立即停止。

不自动：
- 启动 Audit CC；
- 启动 Hermes；
- 开始 TASK_006-P3 / result1.xlsx / Q4 / Q5；
- Ready；
- merge。

由 MAIN / 用户显式决定 TASK_006-P3 立项、result1.xlsx 启动、P3 预算选定。
