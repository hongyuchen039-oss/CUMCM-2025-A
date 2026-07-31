# TASK_007-P2A Q4 THREE-DRONE EVALUATOR + CONTROLLED TESTS

> 唯一当前门是 **TASK_007-P2A Q4 THREE-DRONE EVALUATOR + CONTROLLED TESTS**:
> 在 v3 canonical 合同基础上，实现 Q4 三无人机单弹联合评估器 (`src/q4_three_drones.py`)
> 与完全受控的单元测试 (`tests/test_q4.py`)。本轮**仅**做实现 + 受控测试,
> real Q1 / Q2 / Q3 / Q4 evaluator 调用严格保持 0; 所有真实 evaluator 调用必须
> 通过 `single_bomb_evaluator=` 依赖注入被 stub 替换; 测试身份必须标记为
> `TEST_FIXTURE_ONLY`。
>
> **不**实现 Q4 search / pilot / candidate closure / result2.xlsx 写盘 /
> runtime calibration; **不**启动 Audit full rerun / Hermes / Ready / merge;
> **不**启动 TASK_007-P2B / P3 / P4 / P5 / TASK_008。

## P2A 阶段状态

| 字段 | 值 |
|---|---|
| P0/P1 FINAL ACCEPTANCE | **PASS** |
| P2A AUTHORIZATION | **GRANTED** (`p2a_authorized: true`) |
| canonical contract | `TASK_007-P0P1-v3.json` (`394cbd3557696594caa229be1018e999e69171597d0736823b6c6387c09cb62e`) |
| P2A contract | `work/task_contracts/TASK_007-P2A-v1.json` (`4c325ed9e45381a520250fd08e5d6eceb03e7658d3a3e7dcd5417239db6786fb`) |
| v1 / v2 / v3 | **UNMODIFIED** (hash 全部冻结) |
| Q4 evaluator implemented | **YES** (`src/q4_three_drones.py`) |
| Q4 controlled tests | **PASS** (`tests/test_q4.py`, 73 cases) |
| Q4 real evaluator calls | **0** |
| Q1 / Q2 / Q3 real calls | **0** (no foundation touched) |
| P2B / P3 / P4 / P5 / TASK_008 | **NOT STARTED** |
| result2.xlsx | **NOT GENERATED** |
| Ready | **NO** |
| Merge | **NO** |
| next gate | **MAIN P2A IMPLEMENTATION REVIEW** |

## 本轮范围 (P2A IMPLEMENT + CONTROLLED TESTS)

### 实现 — `src/q4_three_drones.py` (NEW)

- 模块常量: `DRONE_ORDER = ("FY1","FY2","FY3")` (固定顺序);
  `DRONE_INITIAL_POSITIONS = {"FY1":(17800,0,1800), "FY2":(12000,1400,1400), "FY3":(6000,-3000,700)}`;
  `CANDIDATE_SCHEMA_VERSION = 1`; `Q4_CONFIG_SCHEMA_VERSION = 1`;
  `EVALUATION_CALL_CONTRACT_VERSION = "TASK_007_Q4_TWO_STAGE_EXCEPTION_PROPAGATION_V3"`;
  `OBJECTIVE_IDENTITY = "measure(I_FY1 union I_FY2 union I_FY3)"`;
  `INTERVAL_EPSILON_S = 1e-12`; `RAW_HEADING_POLICY = "prevalidated_in_half_open_interval"`;
  `Q4_MODEL_CONTRACT_VERSION = 3`; `Q4_MODEL_CONTRACT_SHA256 = "394cbd35..."`;
  `TRUE_TARGET_GEOMETRY_ID` (模块加载时基于 canonical geometry dict 一次性计算);
  `MISSILE_ID = "M1"`; `MISSILE_INITIAL_POSITION = (20000,0,2000)`;
  `MISSILE_TRAJECTORY_IDENTITY = "M1_constant_velocity_300mps_to_origin"`;
  `CYLINDER_SAMPLING_ALGORITHM_ID = "src.q1_cylinder.generate_cylinder_samples.cell_center_v1"`;
  `Q4_VALID_STATUSES = ("invalid","zero_union","ok")`
- `@dataclass(frozen=True) class ThreeDroneCandidate`: **严格 12 字段**, 即
  `heading_rad_fy{1,2,3}`, `speed_mps_fy{1,2,3}`, `release_time_s_fy{1,2,3}`,
  `delay_s_fy{1,2,3}`。无任何附加字段。
- `@dataclass(frozen=True) class ThreeDroneEvaluation`: 字段 `candidate`, `valid`,
  `status` ∈ `{"invalid","zero_union","ok"}`, `reason`, `drone_evaluations` (tuple,
  prevalidation invalid 时为 `()`), `union_intervals`, `total_union_duration_s`,
  `sample_level`, `scan_step_s`, `elapsed_s`, `q4_evaluation_id` (prevalidation
  invalid 时严格 `""`, **不**得为 `"pending"` / `"placeholder"` / `None`),
  `attempted_single_bomb_calls`, `completed_single_bomb_calls`
- `class Q4EvaluationSystemError(RuntimeError)`: 显式 `__init__` 存储
  `failing_drone_id`, `attempted_single_bomb_calls`, `completed_single_bomb_calls`,
  `completed_drone_ids`, `completed_evaluations`, `original_exception_type`,
  `original_exception_message`。以 `raise ... from exc` 保留 `__cause__`
- 纯函数: `validate_three_drone_candidate(c)` (按 drone 单独 prevalidation, **无**
  跨 drone 规则, 调用 `q2_validate_strategy(strategy, u0=DRONE_INITIAL_POSITIONS[id])`),
  `iter_drone_strategies(c)` (FY1→FY2→FY3 固定顺序),
  `build_cylinder_sample_profile_identity_payload(sample_level)` (含
  `cylinder_sample_profile_schema_version=1`, `effective_profile_parameters`),
  `build_q4_config_identity_payload(*, sample_level, scan_step)` (含
  `q4_config_schema_version=1`, `objective_identity`,
  `evaluation_call_contract_version`; **不**含时间戳 / 主机名 / 日志路径,
  **不**含 `q4_config_sha256` 自身),
  `canonicalize_json_value(v)`, `canonical_json_bytes(payload)`,
  `compute_git_blob_identity(repo_root, execution_head_sha, path)` (subprocess
  调用 `git rev-parse <sha>:<path>` + `git cat-file blob <oid>`, raw bytes,
  **不**解码, **不**做换行转换), `compute_q4_evaluation_id(...)`
- 8-category identity payload (hash-binding for formal ID):
  1. candidate_identity (12 raw fields + `candidate_schema_version` + `drone_order` +
     `raw_heading_policy`); 2. per_drone_context (FY1/2/3 initial position);
  3. missile_and_target_context (missile id + position + speed +
     trajectory identity + fake target origin + true target geometry
     parameters + true_target_geometry_id); 4. numerical_profile
     (sample_level + scan_step_s + interval_touching_epsilon_s +
     cylinder_sample_profile_identity_payload + cylinder_sample_profile_sha256);
  5. code_identity (5 `GitBlobIdentity` for q1_baseline / q1_cylinder /
     q2_single_bomb / q3_three_bombs / q4_evaluator; `execution_head_sha` 是
     provenance only, **不**结果决定性); 6. runtime_config_identity
     (q4_config_schema_version + q4_config_identity_payload + q4_config_sha256
     + objective_identity + evaluation_call_contract_version);
  7. physical_constants (gravity_mps2=G + cloud_radius_m + cloud_sink_mps +
     cloud_duration_s + eps_ground_m=EPS_GROUND);
  8. contract_identity (q4_model_contract_version=3 + q4_model_contract_sha256)
- `evaluate_three_drone_strategy(c, *, sample_level="coarse", scan_step=0.05,
  single_bomb_evaluator=evaluate_single_bomb_strategy, code_identity_payload=None,
  config_identity_payload=None, contract_sha256=Q4_MODEL_CONTRACT_SHA256)` —
  两阶段: Stage A prevalidation (invalid 时 0 evaluator calls); Stage B 严格
  `for drone_id in DRONE_ORDER`: `attempted += 1`, call
  `single_bomb_evaluator(strategy, sample_level=..., scan_step=..., u0=u0)`;
  异常 → `raise Q4EvaluationSystemError(...) from exc`; 正常返回 →
  `completed += 1`, append `SingleBombEvaluation`。Stage C 聚合: 任一 Q2
  `(valid=False, status="invalid")` → `q4.valid=False, status="invalid"`,
  保留 3 个真实返回, union 空; 否则 `union_intervals(*ev.intervals,
  epsilon=INTERVAL_EPSILON_S)`, `total = total_union_duration(union)`,
  `status="ok" if total>0 else "zero_union"`, attach `q4_evaluation_id`
- **不**修改 `src/q1_baseline.py` / `src/q1_cylinder.py` /
  `src/q2_single_bomb.py` / `src/q3_three_bombs.py` 任何 byte
- **不**引入新依赖

### 测试 — `tests/test_q4.py` (NEW, stdlib `unittest` only)

8 个测试类, 73 个 cases, 全部 PASS:

| 测试类 | Cases | 覆盖 |
|---|---:|---|
| `TestCandidateContract` | 19 | exactly 12 fields; FY1/FY2/FY3 独立; heading 0 / `nextafter(2π,0)` 接受; `-1e-12` / `2π` / NaN / ±Inf 拒绝; speed [70,140] 边界; release / delay ≥ 0; 无跨 drone 规则; per-drone u0 prevalidation |
| `TestPrevalidationShortCircuit` | 4 | FY1 / FY2 / FY3 各一次非法 → `invalid`, `attempted=0`, `completed=0`, `drone_evaluations=()`, `q4_evaluation_id=""` (且 **不**为 `"pending"` / `None`) |
| `TestNormalPath` | 12 | FY1→FY2→FY3 严格顺序; u0 映射; `attempted=3 completed=3`; overlapping / disjoint / nested / touching / all-empty / non-empty 全部正确 union |
| `TestQ2StatusMapping` | 5 | `pruned_zero` / `zero_window` `valid=True` **不**导致 Q4 invalid; mix status legal union; 一个 invalid 传播 Q4 invalid 但保留 3 个真实返回; status ∈ `{invalid, zero_union, ok}` |
| `TestExceptionPropagation` | 5 | exception at call 1/2/3: `failing_drone_id`, `attempted=k`, `completed=k-1`, `__cause__` is original, 不返回 `ThreeDroneEvaluation`, 无 fake `SingleBombEvaluation` |
| `TestIdentity` | 18 | canonical dict insertion order 不影响 ID; tuple / list 归一; `-0.0 == 0.0`; NaN / Inf 拒绝; 缺 `q4_evaluator_code_sha256` 拒绝; 非 64-hex SHA 拒绝; 同样 context → 同样 ID; 扰动 12 candidate fields 任意一个 → ID 变化; FY2 u0 改变 → ID 变化; `sample_level` / `scan_step` 改变 → ID 变化; profile 改变 → ID 变化; 5 个 code blob SHA 任一改变 → ID 变化; config 改变 → ID 变化; physical constant 改变 → ID 变化; contract hash 改变 → ID 变化; **仅** `execution_head_sha` 改变 → ID 不变; raw heading 在 ID 中; 所有合成 SHA 标记 `TEST_FIXTURE_ONLY` |
| `TestGitBlobHelper` | 5 | temp git repo 双向 roundtrip; worktree 修改不改 blob SHA; nonexistent path raise `CalledProcessError` (fail-closed); invalid `execution_head_sha` raise `ValueError`; temp dir 自动清理, **不**落在 project repo 下 |
| `TestProductionEvaluatorNotInvoked` | 2 | 注入 recorder 时默认 evaluator 不被调用; module attribute 默认是 `evaluate_single_bomb_strategy` |

运行命令:
```bash
PYTHONDONTWRITEBYTECODE=1 python -B -m unittest tests.test_q4 -v
```
结果: `Ran 73 tests in ... — OK` (all green)。

### Reused surface (read-only, no byte change)

| Reused symbol | Source |
|---|---|
| `G`, `CLOUD_RADIUS`, `CLOUD_SINK`, `CLOUD_DURATION`, `MISSILE_SPEED`, `M0`, `O`, `Vec` | `src/q1_baseline.py:21-46` |
| `SAMPLE_GRADES` | `src/q1_cylinder.py:61-65` |
| `SingleBombStrategy`, `SingleBombEvaluation`, `evaluate_single_bomb_strategy`, `validate_strategy` | `src/q2_single_bomb.py` (signature **不**修改) |
| `EPS_GROUND = 1e-9` | `src/q2_single_bomb.py:68` |
| `INTERVAL_EPSILON_S`, `normalize_intervals`, `union_intervals`, `total_union_duration` | `src/q3_three_bombs.py` |

Q4 wrapper 严格以 keyword 参数传入 `u0=`:
`single_bomb_evaluator(strategy, sample_level=sample_level, scan_step=scan_step, u0=u0)`。

### `work/task_contracts/TASK_007-P2A-v1.json` (NEW)

- `contract_version = 1`; `status = "CANONICAL_P2A_IMPLEMENTATION_AND_TEST_CONTRACT"`
- `parent_contract_path = "work/task_contracts/TASK_007-P0P1-v3.json"`
- `parent_q4_model_contract_sha256 = "394cbd3557696594caa229be1018e999e69171597d0736823b6c6387c09cb62e"`
- `parent_q4_model_contract_version = 3`; `parent_contract_status = "CANONICAL_FINAL_P0P1_CONTRACT"`
- `contract_hash_algorithm = "SHA256_CANONICAL_JSON_EXCLUDING_SELF_FIELD_V1"`
- `contract_hash_excluded_fields = ["q4_p2a_contract_sha256"]`
- `q4_p2a_contract_sha256 = "4c325ed9e45381a520250fd08e5d6eceb03e7658d3a3e7dcd5417239db6786fb"`
  (计算并验证 = exclude-self-field algorithm)
- `scope = "implementation_and_controlled_unit_tests_only"`
- `evaluation_call_contract_version = "TASK_007_Q4_TWO_STAGE_EXCEPTION_PROPAGATION_V3"`
- `objective_identity = "measure(I_FY1 union I_FY2 union I_FY3)"`
- `interval_touching_epsilon_s = 1e-12`; `q4_config_schema_version = 1`;
  `candidate_schema_version = 1`; `drone_order = ["FY1","FY2","FY3"]`
- `real_evaluator_calls = {q1:0, q2:0, q3:0, q4:0, search:0, excel_save:0}`
- `default_production_evaluator_invocation_in_tests = "FORBIDDEN"`
- 所有 `do_not_*` flag 全部 `true` (search / pilot / benchmark / runtime
  calibration / result2.xlsx / q1 q2 q3 foundation modification / result1.xlsx
  modification / official template modification / gitignore / facts / model /
  v1 v2 v3 modification / amend / squash / force-push / audit / hermes /
  ready / merge / TASK_008 / TASK_007-P2B / P3 / P4 / P5 / install deps /
  CI / workflow / formal result / local convergence / global optimum /
  result2 generated / q4 searched / seeds frozen / budget frozen / pilot
  budget frozen / official answer / `git add .`)

### `work/task_context.json` (in-place update)

- `task_id = "TASK_007-P2A-Q4-EVALUATOR"`; `phase_id = "TASK_007-P2A"`;
  `round = "P2A_IMPLEMENT_AND_TEST"`; `current_action = "P2A_IMPLEMENT_AND_TEST"`;
  `next_gate = "MAIN_P2A_REVIEW"`; `expected_head = <p2a-commit-sha>`
- `allowed_modified_paths = ["src/q4_three_drones.py","tests/test_q4.py","NEXT_TASK.md"]`
- `cumulative_changed_files_in_pr14` 6 files:
  `.gitignore`, `MODEL.md`, `NEXT_TASK.md`, `problem/FACTS.md`,
  `src/q4_three_drones.py`, `tests/test_q4.py`
- `bounded_verification.real_evaluator_call_count.{q1,q2,q3,q4,search,excel_save}` 全部 0
- `bounded_verification.max_expensive_evaluations = 0`; `result2_generated = false`
- `allowed_untracked_paths` 包含 4 个中文命名项目根目录文件夹 (与 harness 一致)

### `work/q4_p2a/{test_report,call_accounting}.json` (post-tests-pass)

- `test_report.json`: 73 tests run, 0 failures / 0 errors / 0 skipped, per-class
  breakdown, runner line, v1 / v2 / v3 immutability VERIFIED
- `call_accounting.json`: `real_q4_evaluator_calls = 0`,
  `stubbed_single_bomb_evaluator_calls` (test 期间观察到), `evaluator_call_order
  = ["FY1","FY2","FY3"]`, notes 声明没有任何真实 `evaluate_single_bomb_strategy`
  被调用

### `work/q4_p2a/{code_identity,identity_only_record}.json` (post-commit)

- `code_identity.json`: `execution_head_sha = <p2a-commit-sha>`, 5 个 blob
  identities (q1_baseline / q1_cylinder / q2_single_bomb / q3_three_bombs /
  q4_evaluator) 由 `compute_git_blob_identity` 计算, schema
  `{path, git_blob_oid, blob_size, sha256}`
- `identity_only_record.json`: 基于合成 `ThreeDroneCandidate` (12 字段全部
  finite 且在 domain 内), 记录 `q4_evaluation_id`, `q4_config_sha256`,
  `q4_evaluator_code_sha256` (来自 code_identity.json), `objective_identity`,
  `evaluation_call_contract_version`, `interval_touching_epsilon_s`,
  `sample_level`, `scan_step`, `drone_order`, `candidate_schema_version`,
  `q4_config_schema_version`, `raw_heading_policy`。显式标记
  `identity_only = true`, `evaluation_performed = false`,
  `real_q4_evaluator_calls = 0`, `formal_result_claimed = false`。无 objective
  value, 无 `ThreeDroneEvaluation`, 无真实 evaluator 调用

### `work/pr_14_p2a_body.md` (PR #14 body after commit)

更新 PR #14 描述: P0/P1 FINAL ACCEPTED; P2A IMPLEMENTATION COMPLETE;
controlled tests PASS (73 cases); real Q1/Q2/Q3/Q4 evaluator calls = 0;
q4 code blob identity frozen; identity-only record generated; P2B /
P3 / P4 / P5 / TASK_008 NOT STARTED; result2.xlsx NOT GENERATED; Ready
NO; Merge NO; PR remains Draft; next gate MAIN P2A IMPLEMENTATION REVIEW

## 阶段状态

| 阶段 | 状态 |
|---|---|
| TASK_006-P3 (Q3 result1.xlsx) | **COMPLETE + MERGED** (PR #13 → main @ `2839151c9ef027c200f84ec342e17d43874ca254`) |
| TASK_007-P0/P1 (FINAL SEMANTIC AND HASH-SCOPE FIX) | **COMPLETE** (commit `f47f5d09f79fb21159a57d0e475924a90ee5ec67`) |
| TASK_007-P0/P1 (WORKTREE HYGIENE FINAL CLOSEOUT) | **COMPLETE** (commit `67645d74b1f4d1402645e0f792e9b5f77fdbba4b`) |
| TASK_007-P0/P1 (FINAL ACCEPTANCE) | **PASS** |
| TASK_007-P2A (Q4 evaluator + 单元测试) | **IMPLEMENTATION COMPLETE + TESTS PASSED** (本轮) |
| TASK_007-P2B (tiny bounded pilot + runtime calibration) | **NOT STARTED** |
| TASK_007-P3 (Q4 formal bounded search) | **NOT STARTED** |
| TASK_007-P4 (candidate closure) | **NOT STARTED** |
| TASK_007-P5 (result2.xlsx write + round-trip) | **NOT STARTED** |
| TASK_008 | **NOT STARTED** |

## 起点身份 (P2A 启动)

| 字段 | 值 |
|---|---|
| 起始 HEAD (main) | `2839151c9ef027c200f84ec342e17d43874ca254` (PR #13 mergeCommit) |
| branch | `task/TASK_007-q4-result2` |
| base_branch | `main` |
| base_sha | `2839151c9ef027c200f84ec342e17d43874ca254` |
| 上一轮 HYGIENE CLOSEOUT commit (P2A 起点 HEAD) | `67645d74b1f4d1402645e0f792e9b5f77fdbba4b` |
| 上一轮 FINAL SEMANTIC FIX commit | `f47f5d09f79fb21159a57d0e475924a90ee5ec67` |
| 上一轮 CONSOLIDATED FIX commit | `2f3a38a5af867569b23cc9bed958cf1a8d4b5b10` |
| 上一轮 FIX commit | `6f52c39c14b957d466f39248fcbfa8fae923a234` |
| 上上一轮 PLAN commit | `217985bd4f03a1e023d37e896c4035c1a58f515f` |
| 本轮 P2A FEAT commit | (本轮生成, 第六个普通 commit, 非 amend, 非 squash, 非 force) |
| task_id | `TASK_007-P2A-Q4-EVALUATOR` |
| phase_id | `TASK_007-P2A` |
| contract_version | 1 (P2A 自身 contract); v3 canonical P0/P1 仍指向
  `394cbd3557696594caa229be1018e999e69171597d0736823b6c6387c09cb62e` |
| pr_number | 14 |
| pr_state_target | open, draft=true, merged=false, mergeable=true |
| pr_commits_target | 6 (PLAN + FIX + CONSOLIDATED FIX + FINAL SEMANTIC FIX +
  HYGIENE CLOSEOUT + P2A FEAT) |
| current_action | `P2A_IMPLEMENT_AND_TEST` |
| next_gate | `MAIN_P2A_REVIEW` |
| worktree | `C:\Users\33560\Desktop\CUMCM_2025_A` |
| repository | `hongyuchen039-oss/CUMCM-2025-A` |

## 不可变 hash 复核 (本轮前后必须完全一致)

| 文件 | SHA-256 | Size |
|---|---|---|
| v1 (`work/task_contracts/TASK_007-P0P1-v1.json`) | `21fffb2653c43da371ffe0b17fbff25d8fd6bec9c4043f1d4045cc20b9db6e2e` | 14988 |
| v2 (`work/task_contracts/TASK_007-P0P1-v2.json`) | `e28d35901b9d39b8621f31bb12bdfeb778ebddcdfe5665098e7eb9f274c6bb1d` | 18470 |
| v3 file (`work/task_contracts/TASK_007-P0P1-v3.json`) | `9b4f824c67a42e164e454365e0c920622095871843625db2c01b96853cea59a4` | 30724 |
| v3 contract hash (`q4_model_contract_sha256`) | `394cbd3557696594caa229be1018e999e69171597d0736823b6c6387c09cb62e` | (32 bytes hex) |

任一变化 → **BLOCKED — CANONICAL CONTRACT MUTATED DURING P2A**。

P2A contract 自身 hash (exclude-self-field algorithm):
`4c325ed9e45381a520250fd08e5d6eceb03e7658d3a3e7dcd5417239db6786fb`

## 官方 result2.xlsx 模板 read-only 验证 (保持)

| 字段 | 值 |
|---|---|
| 官方 ZIP SHA-256 | `f9879c0d36b7bdccb99fb330a8032e62851ab1a1f0a1636c92440a1cdaec658e` (14884 bytes, 3 members) |
| result2.xlsx member size | 5272 bytes |
| result2.xlsx member SHA-256 | `91fbc42459aa4c98838b0a4dbe740ec5b970436c3f86d8a22dd7303f127cf106` |
| sheet | `Sheet1` (唯一) |
| header | row 1, A1:J1 (10 列) |
| 模板空白格式行 | rows 2-5 (4 行) |
| 实际写入区 | rows 2, 3, 4 (FY1 → row 2, FY2 → row 3, FY3 → row 4) |
| 保留空白格式行 | row 5 (官方模板预存, 不删除不重排不写入) |
| 附注 cell | B6 |
| workbook footprint | A1:J6 |
| FACTS.md §13.2 修正 | CORRECTED in FIX commit `6f52c39c14b957d466f39248fcbfa8fae923a234` |
| result2.xlsx generated | **NO** |

## 当前 result level

- P2A result level = **EXPERIMENTAL**
  - Q4 three-drone evaluator **实现完成**, **73 controlled tests PASS**
  - real Q4 evaluator calls = 0 (零真实 evaluator 调用)
  - **不**存在 formal Q4 evaluation
  - **不**存在 local convergence
  - **不**存在 global optimum
  - **不**是官方答案
- TASK_007-P2B / P3 / P4 / P5 NOT STARTED
- TASK_008 NOT STARTED
- seeds 数量 / 具体 seed 列表 / wall-clock / evaluation cap / search config /
  pilot self-budget **均 NOT FROZEN**
- Audit (full rerun) NOT STARTED
- Hermes NOT STARTED
- Ready = NO; Merge = NO
- NOT Q4 SEARCHED (Q4 evaluator 仅做 controlled unit tests, **不**做 search /
  pilot / benchmark / runtime calibration)
- NOT FORMAL_RESULT_VERIFIED

## result1.xlsx 状态 (保留不变)

| 字段 | 值 |
|---|---|
| result1.xlsx output SHA | `b938a90b96181be14990d5bd3395c2cff72e93035828542617571ddc1d754847` |
| result1_run_identity_sha256 | `82065aa5fe4d4e6036691a053b38732b9ff1f50497083e3306e262e82a4bfc65` |
| 状态 | GENERATED + ROUND-TRIP-VERIFIED (TASK_006-P3, NOT touched by TASK_007) |

## 任务编号 (固定)

| 编号 | 范围 |
|---|---|
| `TASK_006` | Q3 + result1.xlsx |
| `TASK_007-P0P1` | Q4 foundation preflight + contract freeze + CONTRACT CORRECTION + CONSOLIDATED AUDIT FIX + FINAL SEMANTIC AND HASH-SCOPE FIX + WORKTREE HYGIENE FINAL CLOSEOUT |
| `TASK_007-P2A` | Q4 evaluator + 单元测试 (real Q4 calls = 0) **(本轮)** |
| `TASK_007-P2B` | tiny bounded pilot + runtime calibration (pilot self-budget NOT FROZEN) |
| `TASK_007-P3` | Q4 formal bounded search (artifact root = work/q4_search/) |
| `TASK_007-P4` | candidate closure (artifact root = work/q4_candidate_closure/) |
| `TASK_007-P5` | fine reconstruction + result2.xlsx 写盘 + round-trip 验证 |
| `TASK_008` | Q5 + result3.xlsx |
| `TASK_009` | unified recomputation / sensitivity / robustness / figures |
| `TASK_010` | paper / consistency / final package |

## 本轮允许的 tracked 文件变更 (3 个)

| 文件 | 类型 |
|---|---|
| `src/q4_three_drones.py` | NEW (Q4 three-drone evaluator module) |
| `tests/test_q4.py` | NEW (Q4 controlled tests, 73 cases) |
| `NEXT_TASK.md` | 重写为本轮 TASK_007-P2A scope |

## 本轮允许的 untracked 文件 (work/)

| 文件 | 类型 |
|---|---|
| `work/task_context.json` | 顶层 task_id / phase_id / round / current_action / next_gate / expected_head / allowed_modified_paths / allowed_untracked_paths / bounded_verification 调整 |
| `work/task_contracts/TASK_007-P2A-v1.json` | NEW (P2A contract, contract_version=1) |
| `work/task_contracts/TASK_007-P0P1-v{1,2,3}.json` | 本轮**不修改** (immutable) |
| `work/q4_p2a/test_report.json` | NEW (post-tests-pass) |
| `work/q4_p2a/call_accounting.json` | NEW (post-tests-pass) |
| `work/q4_p2a/code_identity.json` | NEW (post-commit) |
| `work/q4_p2a/identity_only_record.json` | NEW (post-commit) |
| `work/pr_14_p2a_body.md` | NEW (PR #14 body) |

## 关闭条件 (本门)

- ✅ `src/q4_three_drones.py` import 无 error; 实现完整覆盖本 directive
- ✅ `PYTHONDONTWRITEBYTECODE=1 python -B -m unittest tests.test_q4 -v` → 73 tests
  PASS, 0 failures, 0 errors
- ✅ Q3 pure-function regression (`tests.test_q3.TestIntervalUnion` +
  `TestCandidateContract`) PASS — Q3 foundation 未被破坏
- ✅ v1 / v2 / v3 file SHA-256 / size 本轮前后**完全一致** (immutable)
- ✅ `python scripts/verify_task_context.py --context work/task_context.json` →
  `CONTEXT_VALID_AUTHORIZED_DIRTY`
- ✅ `work/task_contracts/TASK_007-P2A-v1.json` `contract_hash_excluded_fields =
  ["q4_p2a_contract_sha256"]`; `q4_p2a_contract_sha256` 自我一致 (删除自身字段
  重算 == 存储值)
- ✅ `work/q4_p2a/test_report.json` 记录 73 tests PASS, v1/v2/v3 SHA 全部一致
- ✅ `work/q4_p2a/call_accounting.json` 记录 `real_q4_evaluator_calls = 0`
- ✅ `NEXT_TASK.md` current gate = TASK_007-P2A Q4 THREE-DRONE EVALUATOR +
  CONTROLLED TESTS; next gate = MAIN P2A REVIEW
- ✅ `NEXT_TASK.md` 不写 P2B / P3 / P4 / P5 / TASK_008 / Audit / Hermes / Ready
  / Merge 启动
- ✅ 单次 commit "FEAT: implement TASK_007 P2A Q4 evaluator and controlled
  tests" (第六个普通 commit, 非 amend, 非 squash, 非 force)
- ✅ push 到 origin
- ✅ PR #14 仍为 Draft; 描述更新为 P2A closeout 状态
- ✅ PR #14 验证: state=OPEN, draft=true, merged=false, mergeable=true,
  base=2839151c..., head=新 P2A FEAT commit, commits=6, changedFiles=6
- ✅ `work/q4_p2a/code_identity.json` 记录 5 个 source file 的 Git blob SHA-256
  (基于 P2A commit SHA 作为 `execution_head_sha`); `q4_evaluator_code_sha256`
  与 `src/q4_three_drones.py` blob 完全一致
- ✅ `work/q4_p2a/identity_only_record.json` 记录 `q4_evaluation_id`,
  `q4_config_sha256`, `objective_identity`,
  `evaluation_call_contract_version`, `interval_touching_epsilon_s`,
  `sample_level`, `scan_step`, `drone_order`, `candidate_schema_version`,
  `q4_config_schema_version`, `raw_heading_policy`; 显式
  `identity_only = true, evaluation_performed = false,
  real_q4_evaluator_calls = 0, formal_result_claimed = false`

不自动 (本轮 boundary):

- ❌ 启动 Q4 search / pilot / benchmark / runtime calibration (TASK_007-P2B / P3)
- ❌ 启动 candidate closure (TASK_007-P4)
- ❌ 启动 result2.xlsx 写盘 (TASK_007-P5)
- ❌ 启动 Audit full rerun
- ❌ 启动 Hermes
- ❌ Mark Ready / merge
- ❌ 启动 TASK_008
- ❌ 冻结 seeds / wall-clock / evaluation cap / search config / pilot self-budget /
  任何 P2B / P3 数字
- ❌ 冒充 Q4 SEARCHED / Q4 EVALUATOR VALIDATED / RESULT2.XLSX GENERATED /
  FORMAL_RESULT_VERIFIED / local convergence / global optimum / 官方答案 /
  P2B 启动 / P3 启动 / P4 启动 / P5 启动 / TASK_008 启动 /
  seeds frozen / budget frozen / pilot budget frozen
- ❌ 修改 Q1 / Q2 / Q3 任何 source byte (foundation 冻结)
- ❌ 修改 v1 / v2 / v3 任何 byte (immutable)
- ❌ 修改 `.gitignore` 已有规则 / `MODEL.md` / `problem/FACTS.md` /
  官方模板 / `outputs/`
- ❌ Amend 任何之前的 commit (PLAN / FIX / CONSOLIDATED FIX / FINAL SEMANTIC /
  HYGIENE CLOSEOUT)
- ❌ Squash commits
- ❌ Force push
- ❌ 使用 `git add .` 或 `git add work/`
- ❌ 安装任何依赖 / 创建 CI / 修改 workflow

## 下一门 (待 MAIN 显式授权)

**MAIN P2A IMPLEMENTATION REVIEW** — MAIN 决定:
1. P2A 阶段 (Q4 evaluator + 单元测试) 是否最终接受;
2. 是否授权启动 TASK_007-P2B (tiny bounded pilot + runtime calibration,
   pilot self-budget 待 MAIN 基于 Q3 历史 + 12 维静态 + 保守上界 + 用户授权
   **首次真实 Q4 call 前** 冻结)。

PR #14 整个 TASK_007 期间保持 Draft, 不合并 (单 PR 规则)。

---

> 旧版 (TASK_007-P0/P1 WORKTREE HYGIENE FINAL CLOSEOUT + FINAL SEMANTIC AND
> HASH-SCOPE FIX) 状态见 git history, 本轮 (TASK_007-P2A) 仅重写 NEXT_TASK.md
> 反映 P2A scope, 不改 P0/P1 任何 commit / contract / MODEL.md / FACTS.md /
> .gitignore。
>
> **不**实现 Q4 search / pilot / candidate closure / result2.xlsx 写盘 /
> runtime calibration; **不**启动 Audit full rerun / Hermes / Ready / merge;
> **不**启动 TASK_007-P2B / P3 / P4 / P5 / TASK_008。
>
> 本轮最高状态: **P0/P1 FINAL ACCEPTED** / **P2A Q4 EVALUATOR IMPLEMENTED +
> 73 CONTROLLED TESTS PASSED** (real Q4 calls = 0) /
> P2B NOT STARTED / P3 NOT STARTED / P4 NOT STARTED / P5 NOT STARTED /
> TASK_008 NOT STARTED / SEEDS NOT FROZEN / BUDGET NOT FROZEN /
> PILOT BUDGET NOT FROZEN / Audit (full rerun) NOT STARTED / Hermes NOT STARTED.