"""Q4 三无人机联合评估器 (TASK_007-P2A).

本轮任务范围 (TASK_007-P2A — IMPLEMENTATION AND CONTROLLED UNIT TESTS):

- 实现 12 维 ThreeDroneCandidate (4 变量 × 3 无人机, 无人机之间 heading /
  speed / release / delay 完全独立);
- 实现 Two-Stage 评估器:
    - Stage A: 纯轻量 prevalidation (调用 q2_validate_strategy 但不触发
      evaluate_single_bomb_strategy 的几何评估);
    - Stage B: 按 FY1 -> FY2 -> FY3 固定顺序调用注入的 single_bomb_evaluator;
- 实现 Q4EvaluationSystemError, 当 injected evaluator 抛异常时立即停止,
  使用 `raise ... from exc` 保留 exception chaining;
- 实现 8 类 Q4 evaluation identity payload, 通过 canonical JSON -> SHA-256
  得到 q4_evaluation_id;
- 所有真实 Q1 / Q2 / Q3 / Q4 evaluator 调用 = 0;
- 测试必须通过 dependency injection 替换默认 evaluator; 默认生产 evaluator
  评估 single_bomb_strategy 时本轮不触发 (real_q4_evaluator_calls = 0).

显式不做 (本轮 boundary):

- 不得运行真实 Q4 candidate 评估 (real_q4_evaluator_calls = 0);
- 不得运行 P2B / P3 / P4 / P5 / 搜索 / 写盘;
- 不得修改任何 Q1 / Q2 / Q3 source / test;
- 不得修改 v1 / v2 / v3 contract JSON.

参考:
- work/task_contracts/TASK_007-P0P1-v3.json (CANONICAL_FINAL_P0P1_CONTRACT)
- problem/FACTS.md §13.4 (heading 方向角规则)
- src/q1_baseline.py (物理常数)
- src/q1_cylinder.py (SAMPLE_GRADES, sampling_algorithm_id)
- src/q2_single_bomb.py (SingleBomb* / evaluate_single_bomb_strategy)
- src/q3_three_bombs.py (INTERVAL_EPSILON_S, union / total)

只使用 Python 标准库.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

# Reused (NOT copied) — read-only from Q1/Q2/Q3 modules
from src.q1_baseline import (
    G, CLOUD_RADIUS, CLOUD_SINK, CLOUD_DURATION,
    MISSILE_SPEED, M0, O,
)
from src.q1_cylinder import SAMPLE_GRADES
from src.q2_single_bomb import (
    SingleBombStrategy,
    SingleBombEvaluation,
    evaluate_single_bomb_strategy,
    validate_strategy as q2_validate_strategy,
    EPS_GROUND,
)
from src.q3_three_bombs import (
    INTERVAL_EPSILON_S,
    normalize_intervals,
    union_intervals,
    total_union_duration,
)


# === Q4 合同常量 ===

# 三无人机固定顺序 (评估调用顺序 / identity payload order / union 计算顺序)
DRONE_ORDER: Tuple[str, str, str] = ("FY1", "FY2", "FY3")

# 三无人机初始位置 (FACTS.md §8 衍生 + 题目定义)
DRONE_INITIAL_POSITIONS: Dict[str, Tuple[float, float, float]] = {
    "FY1": (17800.0, 0.0, 1800.0),
    "FY2": (12000.0, 1400.0, 1400.0),
    "FY3": (6000.0, -3000.0, 700.0),
}

# candidate schema 第一版 (任何 schema 变化必须 +1)
CANDIDATE_SCHEMA_VERSION: int = 1

# q4 config schema 第一版
Q4_CONFIG_SCHEMA_VERSION: int = 1

# Q4 evaluation call contract version
EVALUATION_CALL_CONTRACT_VERSION: str = "TASK_007_Q4_TWO_STAGE_EXCEPTION_PROPAGATION_V3"

# Q4 目标语义 (单一字符串字面量, 进入 identity payload)
OBJECTIVE_IDENTITY: str = "measure(I_FY1 union I_FY2 union I_FY3)"

# 导弹信息
MISSILE_ID: str = "M1"
MISSILE_INITIAL_POSITION: Tuple[float, float, float] = (20000.0, 0.0, 2000.0)
MISSILE_TRAJECTORY_IDENTITY: str = "straight_line_to_fake_target"

# 假目标 (原点) — 与 FACTS §8 一致
FAKE_TARGET_ORIGIN: Tuple[float, float, float] = (0.0, 0.0, 0.0)

# 真目标几何 (FACTS §13 圆柱真目标)
TRUE_TARGET_GEOMETRY_PARAMETERS: Dict[str, Any] = {
    "radius": 7.0,
    "height": 10.0,
    "lower_center": [0.0, 200.0, 0.0],
}

# 圆柱采样算法 ID (与 src/q1_cylinder.generate_cylinder_samples 一致)
CYLINDER_SAMPLING_ALGORITHM_ID: str = (
    "src.q1_cylinder.generate_cylinder_samples.cell_center_v1"
)

# raw heading policy (identity 字段使用 raw heading_rad_fyi, NOT normalized)
RAW_HEADING_POLICY: str = "prevalidated_in_half_open_interval"

# Q4 model contract 锁定 (v3 canonical)
Q4_MODEL_CONTRACT_VERSION: int = 3
Q4_MODEL_CONTRACT_SHA256: str = (
    "394cbd3557696594caa229be1018e999e69171597d0736823b6c6387c09cb62e"
)

# Q4 评估结果合法 status 集合 (只有这三个; pruned_zero / zero_window 是 Q2 内部状态)
Q4_VALID_STATUSES: Tuple[str, ...] = ("invalid", "zero_union", "ok")


# --- 派生常量 (模块加载时计算, 不可变) ---

_TRUE_TARGET_GEOMETRY_ID_BYTES = json.dumps(
    {
        "radius": 7.0,
        "height": 10.0,
        "lower_center": [0.0, 200.0, 0.0],
    },
    sort_keys=True, separators=(",", ":"),
).encode("utf-8")
TRUE_TARGET_GEOMETRY_ID: str = hashlib.sha256(
    _TRUE_TARGET_GEOMETRY_ID_BYTES
).hexdigest()


# === 数据类 ===

@dataclass(frozen=True)
class GitBlobIdentity:
    """Git blob content bytes identity (单一文件 / commit SHA 解析)."""
    path: str
    execution_head_sha: str
    git_blob_oid: str
    blob_size: int
    sha256: str


@dataclass(frozen=True)
class ThreeDroneCandidate:
    """12 维三无人机决策变量.

    每架无人机拥有独立 heading_rad / speed_mps / release_time_s / delay_s;
    跨架不共享 heading / speed / release / delay; 不得添加跨架投放间隔,
    不得添加跨架通信或协同变量.
    """
    heading_rad_fy1: float
    speed_mps_fy1: float
    release_time_s_fy1: float
    delay_s_fy1: float

    heading_rad_fy2: float
    speed_mps_fy2: float
    release_time_s_fy2: float
    delay_s_fy2: float

    heading_rad_fy3: float
    speed_mps_fy3: float
    release_time_s_fy3: float
    delay_s_fy3: float


@dataclass(frozen=True)
class ThreeDroneEvaluation:
    """Q4 评估结果.

    status ∈ {"invalid", "zero_union", "ok"}.
    prevalidation invalid 时: drone_evaluations = (), union_intervals = (),
    total_union_duration_s = 0, attempted = 0, completed = 0, q4_evaluation_id = ""
    (空字符串, 不使用 "pending" / "placeholder" / None).
    """
    candidate: ThreeDroneCandidate
    valid: bool
    status: str
    reason: str
    drone_evaluations: Tuple[SingleBombEvaluation, ...]
    union_intervals: Tuple[Tuple[float, float], ...]
    total_union_duration_s: float
    sample_level: str
    scan_step_s: float
    elapsed_s: float
    q4_evaluation_id: str
    attempted_single_bomb_calls: int
    completed_single_bomb_calls: int


class Q4EvaluationSystemError(RuntimeError):
    """Q4 evaluator 调用链路系统错误.

    当第 k 次 injected / default single_bomb_evaluator 抛异常时构造并 raise.
    使用 `raise Q4EvaluationSystemError(...) from exc` 保留 exception chaining
    (__cause__ = original exception).
    """
    failing_drone_id: str
    attempted_single_bomb_calls: int
    completed_single_bomb_calls: int
    completed_drone_ids: Tuple[str, ...]
    completed_evaluations: Tuple[SingleBombEvaluation, ...]
    original_exception_type: str
    original_exception_message: str

    def __init__(
        self,
        *,
        failing_drone_id: str,
        attempted_single_bomb_calls: int,
        completed_single_bomb_calls: int,
        completed_drone_ids: Tuple[str, ...],
        completed_evaluations: Tuple[SingleBombEvaluation, ...],
        original_exception_type: str,
        original_exception_message: str,
    ) -> None:
        msg = (
            f"Q4 evaluator call failed at drone {failing_drone_id!r}; "
            f"attempted={attempted_single_bomb_calls}, "
            f"completed={completed_single_bomb_calls}, "
            f"original={original_exception_type}: {original_exception_message}"
        )
        super().__init__(msg)
        self.failing_drone_id = failing_drone_id
        self.attempted_single_bomb_calls = attempted_single_bomb_calls
        self.completed_single_bomb_calls = completed_single_bomb_calls
        self.completed_drone_ids = tuple(completed_drone_ids)
        self.completed_evaluations = tuple(completed_evaluations)
        self.original_exception_type = original_exception_type
        self.original_exception_message = original_exception_message


# === Pure helpers ===

def _is_finite(x: Any) -> bool:
    try:
        return math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def _strategy_for_drone(c: ThreeDroneCandidate, drone_id: str) -> SingleBombStrategy:
    if drone_id == "FY1":
        return SingleBombStrategy(
            heading_rad=c.heading_rad_fy1,
            speed_mps=c.speed_mps_fy1,
            release_time_s=c.release_time_s_fy1,
            delay_s=c.delay_s_fy1,
        )
    if drone_id == "FY2":
        return SingleBombStrategy(
            heading_rad=c.heading_rad_fy2,
            speed_mps=c.speed_mps_fy2,
            release_time_s=c.release_time_s_fy2,
            delay_s=c.delay_s_fy2,
        )
    if drone_id == "FY3":
        return SingleBombStrategy(
            heading_rad=c.heading_rad_fy3,
            speed_mps=c.speed_mps_fy3,
            release_time_s=c.release_time_s_fy3,
            delay_s=c.delay_s_fy3,
        )
    raise ValueError(f"unknown drone_id {drone_id!r}")


def iter_drone_strategies(
    c: ThreeDroneCandidate,
) -> Tuple[Tuple[str, Tuple[float, float, float], SingleBombStrategy],
           Tuple[str, Tuple[float, float, float], SingleBombStrategy],
           Tuple[str, Tuple[float, float, float], SingleBombStrategy]]:
    """按 FY1 -> FY2 -> FY3 固定顺序返回 (drone_id, u0, strategy)."""
    return (
        ("FY1", DRONE_INITIAL_POSITIONS["FY1"], _strategy_for_drone(c, "FY1")),
        ("FY2", DRONE_INITIAL_POSITIONS["FY2"], _strategy_for_drone(c, "FY2")),
        ("FY3", DRONE_INITIAL_POSITIONS["FY3"], _strategy_for_drone(c, "FY3")),
    )


def validate_three_drone_candidate(
    c: ThreeDroneCandidate,
) -> Tuple[bool, str]:
    """Stage A: 纯轻量 prevalidation.

    - 不调用 evaluate_single_bomb_strategy;
    - 对每架无人机按 FY1 -> FY2 -> FY3 固定顺序检查:
        1. 4 个 raw 字段均 finite;
        2. raw heading ∈ [0, 2π);
        3. speed_mps ∈ [70, 140];
        4. release_time_s >= 0;
        5. delay_s >= 0;
        6. 调用 q2_validate_strategy (含 EPS_GROUND 起爆高度合同);
    - 不跨架约束.

    Returns:
        (valid, reason). reason 包含 drone_id 与失败字段名.
        prevalidation invalid -> 不生成 ThreeDroneEvaluation q4_evaluation_id.
    """
    two_pi = 2.0 * math.pi
    for drone_id in DRONE_ORDER:
        s = _strategy_for_drone(c, drone_id)
        h = s.heading_rad
        sp = s.speed_mps
        rt = s.release_time_s
        dly = s.delay_s
        # 1. finite
        if not (_is_finite(h) and _is_finite(sp) and _is_finite(rt) and _is_finite(dly)):
            return False, f"prevalidation_failed: {drone_id} non_finite"
        # 2. raw heading ∈ [0, 2π)
        if not (0.0 <= h < two_pi):
            return False, (
                f"prevalidation_failed: {drone_id} heading_rad={h} not in [0, 2pi)"
            )
        # 3. speed
        if not (70.0 <= sp <= 140.0):
            return False, (
                f"prevalidation_failed: {drone_id} speed_mps={sp} not in [70, 140]"
            )
        # 4. release
        if rt < 0.0:
            return False, f"prevalidation_failed: {drone_id} release_time_s={rt} < 0"
        # 5. delay
        if dly < 0.0:
            return False, f"prevalidation_failed: {drone_id} delay_s={dly} < 0"
        # 6. q2_validate_strategy (含 EPS_GROUND 起爆高度合同)
        u0 = DRONE_INITIAL_POSITIONS[drone_id]
        ok, q2_reason = q2_validate_strategy(s, u0=u0)
        if not ok:
            return False, f"prevalidation_failed: {drone_id} {q2_reason}"
    return True, "ok"


# === Cylinder sample profile identity payload ===

def build_cylinder_sample_profile_identity_payload(
    sample_level: str,
) -> Dict[str, Any]:
    """基于 SAMPLE_GRADES[sample_level] 展开 effective profile parameters."""
    if sample_level not in SAMPLE_GRADES:
        raise ValueError(
            f"sample_level 必须 ∈ {list(SAMPLE_GRADES)}, 实际 {sample_level!r}"
        )
    params = SAMPLE_GRADES[sample_level]
    return {
        "cylinder_sample_profile_schema_version": 1,
        "sample_level": sample_level,
        "sampling_algorithm_id": CYLINDER_SAMPLING_ALGORITHM_ID,
        "effective_profile_parameters": {
            "side_theta": params["side_theta"],
            "side_z": params["side_z"],
            "cap_r": params["cap_r"],
            "cap_theta": params["cap_theta"],
        },
    }


def compute_cylinder_sample_profile_sha256(
    payload: Mapping[str, Any],
    *,
    excluded_fields: Sequence[str] = ("cylinder_sample_profile_sha256",),
) -> str:
    """SHA-256 over canonical JSON, excluding self-reference field(s)."""
    filtered = {k: v for k, v in payload.items() if k not in set(excluded_fields)}
    return hashlib.sha256(canonical_json_bytes(filtered)).hexdigest()


# === Q4 config identity payload ===

def build_q4_config_identity_payload(
    *,
    sample_level: str,
    scan_step: float,
) -> Dict[str, Any]:
    """Q4 config identity payload (排除 timestamp / hostname / log path).

    不得包含 self-hash q4_config_sha256.
    """
    if sample_level not in SAMPLE_GRADES:
        raise ValueError(
            f"sample_level 必须 ∈ {list(SAMPLE_GRADES)}, 实际 {sample_level!r}"
        )
    if not (isinstance(scan_step, (int, float)) and math.isfinite(float(scan_step))):
        raise ValueError(f"scan_step 必须有限数值, 实际 {scan_step!r}")
    if float(scan_step) <= 0:
        raise ValueError(f"scan_step 必须 > 0, 实际 {scan_step}")
    return {
        "q4_config_schema_version": Q4_CONFIG_SCHEMA_VERSION,
        "candidate_schema_version": CANDIDATE_SCHEMA_VERSION,
        "sample_level": sample_level,
        "scan_step_s": float(scan_step),
        "interval_touching_epsilon_s": INTERVAL_EPSILON_S,
        "objective_identity": OBJECTIVE_IDENTITY,
        "evaluation_call_contract_version": EVALUATION_CALL_CONTRACT_VERSION,
        "drone_order": list(DRONE_ORDER),
    }


def compute_q4_config_sha256(
    payload: Mapping[str, Any],
    *,
    excluded_fields: Sequence[str] = ("q4_config_sha256",),
) -> str:
    """SHA-256 over canonical JSON, excluding self-reference field(s)."""
    filtered = {k: v for k, v in payload.items() if k not in set(excluded_fields)}
    return hashlib.sha256(canonical_json_bytes(filtered)).hexdigest()


# === Canonical JSON ===

def canonicalize_json_value(value: Any) -> Any:
    """递归规范化 JSON 值.

    Rules:
      - None / bool / str: pass through; bool 不被当作 int;
      - int: pass through;
      - float: must be finite (NaN / Inf -> ValueError); -0.0 -> 0.0;
      - tuple / list -> ordered list;
      - dict -> dict with str keys (non-str -> TypeError);
      - set / frozenset -> TypeError;
      - 其它 -> TypeError.
    """
    # NOTE: bool 检查必须在 int 之前 (bool 是 int 子类)
    if value is None or isinstance(value, bool) or isinstance(value, str):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"NaN/Inf rejected in canonical JSON: {value!r}")
        # -0.0 -> 0.0
        if value == 0.0:
            return 0.0
        return value
    if isinstance(value, (list, tuple)):
        return [canonicalize_json_value(x) for x in value]
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for k, v in value.items():
            if not isinstance(k, str):
                raise TypeError(f"non-str key in canonical JSON: {k!r}")
            out[k] = canonicalize_json_value(v)
        return out
    if isinstance(value, (set, frozenset)):
        raise TypeError("set / frozenset not allowed in canonical JSON")
    raise TypeError(f"unsupported type for canonicalization: {type(value).__name__}")


def canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    """UTF-8 / sort_keys / no whitespace / no NaN-Inf canonical JSON bytes."""
    return json.dumps(
        canonicalize_json_value(dict(payload)),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


# === Git blob identity helper ===

def _is_40_hex(s: Any) -> bool:
    return (
        isinstance(s, str)
        and len(s) == 40
        and all(c in "0123456789abcdef" for c in s)
    )


def _is_64_hex_lower(s: Any) -> bool:
    return (
        isinstance(s, str)
        and len(s) == 64
        and all(c in "0123456789abcdef" for c in s)
    )


def compute_git_blob_identity(
    repo_root: "str | os.PathLike[str]",
    execution_head_sha: str,
    path: str,
) -> GitBlobIdentity:
    """Git blob content identity (D2 严格算法).

    Algorithm:
      1. git rev-parse <execution_head_sha>:<path> -> blob OID;
      2. git cat-file blob <blob_oid> -> 原始 bytes (no decode / no newline convert);
      3. SHA-256(raw bytes);
      4. 返回 GitBlobIdentity.

    Failure closed:
      - 非法 execution_head_sha -> ValueError;
      - 非法 path -> ValueError;
      - blob OID 解析失败 -> CalledProcessError (propagated);
      - blob content 读取失败 -> CalledProcessError (propagated).
    """
    if not _is_40_hex(execution_head_sha):
        raise ValueError(
            f"execution_head_sha must be 40 lowercase hex, got {execution_head_sha!r}"
        )
    if not isinstance(path, str) or not path:
        raise ValueError(f"path must be a non-empty string, got {path!r}")

    # 1. resolve blob OID at execution_head_sha:path
    blob_oid_proc = subprocess.run(
        ["git", "rev-parse", f"{execution_head_sha}:{path}"],
        cwd=os.fspath(repo_root) if not isinstance(repo_root, (bytes, bytearray)) else None,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    blob_oid = blob_oid_proc.stdout.decode("ascii").strip()
    if not _is_40_hex(blob_oid):
        raise ValueError(
            f"git rev-parse returned non-hex blob OID: {blob_oid!r} "
            f"(execution_head={execution_head_sha}, path={path!r})"
        )

    # 2. read raw blob bytes
    cat_proc = subprocess.run(
        ["git", "cat-file", "blob", blob_oid],
        cwd=os.fspath(repo_root) if not isinstance(repo_root, (bytes, bytearray)) else None,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    raw = cat_proc.stdout  # bytes, no decode

    # 3. SHA-256
    sha256 = hashlib.sha256(raw).hexdigest()

    return GitBlobIdentity(
        path=path,
        execution_head_sha=execution_head_sha,
        git_blob_oid=blob_oid,
        blob_size=len(raw),
        sha256=sha256,
    )


# === Identity payload (8 categories) ===

def _candidate_dict(c: ThreeDroneCandidate) -> Dict[str, Any]:
    """Convert ThreeDroneCandidate -> 12 raw fields dict (stable order)."""
    return {
        "heading_rad_fy1": c.heading_rad_fy1,
        "speed_mps_fy1": c.speed_mps_fy1,
        "release_time_s_fy1": c.release_time_s_fy1,
        "delay_s_fy1": c.delay_s_fy1,
        "heading_rad_fy2": c.heading_rad_fy2,
        "speed_mps_fy2": c.speed_mps_fy2,
        "release_time_s_fy2": c.release_time_s_fy2,
        "delay_s_fy2": c.delay_s_fy2,
        "heading_rad_fy3": c.heading_rad_fy3,
        "speed_mps_fy3": c.speed_mps_fy3,
        "release_time_s_fy3": c.release_time_s_fy3,
        "delay_s_fy3": c.delay_s_fy3,
    }


def _code_identity_block(
    code_identity_payload: Mapping[str, Any],
) -> Dict[str, Any]:
    """Reduce 5 GitBlobIdentity-style entries into a flat dict for hashing.

    输入字段名约定 (5 个 code identity):
      q1_baseline_code_sha256 / q1_cylinder_code_sha256 /
      q2_single_bomb_code_sha256 / q3_three_bombs_code_sha256 /
      q4_evaluator_code_sha256

    `execution_head_sha` 是 provenance only, NOT result-determining — 因此
    **不**进入 identity 哈希输入. 同一 5 个 blob SHA 但 HEAD 不同的两次
    evaluate 必须产生同一 q4_evaluation_id (v3 D2 修复条款).
    """
    required = (
        "q1_baseline_code_sha256",
        "q1_cylinder_code_sha256",
        "q2_single_bomb_code_sha256",
        "q3_three_bombs_code_sha256",
        "q4_evaluator_code_sha256",
    )
    for k in required:
        v = code_identity_payload.get(k)
        if not _is_64_hex_lower(v):
            raise ValueError(
                f"code identity field {k!r} must be 64 lowercase hex, got {v!r}"
            )
    return {k: code_identity_payload[k] for k in required}


def build_q4_evaluation_identity_payload(
    candidate: ThreeDroneCandidate,
    *,
    sample_level: str,
    scan_step: float,
    code_identity_payload: Mapping[str, Any],
    config_identity_payload: Mapping[str, Any],
    contract_sha256: str = Q4_MODEL_CONTRACT_SHA256,
) -> Dict[str, Any]:
    """8-category identity payload for q4_evaluation_id hashing."""
    if sample_level not in SAMPLE_GRADES:
        raise ValueError(
            f"sample_level 必须 ∈ {list(SAMPLE_GRADES)}, 实际 {sample_level!r}"
        )
    if not (isinstance(scan_step, (int, float)) and math.isfinite(float(scan_step))):
        raise ValueError(f"scan_step 必须有限数值, 实际 {scan_step!r}")
    if float(scan_step) <= 0:
        raise ValueError(f"scan_step 必须 > 0, 实际 {scan_step}")
    if not _is_64_hex_lower(contract_sha256):
        raise ValueError(
            f"contract_sha256 must be 64 lowercase hex, got {contract_sha256!r}"
        )
    # v3 canonical 绑定: contract_sha256 必须等于 Q4_MODEL_CONTRACT_SHA256;
    # 任何其它 64-hex 都视为 v3 未冻结, fail closed (不冒充 v3 实现 / 不冒充
    # 未来 contract).
    if contract_sha256 != Q4_MODEL_CONTRACT_SHA256:
        raise ValueError(
            f"contract_sha256 must equal Q4_MODEL_CONTRACT_SHA256 "
            f"({Q4_MODEL_CONTRACT_SHA256}), got {contract_sha256!r}"
        )

    cylinder_sample_profile_payload = build_cylinder_sample_profile_identity_payload(
        sample_level
    )
    cylinder_sample_profile_sha = compute_cylinder_sample_profile_sha256(
        cylinder_sample_profile_payload
    )
    q4_config_sha = compute_q4_config_sha256(dict(config_identity_payload))

    return {
        # 1. candidate_identity
        "candidate_identity": {
            "candidate_schema_version": CANDIDATE_SCHEMA_VERSION,
            "drone_order": list(DRONE_ORDER),
            "raw_heading_policy": RAW_HEADING_POLICY,
            "candidate": _candidate_dict(candidate),
        },
        # 2. per_drone_context
        "per_drone_context": {
            "fy1_initial_position_m": list(DRONE_INITIAL_POSITIONS["FY1"]),
            "fy2_initial_position_m": list(DRONE_INITIAL_POSITIONS["FY2"]),
            "fy3_initial_position_m": list(DRONE_INITIAL_POSITIONS["FY3"]),
        },
        # 3. missile_and_target_context
        "missile_and_target_context": {
            "missile_id": MISSILE_ID,
            "missile_initial_position_m": list(MISSILE_INITIAL_POSITION),
            "missile_speed_mps": MISSILE_SPEED,
            "missile_trajectory_identity": MISSILE_TRAJECTORY_IDENTITY,
            "fake_target_origin_m": list(FAKE_TARGET_ORIGIN),
            "true_target_geometry_parameters": {
                "radius": TRUE_TARGET_GEOMETRY_PARAMETERS["radius"],
                "height": TRUE_TARGET_GEOMETRY_PARAMETERS["height"],
                "lower_center": list(TRUE_TARGET_GEOMETRY_PARAMETERS["lower_center"]),
            },
            "true_target_geometry_id": TRUE_TARGET_GEOMETRY_ID,
        },
        # 4. numerical_profile
        "numerical_profile": {
            "sample_level": sample_level,
            "scan_step_s": float(scan_step),
            "interval_touching_epsilon_s": INTERVAL_EPSILON_S,
            "cylinder_sample_profile_identity_payload": cylinder_sample_profile_payload,
            "cylinder_sample_profile_sha256": cylinder_sample_profile_sha,
        },
        # 5. code_identity (provenance execution_head_sha is NOT result-determining)
        "code_identity": _code_identity_block(code_identity_payload),
        # 6. runtime_config_identity
        "runtime_config_identity": {
            "q4_config_schema_version": Q4_CONFIG_SCHEMA_VERSION,
            "q4_config_identity_payload": dict(config_identity_payload),
            "q4_config_sha256": q4_config_sha,
            "objective_identity": OBJECTIVE_IDENTITY,
            "evaluation_call_contract_version": EVALUATION_CALL_CONTRACT_VERSION,
        },
        # 7. physical_constants
        "physical_constants": {
            "gravity_mps2": G,
            "cloud_radius_m": CLOUD_RADIUS,
            "cloud_sink_mps": CLOUD_SINK,
            "cloud_duration_s": CLOUD_DURATION,
            "eps_ground_m": EPS_GROUND,
        },
        # 8. contract_identity
        "contract_identity": {
            "q4_model_contract_version": Q4_MODEL_CONTRACT_VERSION,
            "q4_model_contract_sha256": contract_sha256,
        },
    }


def compute_q4_evaluation_id(
    candidate: ThreeDroneCandidate,
    *,
    sample_level: str,
    scan_step: float,
    code_identity_payload: Mapping[str, Any],
    config_identity_payload: Mapping[str, Any],
    contract_sha256: str = Q4_MODEL_CONTRACT_SHA256,
) -> str:
    """SHA-256 over canonical JSON of 8-category identity payload.

    Returns lowercase 64 hex SHA-256 digest.

    Requires:
      - 5 *_code_sha256 fields all 64-hex lowercase;
      - contract_sha256 == Q4_MODEL_CONTRACT_SHA256 (默认).

    Raises ValueError on missing / malformed SHA fields.
    """
    payload = build_q4_evaluation_identity_payload(
        candidate,
        sample_level=sample_level,
        scan_step=scan_step,
        code_identity_payload=code_identity_payload,
        config_identity_payload=config_identity_payload,
        contract_sha256=contract_sha256,
    )
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


# === Public API: evaluate_three_drone_strategy ===

def evaluate_three_drone_strategy(
    candidate: ThreeDroneCandidate,
    *,
    sample_level: str = "coarse",
    scan_step: float = 0.05,
    single_bomb_evaluator: Callable[..., SingleBombEvaluation] = (
        evaluate_single_bomb_strategy
    ),
    code_identity_payload: Optional[Mapping[str, Any]] = None,
    config_identity_payload: Optional[Mapping[str, Any]] = None,
    contract_sha256: str = Q4_MODEL_CONTRACT_SHA256,
) -> ThreeDroneEvaluation:
    """Q4 三无人机联合评估.

    Two-Stage:
      Stage A: prevalidation (q2_validate_strategy for each drone, no
        single_bomb_evaluator calls). On prevalidation invalid: return
        ThreeDroneEvaluation(valid=False, status="invalid",
        drone_evaluations=(), union_intervals=(), total_union_duration_s=0,
        attempted=0, completed=0, q4_evaluation_id="", elapsed_s=...).
      Stage B: for drone_id in DRONE_ORDER:
        attempted += 1;
        call single_bomb_evaluator(strategy, sample_level=sample_level,
          scan_step=scan_step, u0=DRONE_INITIAL_POSITIONS[drone_id]);
        on exception: raise Q4EvaluationSystemError(...) from exc
          (no ThreeDroneEvaluation returned, no fake SingleBombEvaluation);
        on normal return: completed += 1, append real SingleBombEvaluation.
      Stage C: aggregate Q2 statuses.
        if any (valid=False or status="invalid"): q4 valid=False, status="invalid",
          reason="some_single_bomb_invalid", preserve 3 real returns, union empty,
          total=0, attempted=3, completed=3, q4_evaluation_id="";
        else: union = union_intervals(*ev.intervals, epsilon=INTERVAL_EPSILON_S),
          total = total_union_duration(union),
          status = "ok" if total > 0 else "zero_union", valid=True,
          q4_evaluation_id = compute_q4_evaluation_id(...) if
            code_identity_payload provided, else "".

    Real Q4 evaluator calls = 0 by injection (test uses StubRecorder).
    """
    t0 = time.perf_counter()

    # Stage 0: 验证 sample_level / scan_step (mirror Q2 contract)
    if sample_level not in SAMPLE_GRADES:
        raise ValueError(
            f"sample_level 必须 ∈ {list(SAMPLE_GRADES)}, 实际 {sample_level!r}"
        )
    if not (isinstance(scan_step, (int, float)) and math.isfinite(float(scan_step))):
        raise ValueError(f"scan_step 必须有限数值, 实际 {scan_step!r}")
    if float(scan_step) <= 0:
        raise ValueError(f"scan_step 必须 > 0, 实际 {scan_step}")

    # Stage A: prevalidation (NO evaluator call)
    valid, reason = validate_three_drone_candidate(candidate)
    elapsed = time.perf_counter() - t0
    if not valid:
        return ThreeDroneEvaluation(
            candidate=candidate,
            valid=False,
            status="invalid",
            reason=reason,
            drone_evaluations=(),
            union_intervals=(),
            total_union_duration_s=0.0,
            sample_level=sample_level,
            scan_step_s=float(scan_step),
            elapsed_s=elapsed,
            q4_evaluation_id="",
            attempted_single_bomb_calls=0,
            completed_single_bomb_calls=0,
        )

    # Stage B: call injected evaluator in fixed order
    drone_evs: List[SingleBombEvaluation] = []
    drone_ids: List[str] = []
    attempted = 0
    completed = 0
    for drone_id in DRONE_ORDER:
        strategy = _strategy_for_drone(candidate, drone_id)
        u0 = DRONE_INITIAL_POSITIONS[drone_id]
        attempted += 1
        try:
            ev = single_bomb_evaluator(
                strategy,
                sample_level=sample_level,
                scan_step=scan_step,
                u0=u0,
            )
        except BaseException as exc:
            # raise ... from exc preserves __cause__
            raise Q4EvaluationSystemError(
                failing_drone_id=drone_id,
                attempted_single_bomb_calls=attempted,
                completed_single_bomb_calls=completed,
                completed_drone_ids=tuple(drone_ids),
                completed_evaluations=tuple(drone_evs),
                original_exception_type=type(exc).__name__,
                original_exception_message=str(exc),
            ) from exc
        drone_evs.append(ev)
        drone_ids.append(drone_id)
        completed += 1

    # Stage C: aggregate Q2 statuses
    any_invalid = any(
        (not ev.valid) or ev.status == "invalid" for ev in drone_evs
    )
    if any_invalid:
        elapsed = time.perf_counter() - t0
        invalid_ids = [
            drone_ids[i] for i, ev in enumerate(drone_evs)
            if (not ev.valid) or ev.status == "invalid"
        ]
        return ThreeDroneEvaluation(
            candidate=candidate,
            valid=False,
            status="invalid",
            reason=f"some_single_bomb_invalid: {invalid_ids}",
            drone_evaluations=tuple(drone_evs),
            union_intervals=(),
            total_union_duration_s=0.0,
            sample_level=sample_level,
            scan_step_s=float(scan_step),
            elapsed_s=elapsed,
            q4_evaluation_id="",
            attempted_single_bomb_calls=attempted,
            completed_single_bomb_calls=completed,
        )

    # Stage D: union / total
    union = union_intervals(
        *(ev.intervals for ev in drone_evs),
        epsilon=INTERVAL_EPSILON_S,
    )
    total = total_union_duration(union)
    if total > 0:
        status = "ok"
    else:
        status = "zero_union"

    # Stage E: q4_evaluation_id (only if code_identity_payload provided)
    q4_id = ""
    if code_identity_payload is not None:
        if config_identity_payload is None:
            cfg_payload = build_q4_config_identity_payload(
                sample_level=sample_level, scan_step=float(scan_step)
            )
        else:
            cfg_payload = dict(config_identity_payload)
        q4_id = compute_q4_evaluation_id(
            candidate,
            sample_level=sample_level,
            scan_step=float(scan_step),
            code_identity_payload=code_identity_payload,
            config_identity_payload=cfg_payload,
            contract_sha256=contract_sha256,
        )

    elapsed = time.perf_counter() - t0
    return ThreeDroneEvaluation(
        candidate=candidate,
        valid=True,
        status=status,
        reason=f"union_evaluated: {len(union)} interval(s)",
        drone_evaluations=tuple(drone_evs),
        union_intervals=union,
        total_union_duration_s=float(total),
        sample_level=sample_level,
        scan_step_s=float(scan_step),
        elapsed_s=elapsed,
        q4_evaluation_id=q4_id,
        attempted_single_bomb_calls=attempted,
        completed_single_bomb_calls=completed,
    )