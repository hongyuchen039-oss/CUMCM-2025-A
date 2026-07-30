# TASK_006 — Q3 THREE-BOMB FORMAL BOUNDED SEARCH — P2 (COMPLETE)

> 本轮 (TASK_006-P2) 已完成。
>
> 1. ✅ **不重跑** 94-evaluation Pilot；
> 2. ✅ **不修改** Q1 / Q2 / q3_three_bombs foundation；
> 3. ✅ 实现 `src/q3_search.py` Q3 正式 bounded search 模块；
> 4. ✅ 5 阶段正式搜索：Stage A 360 / B 120 / C 24 / D 6 / E 2 = **512** Q3 evaluations（实测 = 512）；
> 5. ✅ **wall-clock 834.0666 s ≤ 1200 s**；
> 6. ✅ Multi-seed deterministic：`[2025, 2026, 2027]`；
> 7. ✅ Checkpoint / resume（7-field identity，fail-closed）；
> 8. ✅ 输出 `outputs/q3/q3_formal_search_summary.json`（BUDGET_LIMITED_BEST_KNOWN Q3 CANDIDATE）；
> 9. ✅ 单元测试 81/81 PASS（52 P0/P1 + 29 P2 search，含 FakeEvaluator + dry-run + scheduler + resume identity）；
> 10. ✅ PR #13 body 同步（保留 P0/P1 identity + 追加 P2 identity）。
>
> 最终结果等级只能是：`BUDGET_LIMITED_BEST_KNOWN`。

## 当前任务边界 (P2)

- Base: `main` = `007b93d301db73c9a73904337de34d1b4e13467e`
- Branch: `task/TASK_006-q3-three-bombs`
- Phase: `TASK_006-P2`
- Contract version: 3 (v3 snapshot: `work/task_contracts/TASK_006-P2-v3.json`)
- 启动 Harness `work/task_context.json` (gitignored, expected_head = `31ddb7b516e05eb6c20ac465e13b339b6ab70dbc`)

### 本轮允许修改（仅 5 个 tracked 路径 + PR body + work/）

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
| `work/` | gitignored — checkpoint / contract snapshot / logs |

### 禁止修改 (P2)

`src/q1_baseline.py`、`src/q1_cylinder.py`、`src/q2_single_bomb.py`、`src/q2_search.py`、
`src/q3_three_bombs.py`、`outputs/q2/`、`outputs/submission/`、`problem/`、`scripts/`、
`configs/`、`CLAUDE.md`、`.claude/`、`.gitignore`、任何 `result*.xlsx`、
Q1 / Q2 / q3_three_bombs 单元测试、Pilot 已有日志 / checkpoint。

### Pilot 证据保留（P2 锁定）

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

## P2 预算（精确分配，512 Q3 evaluations / 1200 s wall-clock）

| 维度 | 上限 |
|---|---|
| 顶层 Q3 candidate evaluation（总开销） | **512** |
| Run wall-clock | **1200 s** |
| Test wall-clock | 300 s |
| Single-bomb subcall 上限 | 512 × 3 = 1536 |
| Test 阶段 real Q3 evaluation 数 | 0（FakeEvaluator only） |

### 阶段分配（必须总和 = 512）

| 阶段 | 分配 | Profile | 解释 |
|---|---|---|---|
| Stage A — structured coarse exploration | **360** | coarse (0.05) | 3 seeds × 120 = 360 |
| Stage B — bounded coarse refinement | **120** | coarse (0.05) | 12 parents × 10 perturbations = 120 |
| Stage C — medium finalist recheck | **24** | medium (0.02) | 12 parents × 2 perturbation sets |
| Stage D — fine finalist recheck | **6** | fine (0.01) | top-6 finalists |
| Stage E — high-resolution verification | **2** | fine (0.005) | final top-2 验证 / tie-break |
| **总计** | **512** | | |

### Stage A 子分配（每 seed 120 = 60 + 40 + 20）

| 子块 | 每 seed | 总 | 说明 |
|---|---|---|---|
| A1 staggered canonical family | 20 | 60 | 三枚弹在 r1 ~ best_pilot_r1 + 4s / 8s；delay near best_pilot ± small noise |
| A2 compensated release chain | 13 | 40 | release_time_i = best_pilot_r1 + sum(j<i, best_pilot_delay_j / 2) |
| A3 bounded directional diversity | 7 | 20 | heading ± 0.05 rad / speed ± 2 m/s 围绕 best_pilot |

## Checkpoint / Resume (P2)

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

## 验收 Gate (P2 必须全部满足)

- [ ] `src/q3_search.py` 实现：5 阶段 / 512 evals / 1200 s gate
- [ ] `build_formal_schedule(seeds=[2025,2026,2027])` 产出 **360 + 120 + 24 + 6 + 2 = 512** records
- [ ] 每 record 含 `schedule_index / stage / profile / candidate_source / candidate / expected_q3_evaluation_id`
- [ ] 每 Q3 evaluation 后原子写 `work/q3_formal/checkpoint.json`
- [ ] Resume 校验 7 字段（任一 mismatch → fail-closed, exit 2）
- [ ] 真实 Q3 evaluation 数 ≤ 512（hard cap）
- [ ] Real run wall-clock ≤ 1200 s（hard cap）
- [ ] Wall-clock gate hit → 原子写 checkpoint + 不自动延长 + 状态 `WALL_CLOCK_GATE_HIT`
- [ ] Evaluation budget exhausted → 原子写 checkpoint + 状态 `EVALUATION_BUDGET_EXHAUSTED`
- [ ] System error → 状态 `RUN_SYSTEM_ERROR` + 不冒充 0
- [ ] Stage A / B / C / D / E selection rules 正确实现
- [ ] Stage E 复评 top-2 finalists；tie-break on union duration
- [ ] Multi-seed：每 seed 独立 dispatch，结果聚合
- [ ] 输出 `outputs/q3/q3_formal_search_summary.json` 含全部 canonical 字段
- [ ] 单元测试 ≥ 20 cases，全部 PASS
- [ ] RESULT1.XLSX NOT GENERATED
- [ ] Q1 / Q2 / q3_three_bombs NOT modified
- [ ] v1 / v2 contract snapshots preserved
- [ ] original Pilot log / checkpoint preserved
- [ ] TASK_006-P3 / Q4 / Q5 NOT STARTED
- [ ] audit / hermes NOT STARTED

## 停止条件

本轮（`TASK_006-P2`）完成后立即停止。

不自动：
- 启动 Audit CC；
- 启动 Hermes；
- 开始 TASK_006-P3 / result1.xlsx / Q4 / Q5；
- Ready；
- merge。

由 MAIN / 用户显式决定 TASK_006-P3 立项、result1.xlsx 启动、P3 预算选定。
