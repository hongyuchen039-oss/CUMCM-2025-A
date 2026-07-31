# TASK_007-P2A IDENTITY AND FAIL-CLOSED HARDENING — COMPLETE

> 唯一当前门是 **MAIN P2A FINAL ACCEPTANCE AND P2B AUTHORIZATION DECISION**:
> 在 v3 canonical 合同 + P2A-v1 (immutable) 基础上, 完成 P2A 实现 + identity
> 与 fail-closed 加固 (B1/B2/B3/B4 + 五/七/八 全闭), 实现文件
> `src/q4_three_drones.py` 与完全受控的 105 个单元测试 (`tests/test_q4.py`)。
> 本轮**仅**做代码 + 受控测试, real Q1 / Q2 / Q3 / Q4 evaluator 调用严格
> 保持 0; 所有真实 evaluator 调用必须通过 `single_bomb_evaluator=` 依赖
> 注入被 stub 替换; 测试身份必须标记为 `TEST_FIXTURE_ONLY`。
>
> **不**实现 Q4 search / pilot / candidate closure / result2.xlsx 写盘 /
> runtime calibration; **不**启动 Audit full rerun / Hermes / Ready / merge;
> **不**启动 TASK_007-P2B / P3 / P4 / P5 / TASK_008。

## P2A 阶段状态 (含 hardening)

| 字段 | 值 |
|---|---|
| P0/P1 FINAL ACCEPTANCE | **PASS** (`p0p1_final_acceptance: PASS`) |
| P2A AUTHORIZATION | **GRANTED** (`p2a_authorized: true`) |
| canonical P0/P1 contract | `work/task_contracts/TASK_007-P0P1-v3.json` (`394cbd3557696594caa229be1018e999e69171597d0736823b6c6387c09cb62e`) |
| P2A-v1 contract (immutable) | `work/task_contracts/TASK_007-P2A-v1.json` (`4c325ed9e45381a520250fd08e5d6eceb03e7658d3a3e7dcd5417239db6786fb`) |
| P2A-v2 contract (active) | `work/task_contracts/TASK_007-P2A-v2.json` (`3048aeeddaf52a1173af08469e4464df5a4103e7c4af56f3635dd6d90df711db`) |
| v1 / v2 / v3 / P2A-v1 | **UNMODIFIED** (hash 全部冻结, immutable) |
| P2A implementation | **COMPLETE** (commit `d075eaf8c2f2a27dde27c93ab45bdcd2b5483640`) |
| P2A hardening | **COMPLETE** (commit `ba2ffcb8289d5f4efdb8b8f3efd03fd9d29e0bb6`) |
| B1 (identity context keyword-only + 0 stub before id) | **CLOSED** |
| B2 (strict GitBlobIdentity schema) | **CLOSED** |
| B3 (strict context validator / canonical-equal / forbidden keys) | **CLOSED** |
| B4 (Q2 return contract fail-closed; except Exception; KeyboardInterrupt/SystemExit propagate) | **CLOSED** |
| B 五/七 (strict numeric prevalidation; bool/str/None/Decimal/NaN/Inf rejected) | **CLOSED** |
| B 八 (Git subprocess failure wrapped as GitBlobIdentityError) | **CLOSED** |
| Q4 evaluator hardened | **YES** (`src/q4_three_drones.py`) |
| Q4 controlled tests | **PASS** (`tests/test_q4.py`, 105 / 105 cases) |
| Q3 pure-function regression | **PASS** (`tests.test_q3.TestIntervalUnion` + `TestCandidateContract`, 23 / 23) |
| Q4 real evaluator calls | **0** |
| Q1 / Q2 / Q3 real calls | **0** (foundation byte-untouched) |
| P2B / P3 / P4 / P5 / TASK_008 | **NOT STARTED** |
| result2.xlsx | **NOT GENERATED** |
| Ready | **NO** |
| Merge | **NO** |
| next gate | **MAIN P2A FINAL ACCEPTANCE AND P2B AUTHORIZATION DECISION** |

## P2A 实施 + 加固 范围 (TWO FEAT/FIX COMMITS)

### commit `d075eaf` — P2A implementation (FEAT)
- 模块常量: `DRONE_ORDER = ("FY1","FY2","FY3")`;
  `DRONE_INITIAL_POSITIONS = {"FY1":(17800,0,1800), "FY2":(12000,1400,1400), "FY3":(6000,-3000,700)}`;
  `CANDIDATE_SCHEMA_VERSION = 1`; `Q4_CONFIG_SCHEMA_VERSION = 1`;
  `EVALUATION_CALL_CONTRACT_VERSION = "TASK_007_Q4_TWO_STAGE_EXCEPTION_PROPAGATION_V3"`;
  `OBJECTIVE_IDENTITY = "measure(I_FY1 union I_FY2 union I_FY3)"`;
  `INTERVAL_EPSILON_S = 1e-12`; `RAW_HEADING_POLICY = "prevalidated_in_half_open_interval"`;
  `Q4_MODEL_CONTRACT_VERSION = 3`;
  `Q4_MODEL_CONTRACT_SHA256 = "394cbd3557696594caa229be1018e999e69171597d0736823b6c6387c09cb62e"`;
  `TRUE_TARGET_GEOMETRY_ID` (模块加载时一次性计算);
  `MISSILE_ID = "M1"`; `MISSILE_INITIAL_POSITION = (20000,0,2000)`;
  `MISSILE_TRAJECTORY_IDENTITY = "straight_line_to_fake_target"`;
  `CYLINDER_SAMPLING_ALGORITHM_ID = "src.q1_cylinder.generate_cylinder_samples.cell_center_v1"`;
  `Q4_VALID_STATUSES = ("invalid","zero_union","ok")`;
  `Q2_VALID_STATUSES = ("invalid","pruned_zero","zero_window","ok")`;
  `REQUIRED_CODE_IDENTITY_KEYS = ("q1_baseline","q1_cylinder","q2_single_bomb","q3_three_bombs","q4_evaluator")`;
  `REQUIRED_CODE_IDENTITY_PATHS` 精确路径映射.
- `@dataclass(frozen=True) class ThreeDroneCandidate`: **严格 12 字段** —
  `heading_rad_fy{1,2,3}`, `speed_mps_fy{1,2,3}`, `release_time_s_fy{1,2,3}`,
  `delay_s_fy{1,2,3}`. 无任何附加字段, 跨无人机之间 heading / speed /
  release / delay 完全独立.
- `@dataclass(frozen=True) class ThreeDroneEvaluation`: 字段 `candidate`,
  `valid`, `status ∈ {"invalid","zero_union","ok"}`, `reason`,
  `drone_evaluations` (tuple, prevalidation invalid 时为 `()`),
  `union_intervals`, `total_union_duration_s`, `sample_level`, `scan_step_s`,
  `elapsed_s`, `q4_evaluation_id` (prevalidation invalid 时严格 `""`, **不**
  得为 `"pending"` / `"placeholder"` / `None`; 正常路径必须是 lowercase
  64 hex SHA-256), `attempted_single_bomb_calls`, `completed_single_bomb_calls`.
- `@dataclass(frozen=True) class GitBlobIdentity`: `path`, `execution_head_sha`,
  `git_blob_oid`, `blob_size`, `sha256` (B2 strict schema).
- `@dataclass(frozen=True) class Q4EvaluationIdentityContext`: **8 field
  frozen dataclass** — `candidate_schema_version`, `code_identity` (Mapping[str,
  GitBlobIdentity]), `q4_config_identity_payload`, `cylinder_sample_profile_identity_payload`,
  `missile_and_target_context`, `physical_constants`, `contract_version`,
  `contract_sha256`.
- `class Q4EvaluationSystemError(RuntimeError)`: 显式 `__init__` 存储
  `failing_drone_id`, `attempted_single_bomb_calls`,
  `completed_single_bomb_calls`, `completed_drone_ids`,
  `completed_evaluations`, `original_exception_type`,
  `original_exception_message`. 以 `raise ... from exc` 保留 `__cause__`.
- `class Q2ReturnContractError(RuntimeError)`: Q2 evaluator 返回 contract
  不被满足时隔离 raise, 在 `evaluate_three_drone_strategy` 中被包装为
  `Q4EvaluationSystemError(..., original_exception_type="Q2ReturnContractError")`.
- `class GitBlobIdentityError(RuntimeError)`: Git subprocess 失败 (`rev-parse`
  或 `cat-file blob`) 时包装 `CalledProcessError`, 含 `execution_head_sha`,
  `path`, `stderr`, `original_exception_type` 上下文.
- 纯函数: `validate_three_drone_candidate(c)` (按 drone 单独 prevalidation,
  无跨 drone 规则, 调用 `q2_validate_strategy(strategy, u0=...)`),
  `iter_drone_strategies(c)` (FY1→FY2→FY3 固定顺序),
  `build_cylinder_sample_profile_identity_payload(sample_level)` (含
  `cylinder_sample_profile_schema_version=1`, `effective_profile_parameters`),
  `build_q4_config_identity_payload(*, sample_level, scan_step)` (含
  `q4_config_schema_version=1`, `objective_identity`,
  `evaluation_call_contract_version`; **不**含时间戳 / 主机名 / 日志路径 /
  working_directory / elapsed / generated_at, **不**含 `q4_config_sha256` 自身),
  `canonicalize_json_value(v)` (recursive: str/bool/None/int 通过; float 必须
  finite, `-0.0 → 0.0`; tuple/list → list; dict → str-keyed dict; set →
  TypeError), `canonical_json_bytes(payload)` (UTF-8, sort_keys, no whitespace,
  no NaN/Inf), `compute_cylinder_sample_profile_sha256`,
  `compute_q4_config_sha256`, `compute_git_blob_identity(repo_root,
  execution_head_sha, path)` (subprocess `git rev-parse <sha>:<path>` + `git
  cat-file blob <oid>`, raw bytes, **不**解码, **不**做换行转换; bad input →
  `ValueError`; `CalledProcessError` → `GitBlobIdentityError`),
  `compute_q4_evaluation_id(...)`, `build_q4_evaluation_identity_payload(...)`,
  `build_q4_evaluation_identity_context(*, code_identity, sample_level, scan_step)`,
  `_is_real_finite_number(v)` (strict finite check; rejects `bool` 在 `int`
  之前, 拒绝 `str`/`None`/`Decimal`/`NaN`/`Inf`),
  `_is_strictly_real_finite_number(v)` (= `_is_real_finite_number`),
  `_validate_and_reduce_code_identity(code_identity)` (B2 严格 schema
  validator: 5 必填 key, 路径精确, 5 `execution_head_sha` 一致, 严格
  flat output schema `[{path, git_blob_oid, blob_size, sha256}]`),
  `_validate_canonical_equal(actual, expected, *, label)` (B3 严格
  canonical-equal: field set 完全一致, 无 forbidden non-result keys),
  `_build_expected_missile_and_target_context()`,
  `_build_expected_physical_constants()`,
  `_validate_normal_identity_context(identity_context, *, sample_level, scan_step)`
  (B3 strict context validator — 任一不一致立即 `ValueError`, 0 stub calls 之前),
  `_validate_q2_return_contract(ev, *, drone_id)` (B4 post-call contract 验证),
  `_is_40_hex(s)`, `_is_64_hex_lower(s)`.
- 8-category identity payload (hash-binding for formal ID):
  1. `candidate_identity` (12 raw fields + `candidate_schema_version=1` +
     `drone_order=["FY1","FY2","FY3"]` + `raw_heading_policy`); 2.
     `per_drone_context` (FY1/2/3 initial position); 3.
     `missile_and_target_context` (missile id + position + speed +
     trajectory identity + fake target origin + true target geometry
     parameters + true_target_geometry_id); 4. `numerical_profile`
     (sample_level + scan_step_s + interval_touching_epsilon_s +
     cylinder_sample_profile_identity_payload + cylinder_sample_profile_sha256);
     5. `code_identity` (5 `GitBlobIdentity` for q1_baseline / q1_cylinder /
     q2_single_bomb / q3_three_bombs / q4_evaluator; **strict output schema**:
     `{path, git_blob_oid, blob_size, sha256}` only; `execution_head_sha`
     是 provenance only, **不**结果决定性); 6. `runtime_config_identity`
     (q4_config_schema_version + q4_config_identity_payload + q4_config_sha256
     + objective_identity + evaluation_call_contract_version);
     7. `physical_constants` (gravity_mps2=G + cloud_radius_m + cloud_sink_mps
     + cloud_duration_s + eps_ground_m=EPS_GROUND);
     8. `contract_identity` (q4_model_contract_version=3 +
     q4_model_contract_sha256=`394cbd35...c09cb62e`).

### 公开 evaluator API (当前真实签名)

```python
def evaluate_three_drone_strategy(
    candidate: ThreeDroneCandidate,
    *,
    sample_level: str = "coarse",
    scan_step: float = 0.05,
    identity_context: Q4EvaluationIdentityContext,                # keyword-only REQUIRED
    single_bomb_evaluator: Callable[..., SingleBombEvaluation] = (
        evaluate_single_bomb_strategy                             # production default
    ),
) -> ThreeDroneEvaluation:
```

**`identity_context` keyword-only 必填**, 0 stub calls 之前完整校验
(B1/B2/B3). `code_identity_payload` / `config_identity_payload` /
`contract_sha256` 等旧 kwargs **已删除**.

显式保证:

- **prevalidation invalid** 唯一允许 `q4_evaluation_id=""` (空字符串, 不得为
  `"pending"` / `"placeholder"` / `None`), 0 evaluator calls.
- **prevalidation valid** → 0 stub calls 之前生成 `q4_evaluation_id`.
- **ok / zero_union / Q2-normal-invalid** 三种正常路径均必须输出 lowercase
  64 hex `q4_evaluation_id`.
- **Q2 return contract** (`isinstance(ev, SingleBombEvaluation)`, `status ∈
  {invalid, pruned_zero, zero_window, ok}`, `valid` 与 `status` 一致) 任一不
  满足 → fail closed, raise `Q4EvaluationSystemError` with
  `original_exception_type="Q2ReturnContractError"`, `raise ... from
  contract_error`.
- **Exception path** (注入 evaluator 抛 `Exception`) → fail closed, raise
  `Q4EvaluationSystemError(...) from exc` 保留 `__cause__`. **绝不**返回
  `ThreeDroneEvaluation`.
- **`KeyboardInterrupt` / `SystemExit` / `GeneratorExit`** 原样传播, 不包装.
- **`scan_step`** 必须 strict finite real number (`_is_strictly_real_finite_number`),
  必须 > 0, 拒绝 `bool`.
- **`sample_level`** 必须 ∈ `SAMPLE_GRADES`.
- **candidate 12 字段** strict finite, `heading_rad ∈ [0, 2π)`, `speed_mps ∈
  [70, 140]`, `release_time_s ≥ 0`, `delay_s ≥ 0`; 不跨 drone 约束.

### `commit ba2ffcb` — P2A hardening (FIX) 增量
- 新增 `Q4EvaluationIdentityContext` (frozen dataclass, 8 fields) +
  `build_q4_evaluation_identity_context` 单 builder.
- 新增 `Q2ReturnContractError` + `_validate_q2_return_contract` (B4).
- 新增 `GitBlobIdentityError` (含 execution_head_sha/path/stderr/
  original_exception_type 上下文).
- 新增 `_is_real_finite_number` (strict finite, 拒绝 `bool`/`str`/`None`/
  `Decimal`/`NaN`/`Inf`) + `_is_strictly_real_finite_number`.
- 新增 `_validate_and_reduce_code_identity` (B2 严格 schema validator:
  5 必填 key + 路径精确 + 5 `execution_head_sha` 一致 + 严格 flat output
  `{path, git_blob_oid, blob_size, sha256}`).
- 新增 `_validate_canonical_equal` + `_build_expected_missile_and_target_context`
  + `_build_expected_physical_constants` + `_validate_normal_identity_context`
  (B3 strict context validator — 任一不一致立即 `ValueError`, 0 stub calls 之前).
- `evaluate_three_drone_strategy` signature: `identity_context` 是 keyword-only
  必填, 删除 `code_identity_payload=None` / `config_identity_payload=None` /
  `contract_sha256` 默认 kwargs.
- Stage B0: 完整 `_validate_normal_identity_context` 在 0 stub calls 之前.
- Stage B1: 在 0 stub calls 之前生成 `q4_evaluation_id` (`compute_q4_evaluation_id`).
- Stage C: `try/except Exception` (不 `BaseException`); `KeyboardInterrupt` /
  `SystemExit` / `GeneratorExit` 原样传播.
- Stage C 后: 每次 `single_bomb_evaluator` 正常返回 → `_validate_q2_return_contract`;
  illegal → raise `Q4EvaluationSystemError(... original_exception_type="Q2ReturnContractError") from contract_error`.
- Stage D (Q2 normal invalid): `q4_evaluation_id` 仍为 lowercase 64 hex (B1).
- Stage E (ok / zero_union): `q4_evaluation_id` 仍为 lowercase 64 hex (B1).
- 不修改任何 Q1/Q2/Q3 source byte; 不修改任何 v1/v2/v3/P2A-v1 合同 byte.

## Q4 代码 blob identity (在 commit `ba2ffcb` 处重新冻结)

| Path | git_blob_oid | size | SHA-256 |
|---|---|---:|---|
| `src/q1_baseline.py` | `c26688a07639299aafc6222f033a67f2b789e93d` | 21392 | `d2f98172185622eff22c405a811372da67c62284489b01890de8e068d45f89af` |
| `src/q1_cylinder.py` | `9e9427278f61f77df47c418658bdd798ce13ce85` | 52725 | `915f56ea5a32b6b128c97cea8b80dfec3d4051427280ee4fe5d4e57466d86d59` |
| `src/q2_single_bomb.py` | `378ad6a70de6ed1696961896e9527bcb9c24e375` | 48157 | `81488776f6d1a06e225b3d21acd5677c59ccf41eaeda9e4cbf8dbe09d5d45464` |
| `src/q3_three_bombs.py` | `474e1254c6ffdef63172f483d9c2d1113e9f347d` | 80037 | `1e19fc50ba7fabe5d06e3ddc5664d64b3d338616fd1c5a55a4d31ea56c9a88ee` |
| `src/q4_three_drones.py` | `9c0c51d127d0f3b6a8fd3067d38898dd6a9bcbb8` | 49736 | `84a8ca1e7884674fdbae7777c2603b2e3311c5ad89d8f2dd3036847b2e6782a5` |

完整 64 位 SHA-256 (以 `work/q4_p2a/code_identity.json` 为权威 source of
truth). `q4_evaluator_code_sha256` =
`84a8ca1e7884674fdbae7777c2603b2e3311c5ad89d8f2dd3036847b2e6782a5`.

**新 identity-only `q4_evaluation_id`**:
`fc524533bc466820946f35074b32116f95d8ef58a2eeffd332c43427930d3be7`
(基于 hardening commit 的 q4_evaluator blob, 合成 candidate, **不**对应任何
真实 evaluator 调用).

**旧 P2A-v1 `q4_evaluation_id`** `77110c494d45f2df...` **已 superseded**,
不得再使用.

## 测试覆盖 (105 / 105 PASS)

9 个测试类, 105 个 cases, 全部 PASS:

| 测试类 | Cases | 覆盖 |
|---|---:|---|
| `TestCandidateContract` | 24 | exactly 12 fields; FY1/FY2/FY3 独立; heading 0 / `nextafter(2π,0)` 接受; `-1e-12` / `2π` / NaN / ±Inf 拒绝; speed [70,140] 边界; release / delay ≥ 0; 无跨 drone 规则; per-drone u0 prevalidation; **string / None / bool candidate fields rejected as invalid (no TypeError)** |
| `TestPrevalidationShortCircuit` | 4 | FY1 / FY2 / FY3 各一次非法 → `invalid`, `attempted=0`, `completed=0`, `drone_evaluations=()`, `q4_evaluation_id=""` (且 **不**为 `"pending"` / `None`) |
| `TestNormalPath` | 12 | FY1→FY2→FY3 严格顺序; u0 映射; `attempted=3 completed=3`; overlapping / disjoint / nested / touching / all-empty / non-empty 全部正确 union; `sample_level` / `scan_step` 非法在 prevalidation 前 raise `ValueError` |
| `TestQ2StatusMapping` | 5 | `pruned_zero` / `zero_window` `valid=True` **不**导致 Q4 invalid; mix status legal union; 一个 invalid 传播 Q4 invalid 但保留 3 个真实返回; status ∈ `{invalid, zero_union, ok}` |
| `TestExceptionPropagation` | 10 | exception at call 1/2/3: `failing_drone_id`, `attempted=k`, `completed=k-1`, `__cause__` is original, 不返回 `ThreeDroneEvaluation`, **KeyboardInterrupt / SystemExit 原样传播**, Q2ReturnContractError 路径 (non-SingleBombEvaluation / unknown status / valid-true-status-invalid / valid-false-status-ok) fail closed |
| `TestIdentity` | 21 | canonical dict insertion order 不影响 ID; tuple / list 归一; **真实 `-0.0` vs `0.0` canonical equal**; NaN / Inf 拒绝; 缺 `q4_evaluator_code_sha256` 拒绝; 非 64-hex SHA 拒绝; 同样 context → 同样 ID; 扰动 12 candidate fields 任意一个 → ID 变化; FY2 u0 改变 → ID 变化; `sample_level` / `scan_step` 改变 → ID 变化; profile 改变 → ID 变化; 5 个 code blob SHA 任一改变 → ID 变化; config 改变 → ID 变化; physical constant 改变 → ID 变化; contract hash 改变 → ID 拒绝; **仅** `execution_head_sha` 改变 → ID 不变 (provenance only); raw heading 在 ID 中; **ok / zero_union / Q2-normal-invalid 三个路径 ID 均是 64 hex lowercase**; 所有合成 SHA 标记 `TEST_FIXTURE_ONLY` |
| `TestIdentityContextHardening` | 21 | `identity_context` keyword-only 必填 (TypeError); missing identity_context 不触发任何 stub call; **invalid identity_context 0 stub calls**; B2 GitBlobIdentity missing/extra key / wrong path / wrong blob OID / wrong blob size / 5 execution_head_sha 不一致; **modify path / blob_oid / blob_size / sha256 任一 → ID 变化**; modify 仅 execution_head_sha → ID 不变 (provenance only); B3 config extra timestamp / missing field / sample_level mismatch / scan_step mismatch / profile side_theta mismatch 全部拒绝 |
| `TestGitBlobHelper` | 5 | temp git repo 双向 roundtrip; worktree 修改不改 blob SHA; nonexistent path raise **`GitBlobIdentityError`** (含 execution_head_sha/path/stderr/original); invalid `execution_head_sha` raise `ValueError`; temp dir 自动清理, **不**落在 project repo 下 |
| `TestProductionEvaluatorNotInvoked` | 3 | 注入 recorder 时默认 evaluator 不被调用; module attribute 默认是 `evaluate_single_bomb_strategy`; **`identity_context` 必填 keyword-only** (inspect.signature 验证) |

运行命令:
```bash
PYTHONDONTWRITEBYTECODE=1 python -B -m unittest tests.test_q4 -v
```
结果: `Ran 105 tests in ... — OK` (all green).

Q3 回归:
```bash
python -B -m unittest tests.test_q3.TestIntervalUnion tests.test_q3.TestCandidateContract
```
结果: `Ran 23 tests in ... — OK` (Q3 foundation intact).

## Reused surface (read-only, no byte change)

| Reused symbol | Source |
|---|---|
| `G`, `CLOUD_RADIUS`, `CLOUD_SINK`, `CLOUD_DURATION`, `MISSILE_SPEED`, `M0`, `O`, `Vec` | `src/q1_baseline.py` |
| `SAMPLE_GRADES` | `src/q1_cylinder.py` |
| `SingleBombStrategy`, `SingleBombEvaluation`, `evaluate_single_bomb_strategy`, `validate_strategy`, `EPS_GROUND` | `src/q2_single_bomb.py` (signature **不**修改) |
| `INTERVAL_EPSILON_S`, `normalize_intervals`, `union_intervals`, `total_union_duration` | `src/q3_three_bombs.py` |

Q4 wrapper 严格以 keyword 参数传入 `u0=`:
`single_bomb_evaluator(strategy, sample_level=sample_level, scan_step=scan_step, u0=u0)`.

## `work/task_contracts/TASK_007-P2A-v1.json` (immutable)

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
- **本轮 (P2A hardening) 不得修改本文件**. frozen hash
  `4c325ed9...6786fb` 即 immutable provenance reference.

## `work/task_contracts/TASK_007-P2A-v2.json` (NEW, active)

- `contract_version = 2`; `status = "CANONICAL_P2A_IDENTITY_AND_FAIL_CLOSED_HARDENED"`
- `supersedes = "work/task_contracts/TASK_007-P2A-v1.json"`
- `superseded_contract_sha256 = "4c325ed9e45381a520250fd08e5d6eceb03e7658d3a3e7dcd5417239db6786fb"`
- `superseded_status = "CANONICAL_P2A_IMPLEMENTATION_AND_TEST_CONTRACT"`
- `findings_closed = ["B1", "B2", "B3", "B4"]`
- `q4_p2a_contract_sha256 = "3048aeeddaf52a1173af08469e4464df5a4103e7c4af56f3635dd6d90df711db"`
- `next_gate = "MAIN_P2A_MICRO_DELTA_REVIEW"`
- 继承 v1 的 `parent_q4_model_contract_sha256` /
  `evaluation_call_contract_version` / `objective_identity` /
  `interval_touching_epsilon_s` / `q4_config_schema_version` /
  `candidate_schema_version` / `drone_order` / `drone_initial_positions`.
- 新增字段: `identity_context_required_fields` (8), `identity_context_forbids`
  (`timestamp, hostname, log_path, working_directory, elapsed, generated_at`),
  `code_identity_required_keys` (5), `code_identity_required_paths` (5), strict
  output schema (`q4_evaluation_id_format = "lowercase 64 hex SHA-256 of
  canonical JSON of 8-category identity payload"`).

## `work/task_context.json` (in-place update)

- `task_id = "TASK_007-P2A-Q4-EVALUATOR"`; `phase_id = "TASK_007-P2A"`;
  `round = "P2A_IDENTITY_AND_FAIL_CLOSED_HARDENING"`;
  `current_action = "P2A_IDENTITY_AND_FAIL_CLOSED_HARDENING"`;
  `next_gate = "MAIN_P2A_MICRO_DELTA_REVIEW"`;
  `expected_head = "ba2ffcb8289d5f4efdb8b8f3efd03fd9d29e0bb6"`;
  `p2b_started = false`; `result2_generated = false`;
  `findings_closed_p2a = ["B1","B2","B3","B4"]`.
- `allowed_modified_paths = ["src/q4_three_drones.py","tests/test_q4.py"]`
  (本轮 hardening 不修改 NEXT_TASK.md 之外的 tracked file).
- `cumulative_changed_files_in_pr14` 仍严格 6 files:
  `.gitignore`, `MODEL.md`, `NEXT_TASK.md`, `problem/FACTS.md`,
  `src/q4_three_drones.py`, `tests/test_q4.py`.
- `bounded_verification.real_evaluator_call_count.{q1,q2,q3,q4,search,excel_save}`
  全部 0; `bounded_verification.max_expensive_evaluations = 0`;
  `bounded_verification.real_q4_evaluator_calls = 0`;
  `bounded_verification.result2_generated = false`.
- `allowed_untracked_paths` 包含 4 个中文命名项目根目录文件夹 (与 harness 一致).
- Harness: `python scripts/verify_task_context.py --context work/task_context.json` →
  `CONTEXT_VALID_AUTHORIZED_DIRTY`.

## `work/q4_p2a/{test_report,call_accounting}.json` (post-tests-pass)

- `test_report.json`: `tests_run: 105`, `failures: 0`, `errors: 0`,
  `skipped: 0`, per-class breakdown (TestCandidateContract 24, …,
  TestProductionEvaluatorNotInvoked 3), runner line, v1 / v2 / v3 /
  P2A-v1 immutability VERIFIED, `p2a_v2_q4_p2a_contract_sha256` =
  `3048aeeddaf52a1173af08469e4464df5a4103e7c4af56f3635dd6d90df711db`.
- `call_accounting.json`: `real_q4_evaluator_calls = 0`,
  `real_q1_evaluator_calls = 0`, `real_q2_evaluator_calls = 0`,
  `real_q3_evaluator_calls = 0`, `real_search_calls = 0`,
  `real_excel_save_calls = 0`, `evaluator_call_order = ["FY1","FY2","FY3"]`,
  notes 声明没有任何真实 `evaluate_single_bomb_strategy` 被调用.

## `work/q4_p2a/{code_identity,identity_only_record}.json` (post-commit)

- `code_identity.json`: `execution_head_sha = "ba2ffcb8289d5f4efdb8b8f3efd03fd9d29e0bb6"`,
  5 个 blob identities (q1_baseline / q1_cylinder / q2_single_bomb /
  q3_three_bombs / q4_evaluator) 由 `compute_git_blob_identity` 在 commit
  `ba2ffcb` 处计算, schema `{key, path, git_blob_oid, blob_size, sha256,
  execution_head_sha}`. **完整 64 位 SHA-256** 写入, **不**省略.
- `identity_only_record.json`: 基于合成 `ThreeDroneCandidate` (12 字段全部
  finite 且在 domain 内), 记录 `q4_evaluation_id =
  fc524533bc466820946f35074b32116f95d8ef58a2eeffd332c43427930d3be7`,
  `q4_config_sha256 = 6c85accb6536b9867d1a1f83df2d9d08b34f483c7194b3cc859a3b4cd592432f`,
  `q4_evaluator_code_sha256` (来自 code_identity.json, 完整 64 位),
  `objective_identity`, `evaluation_call_contract_version`,
  `interval_touching_epsilon_s`, `sample_level`, `scan_step_s`, `drone_order`,
  `candidate_schema_version`, `q4_config_schema_version`,
  `raw_heading_policy`, `contract_version=3`, `contract_sha256=
  394cbd3557696594caa229be1018e999e69171597d0736823b6c6387c09cb62e`,
  `commit_sha`, `commit_short`, `p2a_implementation_commit`,
  `p2a_hardening_commit`, `p2a_v1_superseded_sha256`, `p2a_v2_sha256`.
  显式标记 `identity_only = true`, `evaluation_performed = false`,
  `real_q4_evaluator_calls = 0`, `formal_result_claimed = false`. 无
  objective value, 无 `ThreeDroneEvaluation`, 无真实 evaluator 调用.

## `work/pr_14_p2a_body.md` (PR #14 body, hardened)

P2A TRACKED STATE SYNC COMPLETE; B1/B2/B3/B4 CLOSED; P2A FINAL ACCEPTANCE
PENDING MAIN; P2B NOT AUTHORIZED; real Q1/Q2/Q3/Q4 evaluator calls = 0;
search calls = 0; excel save calls = 0; result2.xlsx generated = NO; Ready
NO; Merge NO; next gate = MAIN P2A FINAL ACCEPTANCE AND P2B AUTHORIZATION
DECISION.

## 阶段状态

| 阶段 | 状态 |
|---|---|
| TASK_006-P3 (Q3 result1.xlsx) | **COMPLETE + MERGED** (PR #13 → main @ `2839151c9ef027c200f84ec342e17d43874ca254`) |
| TASK_007-P0/P1 (FINAL SEMANTIC AND HASH-SCOPE FIX) | **COMPLETE** (commit `f47f5d09f79fb21159a57d0e475924a90ee5ec67`) |
| TASK_007-P0/P1 (WORKTREE HYGIENE FINAL CLOSEOUT) | **COMPLETE** (commit `67645d74b1f4d1402645e0f792e9b5f77fdbba4b`) |
| TASK_007-P0/P1 (FINAL ACCEPTANCE) | **PASS** |
| TASK_007-P2A implementation | **COMPLETE** (commit `d075eaf8c2f2a27dde27c93ab45bdcd2b5483640`) |
| TASK_007-P2A hardening (B1/B2/B3/B4) | **COMPLETE** (commit `ba2ffcb8289d5f4efdb8b8f3efd03fd9d29e0bb6`) |
| TASK_007-P2B (tiny bounded pilot + runtime calibration) | **NOT STARTED / NOT AUTHORIZED** |
| TASK_007-P3 (Q4 formal bounded search) | **NOT STARTED** |
| TASK_007-P4 (candidate closure) | **NOT STARTED** |
| TASK_007-P5 (result2.xlsx write + round-trip) | **NOT STARTED** |
| TASK_008 | **NOT STARTED** |

## 起点身份 (P2A hardening 启动)

| 字段 | 值 |
|---|---|
| 起始 HEAD (main) | `2839151c9ef027c200f84ec342e17d43874ca254` (PR #13 mergeCommit) |
| branch | `task/TASK_007-q4-result2` |
| base_branch | `main` |
| base_sha | `2839151c9ef027c200f84ec342e17d43874ca254` |
| P0/P1 FINAL HYGIENE CLOSEOUT commit | `67645d74b1f4d1402645e0f792e9b5f77fdbba4b` |
| P2A implementation commit | `d075eaf8c2f2a27dde27c93ab45bdcd2b5483640` |
| P2A hardening commit | `ba2ffcb8289d5f4efdb8b8f3efd03fd9d29e0bb6` |
| task_id | `TASK_007-P2A-Q4-EVALUATOR` |
| phase_id | `TASK_007-P2A` |
| contract_version (P2A self) | 2 (v1 immutable `4c325ed9...6786fb`; v2 active
  `3048aeed...df711db`); v3 canonical P0/P1 仍指向
  `394cbd3557696594caa229be1018e999e69171597d0736823b6c6387c09cb62e` |
| pr_number | 14 |
| pr_state_target | open, draft=true, merged=false, mergeable=true |
| pr_commits_target | 8 (PLAN + 4 FIX + P2A FEAT + P2A HARDENING + DOCS TRACKED STATE SYNC) |
| current_action | `P2A_IDENTITY_AND_FAIL_CLOSED_HARDENING` (已闭合, 等 MAIN 决定) |
| next_gate | `MAIN_P2A_MICRO_DELTA_REVIEW` |
| worktree | `C:\Users\33560\Desktop\CUMCM_2025_A` |
| repository | `hongyuchen039-oss/CUMCM-2025-A` |

## 不可变 hash 复核 (本轮前后必须完全一致)

| 文件 | SHA-256 | Size |
|---|---|---|
| v1 (`work/task_contracts/TASK_007-P0P1-v1.json`) | `21fffb2653c43da371ffe0b17fbff25d8fd6bec9c4043f1d4045cc20b9db6e2e` | 14988 |
| v2 (`work/task_contracts/TASK_007-P0P1-v2.json`) | `e28d35901b9d39b8621f31bb12bdfeb778ebddcdfe5665098e7eb9f274c6bb1d` | 18470 |
| v3 file (`work/task_contracts/TASK_007-P0P1-v3.json`) | `9b4f824c67a42e164e454365e0c920622095871843625db2c01b96853cea59a4` | 30724 |
| v3 contract hash (`q4_model_contract_sha256`) | `394cbd3557696594caa229be1018e999e69171597d0736823b6c6387c09cb62e` | (32 bytes hex) |
| P2A-v1 file SHA-256 | `5306f38532579f99dd68c6dd6f4a23ce73d19cae5aa847ad597ca16096f838cd` | 6221 |
| P2A-v1 contract hash (`q4_p2a_contract_sha256`) | `4c325ed9e45381a520250fd08e5d6eceb03e7658d3a3e7dcd5417239db6786fb` | (32 bytes hex, exclude-self-field) |
| P2A-v2 contract hash (`q4_p2a_contract_sha256`) | `3048aeeddaf52a1173af08469e4464df5a4103e7c4af56f3635dd6d90df711db` | (32 bytes hex, exclude-self-field) |

任一变化 → **BLOCKED — CANONICAL CONTRACT MUTATED**.

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
  - Q4 three-drone evaluator 实现完成 + B1/B2/B3/B4 hardening 闭合
  - **105 controlled tests PASS** (real Q4 evaluator calls = 0)
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
| `TASK_007-P2A` | Q4 evaluator + 单元测试 + identity & fail-closed hardening (real Q4 calls = 0) **(本轮: P2A implementation + hardening + DOCS tracked state sync, 三次 commit)** |
| `TASK_007-P2B` | tiny bounded pilot + runtime calibration (pilot self-budget NOT FROZEN) |
| `TASK_007-P3` | Q4 formal bounded search (artifact root = work/q4_search/) |
| `TASK_007-P4` | candidate closure (artifact root = work/q4_candidate_closure/) |
| `TASK_007-P5` | fine reconstruction + result2.xlsx 写盘 + round-trip 验证 |
| `TASK_008` | Q5 + result3.xlsx |
| `TASK_009` | unified recomputation / sensitivity / robustness / figures |
| `TASK_010` | paper / consistency / final package |

## PR #14 累积变更文件 (严格 6 个)

| 文件 | 累计类型 |
|---|---|
| `.gitignore` | 既有 (P0/P1) |
| `MODEL.md` | 既有 (P0/P1) |
| `NEXT_TASK.md` | **DOCS 同步**: 本轮 P2A tracked state closeout |
| `problem/FACTS.md` | 既有 (P0/P1) |
| `src/q4_three_drones.py` | P2A implementation + P2A hardening |
| `tests/test_q4.py` | P2A implementation + P2A hardening |

**不**得引入第 7 个 tracked file.

## 关闭条件 (P2A hardening + DOCS tracked state sync, 本门已闭合)

- ✅ B1 / B2 / B3 / B4 (五/七/八) 全部 **CLOSED**; q4_evaluator code SHA 与
  commit `ba2ffcb` blob 完全一致.
- ✅ `PYTHONDONTWRITEBYTECODE=1 python -B -m unittest tests.test_q4 -v` → 105
  tests PASS, 0 failures, 0 errors (committed already, **不**再重跑).
- ✅ Q3 pure-function regression 23/23 PASS (committed already, **不**再重跑).
- ✅ v1 / v2 / v3 / P2A-v1 / P2A-v2 file SHA-256 / size / self-reference hash
  全部 immutable (任一变化 → BLOCKED).
- ✅ `python scripts/verify_task_context.py --context work/task_context.json` →
  `CONTEXT_VALID_AUTHORIZED_DIRTY`.
- ✅ `src/q4_three_drones.py`, `tests/test_q4.py`, `MODEL.md`, `problem/FACTS.md`,
  `.gitignore` 本轮 (DOCS tracked state sync) **不**变更 (仅 NEXT_TASK.md
  变更).
- ✅ 单次 commit "DOCS: synchronize TASK_007 P2A hardened state" (第八个普通
  commit, 非 amend, 非 squash, 非 force).
- ✅ push 到 origin `task/TASK_007-q4-result2`.
- ✅ PR #14 仍为 Draft; 描述更新为 P2A TRACKED STATE SYNC COMPLETE.
- ✅ PR #14 验证: state=OPEN, draft=true, merged=false, mergeable=true,
  base=`2839151c...`, head=new DOCS sync commit, commits=8, changedFiles=6.

不自动 (本门 boundary):

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
- ❌ 修改 v1 / v2 / v3 / P2A-v1 / P2A-v2 任何 byte (immutable)
- ❌ 修改 `.gitignore` / `MODEL.md` / `problem/FACTS.md` /
  `src/q4_three_drones.py` / `tests/test_q4.py` / 官方模板 / `outputs/`
  (本轮 DOCS tracked state sync 仅修改 NEXT_TASK.md)
- ❌ Amend 任何之前的 commit
- ❌ Squash commits
- ❌ Force push
- ❌ 使用 `git add .` 或 `git add work/`
- ❌ 安装任何依赖 / 创建 CI / 修改 workflow
- ❌ 重新运行 105 个测试 (本轮是纯 DOCS 同步)
- ❌ 运行任何真实 evaluator

## 下一门 (待 MAIN 显式授权)

**MAIN P2A FINAL ACCEPTANCE AND P2B AUTHORIZATION DECISION** — MAIN 决定:
1. P2A 阶段 (Q4 implementation + hardening + 105 controlled tests) 是否最终
   接受 (`p2a_final_acceptance: PENDING → ACCEPTED/REJECTED`);
2. 是否授权启动 TASK_007-P2B (tiny bounded pilot + runtime calibration,
   pilot self-budget 待 MAIN 基于 Q3 历史 + 12 维静态 + 保守上界 + 用户授权
   **首次真实 Q4 call 前** 冻结).

PR #14 整个 TASK_007 期间保持 Draft, 不合并 (单 PR 规则)。

---

> 旧版 (TASK_007-P0/P1 WORKTREE HYGIENE FINAL CLOSEOUT + FINAL SEMANTIC AND
> HASH-SCOPE FIX) 状态见 git history; 本轮 (TASK_007-P2A TRACKED STATE
> CLOSEOUT) 仅重写 NEXT_TASK.md 反映 P2A implementation + hardening 全部闭
> 合, **不**改 P0/P1 任何 commit / contract / MODEL.md / FACTS.md /
> .gitignore, **不**改 `src/q4_three_drones.py` / `tests/test_q4.py` /
> 任何 v1/v2/v3/P2A-v1/P2A-v2 contract byte.
>
> **不**实现 Q4 search / pilot / candidate closure / result2.xlsx 写盘 /
> runtime calibration; **不**启动 Audit full rerun / Hermes / Ready / merge;
> **不**启动 TASK_007-P2B / P3 / P4 / P5 / TASK_008.
>
> 本轮最高状态: **P0/P1 FINAL ACCEPTED** / **P2A Q4 EVALUATOR IMPLEMENTED +
> HARDENED (B1/B2/B3/B4) + 105 CONTROLLED TESTS PASSED** (real Q4 calls = 0)
> / P2B NOT STARTED / P3 NOT STARTED / P4 NOT STARTED / P5 NOT STARTED /
> TASK_008 NOT STARTED / SEEDS NOT FROZEN / BUDGET NOT FROZEN /
> PILOT BUDGET NOT FROZEN / Audit (full rerun) NOT STARTED / Hermes NOT STARTED.