"""Q4 三无人机联合评估器 (TASK_007-P2A — IDENTITY AND FAIL-CLOSED HARDENING).

本轮任务范围 (TASK_007-P2A — IMPLEMENTATION AND CONTROLLED UNIT TESTS,
                                                   ↑ HARDENING):

- 实现 12 维 ThreeDroneCandidate (4 变量 × 3 无人机, 无人机之间 heading /
  speed / release / delay 完全独立);
- 实现 Two-Stage 评估器:
    - Stage A: 纯轻量 prevalidation (调用 q2_validate_strategy 但不触发
      evaluate_single_bomb_strategy 的几何评估);
    - Stage B: 按 FY1 -> FY2 -> FY3 固定顺序调用注入的 single_bomb_evaluator;
- 实现 Q4EvaluationSystemError, 当 injected evaluator 抛 Exception 时立即停止,
  使用 `raise ... from exc` 保留 exception chaining;
  KeyboardInterrupt / SystemExit / GeneratorExit 原样传播（B4）;
- 实现 Q4EvaluationIdentityContext 必填 keyword-only context, 包含
  code_identity (Mapping[str, GitBlobIdentity]) + q4_config / profile /
  missile_and_target / physical / contract context（B1/B2/B3）;
- 严格 GitBlobIdentity schema: 5 必填 key, 每项 path / OID / size / sha256
  验证, 5 个 execution_head_sha 必须一致（B2）;
- 实现 Q2ReturnContractError 隔离 Q2 q4-evaluator 返回 contract 差异;
  任何非 SingleBombEvaluation / 非法 status / valid 不一致 → fail closed
  raise Q4EvaluationSystemError（B4）;
- evaluate_three_drone_strategy 在 prevalidation invalid 时 0 Q2 calls,
  q4_evaluation_id == ""; prevalidation valid 时 0 stub calls 前已生成
  q4_evaluation_id; ok / zero_union / Q2 normal invalid 三种正常路径均
  必须输出 lowercase 64 hex q4_evaluation_id（B1）;
- 严格 numeric prevalidation: 字符串 / None / bool / Decimal / NaN / Inf
  全部正常 invalid, 不抛 TypeError（五/七）;
- compute_git_blob_identity 失败包含 execution_head_sha / path / stderr
  上下文（八）;
- 所有真实 Q1 / Q2 / Q3 / Q4 evaluator 调用 = 0;
- 测试必须通过 dependency injection 替换默认 evaluator; 默认生产 evaluator
  评估 single_bomb_strategy 时本轮不触发 (real_q4_evaluator_calls = 0).

显式不做 (本轮 boundary):

- 不得运行真实 Q4 candidate 评估 (real_q4_evaluator_calls = 0);
- 不得运行 P2B / P3 / P4 / P5 / 搜索 / 写盘;
- 不得修改任何 Q1 / Q2 / Q3 source / test;
- 不得修改 v1 / v2 / v3 contract JSON; 不得修改 P2A-v1 contract JSON.

参考:
- work/task_contracts/TASK_007-P0P1-v3.json (CANONICAL_FINAL_P0P1_CONTRACT)
- work/task_contracts/TASK_007-P2A-v1.json (CANONICAL_P2A_IMPLEMENTATION_AND_TEST_CONTRACT)
- work/task_contracts/TASK_007-P2A-v2.json (CANONICAL_P2A_IDENTITY_AND_FAIL_CLOSED_HARDENED)
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

# Q2 内部合法 status (Q2 evaluator 正常返回)
Q2_VALID_STATUSES: Tuple[str, ...] = ("invalid", "pruned_zero", "zero_window", "ok")

# Required code identity keys (B2 严格 schema)
REQUIRED_CODE_IDENTITY_KEYS: Tuple[str, ...] = (
    "q1_baseline",
    "q1_cylinder",
    "q2_single_bomb",
    "q3_three_bombs",
    "q4_evaluator",
)

# 每 key 期望的 path (B2 路径必须精确对应)
REQUIRED_CODE_IDENTITY_PATHS: Dict[str, str] = {
    "q1_baseline": "src/q1_baseline.py",
    "q1_cylinder": "src/q1_cylinder.py",
    "q2_single_bomb": "src/q2_single_bomb.py",
    "q3_three_bombs": "src/q3_three_bombs.py",
    "q4_evaluator": "src/q4_three_drones.py",
}


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


# === 异常 ===

class Q4EvaluationSystemError(RuntimeError):
    """Q4 evaluator 调用链路系统错误 (B1/B4).

    当第 k 次 injected / default single_bomb_evaluator 抛 Exception 时构造并
    raise, 或当 Q2 返回 contract 不被满足时构造并 raise.
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


class Q2ReturnContractError(RuntimeError):
    """Q2 evaluator 返回 contract 不被满足 (B4)."""


class GitBlobIdentityError(RuntimeError):
    """Git blob identity 解析失败 (八)."""

    def __init__(
        self,
        *,
        execution_head_sha: str,
        path: str,
        stderr: str,
        original_exception_type: str,
    ) -> None:
        msg = (
            f"git blob identity resolution failed: "
            f"execution_head_sha={execution_head_sha!r}, path={path!r}, "
            f"original={original_exception_type}, stderr={stderr!r}"
        )
        super().__init__(msg)
        self.execution_head_sha = execution_head_sha
        self.path = path
        self.stderr = stderr
        self.original_exception_type = original_exception_type


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
    正常路径 (ok / zero_union / Q2 normal invalid) q4_evaluation_id 必须是
    lowercase 64 hex SHA-256 (B1).
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


@dataclass(frozen=True)
class Q4EvaluationIdentityContext:
    """Normal-path 必填 keyword-only identity context (B1).

    evaluate_three_drone_strategy 在 prevalidation invalid 时不会读这个
    context; prevalidation valid 时必须在 0 stub calls 之前完整验证
    此 context, 之后才会进入 FY1 -> FY2 -> FY3 调用链.
    """
    candidate_schema_version: int
    code_identity: Mapping[str, GitBlobIdentity]
    q4_config_identity_payload: Mapping[str, object]
    cylinder_sample_profile_identity_payload: Mapping[str, object]
    missile_and_target_context: Mapping[str, object]
    physical_constants: Mapping[str, object]
    contract_version: int
    contract_sha256: str


# === Pure helpers ===

def _is_real_finite_number(value: object) -> bool:
    """严格 finite number check (不允许 bool / str / None / Decimal).

    bool 必须在 int 之前排除 (bool 是 int 的 subclass).
    """
    if isinstance(value, bool):
        return False
    if not isinstance(value, (int, float)):
        return False
    return math.isfinite(float(value))


def _is_strictly_real_finite_number(value: object) -> bool:
    """严格有限数值 (排除 bool).

    适用于 scan_step / heading / speed / release / delay 等所有数值字段.
    """
    return _is_real_finite_number(value)


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


def _candidate_fields(c: ThreeDroneCandidate) -> Tuple[Tuple[str, object], ...]:
    """12 字段 (name, value) 固定顺序, 用于严格 prevalidation."""
    return (
        ("heading_rad_fy1", c.heading_rad_fy1),
        ("speed_mps_fy1", c.speed_mps_fy1),
        ("release_time_s_fy1", c.release_time_s_fy1),
        ("delay_s_fy1", c.delay_s_fy1),
        ("heading_rad_fy2", c.heading_rad_fy2),
        ("speed_mps_fy2", c.speed_mps_fy2),
        ("release_time_s_fy2", c.release_time_s_fy2),
        ("delay_s_fy2", c.delay_s_fy2),
        ("heading_rad_fy3", c.heading_rad_fy3),
        ("speed_mps_fy3", c.speed_mps_fy3),
        ("release_time_s_fy3", c.release_time_s_fy3),
        ("delay_s_fy3", c.delay_s_fy3),
    )


def iter_drone_strategies(
    c: ThreeDroneCandidate,
) -> Tuple[
    Tuple[str, Tuple[float, float, float], SingleBombStrategy],
    Tuple[str, Tuple[float, float, float], SingleBombStrategy],
    Tuple[str, Tuple[float, float, float], SingleBombStrategy],
]:
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
    - 12 字段每一项必须严格 finite number (拒绝 bool / str / None / Decimal);
    - 按 FY1 -> FY2 -> FY3 固定顺序逐架检查:
        1. 4 个 raw 字段均 finite;
        2. raw heading ∈ [0, 2π);
        3. speed_mps ∈ [70, 140];
        4. release_time_s >= 0;
        5. delay_s >= 0;
        6. 调用 q2_validate_strategy (含 EPS_GROUND 起爆高度合同);
    - 不跨架约束.
    - 字符串 / None / bool / Decimal 等异常类型: 正常 invalid 返回, 不抛
      TypeError.

    Returns:
        (valid, reason). reason 包含 drone_id 与失败字段名.
        prevalidation invalid -> 不生成 ThreeDroneEvaluation q4_evaluation_id.
    """
    try:
        two_pi = 2.0 * math.pi
        for drone_id in DRONE_ORDER:
            s = _strategy_for_drone(c, drone_id)
            h = s.heading_rad
            sp = s.speed_mps
            rt = s.release_time_s
            dly = s.delay_s
            # 1. finite (strict, 拒绝 bool / str / None / Decimal)
            for label, val in (("heading_rad", h), ("speed_mps", sp),
                               ("release_time_s", rt), ("delay_s", dly)):
                if not _is_real_finite_number(val):
                    return False, (
                        f"prevalidation_failed: {drone_id} {label}={val!r} "
                        f"not_strict_real_finite_number"
                    )
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
    except (TypeError, ValueError) as exc:
        # 任何意外数值 / 类型异常 — 转化为 prevalidation invalid, 不抛
        # TypeError / ValueError (B 五/七).
        return False, f"prevalidation_failed: type_or_value_error {exc}"


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
    if not _is_strictly_real_finite_number(scan_step):
        raise ValueError(f"scan_step 必须有限数值 (且非 bool), 实际 {scan_step!r}")
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

    Failure closed (八):
      - 非法 execution_head_sha -> ValueError;
      - 非法 path -> ValueError;
      - subprocess CalledProcessError -> GitBlobIdentityError (含
        execution_head_sha / path / stderr 上下文).
    """
    if not _is_40_hex(execution_head_sha):
        raise ValueError(
            f"execution_head_sha must be 40 lowercase hex, got {execution_head_sha!r}"
        )
    if not isinstance(path, str) or not path:
        raise ValueError(f"path must be a non-empty string, got {path!r}")

    cwd = os.fspath(repo_root) if not isinstance(repo_root, (bytes, bytearray)) else None

    # 1. resolve blob OID at execution_head_sha:path
    try:
        blob_oid_proc = subprocess.run(
            ["git", "rev-parse", f"{execution_head_sha}:{path}"],
            cwd=cwd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or b"").decode("utf-8", errors="replace")
        raise GitBlobIdentityError(
            execution_head_sha=execution_head_sha,
            path=path,
            stderr=stderr,
            original_exception_type=type(exc).__name__,
        ) from exc
    blob_oid = blob_oid_proc.stdout.decode("ascii").strip()
    if not _is_40_hex(blob_oid):
        raise ValueError(
            f"git rev-parse returned non-hex blob OID: {blob_oid!r} "
            f"(execution_head={execution_head_sha}, path={path!r})"
        )

    # 2. read raw blob bytes
    try:
        cat_proc = subprocess.run(
            ["git", "cat-file", "blob", blob_oid],
            cwd=cwd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or b"").decode("utf-8", errors="replace")
        raise GitBlobIdentityError(
            execution_head_sha=execution_head_sha,
            path=path,
            stderr=stderr,
            original_exception_type=type(exc).__name__,
        ) from exc
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


# === B2: 严格 GitBlobIdentity schema 校验 ===

def _validate_and_reduce_code_identity(
    code_identity: Mapping[str, Any],
) -> Dict[str, Dict[str, str]]:
    """Strict GitBlobIdentity schema validation (B2).

    输入: Mapping[str, Any] (期望 5 key, value 为 GitBlobIdentity).
    输出: 严格 5 项 flat dict [{path, git_blob_oid, blob_size, sha256}].
    execution_head_sha 单独验证 5 项一致, 作为 provenance / evidence.

    Raises:
      ValueError on missing key / wrong path / wrong type / wrong format /
      5 execution_head_sha 不一致.
    """
    if not isinstance(code_identity, Mapping):
        raise ValueError(
            f"code_identity must be a Mapping, got {type(code_identity).__name__}"
        )

    # 1. 5 必填 key 全部存在
    for key in REQUIRED_CODE_IDENTITY_KEYS:
        if key not in code_identity:
            raise ValueError(
                f"code_identity missing required key {key!r}; "
                f"required={list(REQUIRED_CODE_IDENTITY_KEYS)}"
            )
    # 2. 不得含多余 key
    extras = set(code_identity.keys()) - set(REQUIRED_CODE_IDENTITY_KEYS)
    if extras:
        raise ValueError(
            f"code_identity has extra keys {sorted(extras)!r}; "
            f"required={list(REQUIRED_CODE_IDENTITY_KEYS)}"
        )

    # 3. 逐项验证 (path / sha / OID / size / execution_head_sha)
    execution_head_shas = set()
    blobs: Dict[str, GitBlobIdentity] = {}
    for key in REQUIRED_CODE_IDENTITY_KEYS:
        item = code_identity[key]
        if not isinstance(item, GitBlobIdentity):
            raise ValueError(
                f"code_identity[{key!r}] must be GitBlobIdentity, "
                f"got {type(item).__name__}"
            )
        # path
        if not isinstance(item.path, str) or not item.path:
            raise ValueError(
                f"code_identity[{key!r}].path must be non-empty string, "
                f"got {item.path!r}"
            )
        if item.path != REQUIRED_CODE_IDENTITY_PATHS[key]:
            raise ValueError(
                f"code_identity[{key!r}].path must be {REQUIRED_CODE_IDENTITY_PATHS[key]!r}, "
                f"got {item.path!r}"
            )
        # execution_head_sha
        if not _is_40_hex(item.execution_head_sha):
            raise ValueError(
                f"code_identity[{key!r}].execution_head_sha must be 40 lowercase hex, "
                f"got {item.execution_head_sha!r}"
            )
        execution_head_shas.add(item.execution_head_sha)
        # git_blob_oid
        if not _is_40_hex(item.git_blob_oid):
            raise ValueError(
                f"code_identity[{key!r}].git_blob_oid must be 40 lowercase hex, "
                f"got {item.git_blob_oid!r}"
            )
        # blob_size
        if not isinstance(item.blob_size, int) or isinstance(item.blob_size, bool):
            raise ValueError(
                f"code_identity[{key!r}].blob_size must be int, got {item.blob_size!r}"
            )
        if item.blob_size < 0:
            raise ValueError(
                f"code_identity[{key!r}].blob_size must be >= 0, got {item.blob_size!r}"
            )
        # sha256
        if not _is_64_hex_lower(item.sha256):
            raise ValueError(
                f"code_identity[{key!r}].sha256 must be 64 lowercase hex, "
                f"got {item.sha256!r}"
            )
        blobs[key] = item

    # 4. 5 个 execution_head_sha 必须一致
    if len(execution_head_shas) != 1:
        raise ValueError(
            f"all 5 code_identity execution_head_sha must be identical; "
            f"got {sorted(execution_head_shas)!r}"
        )

    # 5. 严格 schema 输出 (B2: 仅 path / git_blob_oid / blob_size / sha256
    #    进入 hash 输入; execution_head_sha 仅 provenance / evidence).
    return {
        key: {
            "path": blobs[key].path,
            "git_blob_oid": blobs[key].git_blob_oid,
            "blob_size": blobs[key].blob_size,
            "sha256": blobs[key].sha256,
        }
        for key in REQUIRED_CODE_IDENTITY_KEYS
    }


# === B3: 严格 context validator (config / profile / missile / physical / contract) ===

def _validate_canonical_equal(
    actual: Mapping[str, object],
    expected: Mapping[str, object],
    *,
    label: str,
) -> None:
    """严格 canonical-equal 检查 (B3).

    不允许:
      - 缺字段
      - 多字段
      - 包含 timestamp / hostname / log_path / working_directory / elapsed /
        generated_at 等非结果字段
    """
    if not isinstance(actual, Mapping):
        raise ValueError(
            f"{label} must be a Mapping, got {type(actual).__name__}"
        )
    FORBIDDEN_KEYS = {
        "timestamp", "hostname", "log_path", "working_directory",
        "elapsed", "generated_at",
    }
    actual_keys = set(actual.keys())
    expected_keys = set(expected.keys())
    if actual_keys != expected_keys:
        raise ValueError(
            f"{label} canonical key mismatch: "
            f"missing={sorted(expected_keys - actual_keys)!r}, "
            f"extra={sorted(actual_keys - expected_keys)!r}"
        )
    forbidden_overlap = actual_keys & FORBIDDEN_KEYS
    if forbidden_overlap:
        raise ValueError(
            f"{label} contains forbidden non-result keys {sorted(forbidden_overlap)!r}"
        )
    # canonical-equal: 通过 canonical JSON bytes 比较
    actual_bytes = canonical_json_bytes(actual)
    expected_bytes = canonical_json_bytes(expected)
    if actual_bytes != expected_bytes:
        raise ValueError(
            f"{label} canonical JSON mismatch: "
            f"actual={actual_bytes.decode('utf-8')!r}, "
            f"expected={expected_bytes.decode('utf-8')!r}"
        )


def _build_expected_missile_and_target_context() -> Dict[str, object]:
    return {
        "missile_id": MISSILE_ID,
        "missile_initial_position_m": list(MISSILE_INITIAL_POSITION),
        "missile_speed_mps": MISSILE_SPEED,
        "missile_trajectory_identity": MISSILE_TRAJECTORY_IDENTITY,
        "fake_target_origin_m": list(FAKE_TARGET_ORIGIN),
        "true_target_geometry_parameters": {
            "radius": float(TRUE_TARGET_GEOMETRY_PARAMETERS["radius"]),
            "height": float(TRUE_TARGET_GEOMETRY_PARAMETERS["height"]),
            "lower_center": list(TRUE_TARGET_GEOMETRY_PARAMETERS["lower_center"]),
        },
        "true_target_geometry_id": TRUE_TARGET_GEOMETRY_ID,
    }


def _build_expected_physical_constants() -> Dict[str, object]:
    return {
        "gravity_mps2": float(G),
        "cloud_radius_m": float(CLOUD_RADIUS),
        "cloud_sink_mps": float(CLOUD_SINK),
        "cloud_duration_s": float(CLOUD_DURATION),
        "eps_ground_m": float(EPS_GROUND),
    }


def _validate_normal_identity_context(
    identity_context: Q4EvaluationIdentityContext,
    *,
    sample_level: str,
    scan_step: float,
) -> None:
    """B3: 严格 identity_context 校验, 0 stub calls 之前。

    Raises:
      ValueError on 任何不一致.
    """
    # 1. candidate_schema_version
    if identity_context.candidate_schema_version != CANDIDATE_SCHEMA_VERSION:
        raise ValueError(
            f"identity_context.candidate_schema_version must be "
            f"{CANDIDATE_SCHEMA_VERSION}, got {identity_context.candidate_schema_version!r}"
        )
    # 2. contract_version / contract_sha256
    if identity_context.contract_version != Q4_MODEL_CONTRACT_VERSION:
        raise ValueError(
            f"identity_context.contract_version must be "
            f"{Q4_MODEL_CONTRACT_VERSION}, got {identity_context.contract_version!r}"
        )
    if (not _is_64_hex_lower(identity_context.contract_sha256)
            or identity_context.contract_sha256 != Q4_MODEL_CONTRACT_SHA256):
        raise ValueError(
            f"identity_context.contract_sha256 must equal "
            f"{Q4_MODEL_CONTRACT_SHA256}, got {identity_context.contract_sha256!r}"
        )
    # 3. q4_config_identity_payload 必须 canonical-equal 于
    #    build_q4_config_identity_payload(sample_level, scan_step)
    expected_config = build_q4_config_identity_payload(
        sample_level=sample_level, scan_step=float(scan_step),
    )
    _validate_canonical_equal(
        identity_context.q4_config_identity_payload,
        expected_config,
        label="identity_context.q4_config_identity_payload",
    )
    # 4. cylinder_sample_profile_identity_payload 必须 canonical-equal 于
    #    build_cylinder_sample_profile_identity_payload(sample_level)
    expected_profile = build_cylinder_sample_profile_identity_payload(sample_level)
    _validate_canonical_equal(
        identity_context.cylinder_sample_profile_identity_payload,
        expected_profile,
        label="identity_context.cylinder_sample_profile_identity_payload",
    )
    # 5. missile_and_target_context
    expected_missile = _build_expected_missile_and_target_context()
    _validate_canonical_equal(
        identity_context.missile_and_target_context,
        expected_missile,
        label="identity_context.missile_and_target_context",
    )
    # 6. physical_constants
    expected_phys = _build_expected_physical_constants()
    _validate_canonical_equal(
        identity_context.physical_constants,
        expected_phys,
        label="identity_context.physical_constants",
    )


def build_q4_evaluation_identity_context(
    *,
    code_identity: Mapping[str, GitBlobIdentity],
    sample_level: str,
    scan_step: float,
) -> Q4EvaluationIdentityContext:
    """B1/B3: 单一 builder, 从模块真实常量生成其余冻结 context.

    Args:
      code_identity: 严格 5 key GitBlobIdentity mapping (B2).
      sample_level: 必须 ∈ SAMPLE_GRADES.
      scan_step: 必须 strict finite real number > 0.

    Returns:
      Q4EvaluationIdentityContext (全部 context 由本模块真实常量生成).

    Raises:
      ValueError on 任何 schema / numerical / code identity 不一致.
    """
    if sample_level not in SAMPLE_GRADES:
        raise ValueError(
            f"sample_level 必须 ∈ {list(SAMPLE_GRADES)}, 实际 {sample_level!r}"
        )
    if not _is_strictly_real_finite_number(scan_step):
        raise ValueError(f"scan_step 必须有限数值 (且非 bool), 实际 {scan_step!r}")
    if float(scan_step) <= 0:
        raise ValueError(f"scan_step 必须 > 0, 实际 {scan_step}")

    # 强校验 code_identity (B2): 抛 ValueError on 任何不一致
    _validate_and_reduce_code_identity(code_identity)

    cfg = build_q4_config_identity_payload(
        sample_level=sample_level, scan_step=float(scan_step),
    )
    profile = build_cylinder_sample_profile_identity_payload(sample_level)
    missile_ctx = _build_expected_missile_and_target_context()
    phys = _build_expected_physical_constants()

    return Q4EvaluationIdentityContext(
        candidate_schema_version=CANDIDATE_SCHEMA_VERSION,
        code_identity=dict(code_identity),
        q4_config_identity_payload=cfg,
        cylinder_sample_profile_identity_payload=profile,
        missile_and_target_context=missile_ctx,
        physical_constants=phys,
        contract_version=Q4_MODEL_CONTRACT_VERSION,
        contract_sha256=Q4_MODEL_CONTRACT_SHA256,
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


def build_q4_evaluation_identity_payload(
    candidate: ThreeDroneCandidate,
    *,
    sample_level: str,
    scan_step: float,
    identity_context: Q4EvaluationIdentityContext,
) -> Dict[str, Any]:
    """8-category identity payload for q4_evaluation_id hashing.

    不再接受 relaxed code_identity_payload / config_identity_payload;
    强制使用 mapping Q4EvaluationIdentityContext (B1/B2/B3).
    """
    if sample_level not in SAMPLE_GRADES:
        raise ValueError(
            f"sample_level 必须 ∈ {list(SAMPLE_GRADES)}, 实际 {sample_level!r}"
        )
    if not _is_strictly_real_finite_number(scan_step):
        raise ValueError(f"scan_step 必须有限数值 (且非 bool), 实际 {scan_step!r}")
    if float(scan_step) <= 0:
        raise ValueError(f"scan_step 必须 > 0, 实际 {scan_step}")

    # 0. 严格 context 校验 (B3) — 任一不一致立即 ValueError (0 stub calls)
    _validate_normal_identity_context(
        identity_context, sample_level=sample_level, scan_step=float(scan_step),
    )

    # 1. 严格 code_identity schema (B2)
    code_identity_block = _validate_and_reduce_code_identity(
        identity_context.code_identity
    )

    profile_payload = dict(identity_context.cylinder_sample_profile_identity_payload)
    profile_sha = compute_cylinder_sample_profile_sha256(profile_payload)
    config_payload = dict(identity_context.q4_config_identity_payload)
    config_sha = compute_q4_config_sha256(config_payload)

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
        "missile_and_target_context": dict(identity_context.missile_and_target_context),
        # 4. numerical_profile
        "numerical_profile": {
            "sample_level": sample_level,
            "scan_step_s": float(scan_step),
            "interval_touching_epsilon_s": INTERVAL_EPSILON_S,
            "cylinder_sample_profile_identity_payload": profile_payload,
            "cylinder_sample_profile_sha256": profile_sha,
        },
        # 5. code_identity (B2: 严格 schema, execution_head_sha 不入 hash)
        "code_identity": code_identity_block,
        # 6. runtime_config_identity
        "runtime_config_identity": {
            "q4_config_schema_version": Q4_CONFIG_SCHEMA_VERSION,
            "q4_config_identity_payload": config_payload,
            "q4_config_sha256": config_sha,
            "objective_identity": OBJECTIVE_IDENTITY,
            "evaluation_call_contract_version": EVALUATION_CALL_CONTRACT_VERSION,
        },
        # 7. physical_constants
        "physical_constants": dict(identity_context.physical_constants),
        # 8. contract_identity
        "contract_identity": {
            "q4_model_contract_version": identity_context.contract_version,
            "q4_model_contract_sha256": identity_context.contract_sha256,
        },
    }


def compute_q4_evaluation_id(
    candidate: ThreeDroneCandidate,
    *,
    sample_level: str,
    scan_step: float,
    identity_context: Q4EvaluationIdentityContext,
) -> str:
    """SHA-256 over canonical JSON of 8-category identity payload.

    Returns lowercase 64 hex SHA-256 digest.

    Raises:
      ValueError on 任何 schema / numerical / context 不一致.
    """
    payload = build_q4_evaluation_identity_payload(
        candidate,
        sample_level=sample_level,
        scan_step=scan_step,
        identity_context=identity_context,
    )
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


# === B4: Q2 return contract 验证 ===

def _validate_q2_return_contract(
    ev: object,
    *,
    drone_id: str,
) -> None:
    """B4: 验证 Q2 evaluator 正常返回的 SingleBombEvaluation contract.

    Rules:
      1. isinstance(ev, SingleBombEvaluation);
      2. ev.status ∈ {"invalid","pruned_zero","zero_window","ok"};
      3. status == "invalid" 必须 valid is False;
         status in {"pruned_zero","zero_window","ok"} 必须 valid is True.

    Raises:
      Q2ReturnContractError on 任何不一致.
    """
    if not isinstance(ev, SingleBombEvaluation):
        raise Q2ReturnContractError(
            f"q2 evaluator return for {drone_id!r} must be SingleBombEvaluation, "
            f"got {type(ev).__name__}"
        )
    if not isinstance(ev.status, str) or ev.status not in Q2_VALID_STATUSES:
        raise Q2ReturnContractError(
            f"q2 evaluator return for {drone_id!r} has invalid status "
            f"{ev.status!r} (must be one of {list(Q2_VALID_STATUSES)})"
        )
    if ev.status == "invalid":
        if ev.valid is not False:
            raise Q2ReturnContractError(
                f"q2 evaluator return for {drone_id!r} has status='invalid' "
                f"but valid={ev.valid!r} (must be False)"
            )
    else:
        if ev.valid is not True:
            raise Q2ReturnContractError(
                f"q2 evaluator return for {drone_id!r} has status={ev.status!r} "
                f"but valid={ev.valid!r} (must be True)"
            )


# === Public API: evaluate_three_drone_strategy ===

def evaluate_three_drone_strategy(
    candidate: ThreeDroneCandidate,
    *,
    sample_level: str = "coarse",
    scan_step: float = 0.05,
    identity_context: Q4EvaluationIdentityContext,
    single_bomb_evaluator: Callable[..., SingleBombEvaluation] = (
        evaluate_single_bomb_strategy
    ),
) -> ThreeDroneEvaluation:
    """Q4 三无人机联合评估 (B1/B4 hardened).

    Args:
      candidate: 12-field ThreeDroneCandidate.
      sample_level: ∈ SAMPLE_GRADES.
      scan_step: > 0 严格 finite real number (非 bool).
      identity_context: 必填 keyword-only; 0 stub calls 前完整验证.
      single_bomb_evaluator: 注入 evaluator; 默认 evaluate_single_bomb_strategy
        仅在 production 中使用; 测试必须通过 dependency injection 替换.

    Two-Stage (B1):
      Stage A: prevalidation. invalid -> 0 evaluator calls, q4_evaluation_id == "".
      Stage B: 0 stub calls 之前完成 identity_context 严格校验, 生成
        q4_evaluation_id (lowercase 64 hex).
      Stage C: FY1 -> FY2 -> FY3 调用链. 每个 evaluator 正常返回必须满足
        Q2 return contract (B4); 异常 (Exception) -> 立即 raise
        Q4EvaluationSystemError. KeyboardInterrupt / SystemExit / GeneratorExit
        原样传播, 不包装.
      Stage D: 聚合. 任一 Q2 (valid=False, status="invalid") ->
        q4 valid=False, status="invalid", 保留 3 returns, union empty, total=0,
        q4_evaluation_id 仍为 lowercase 64 hex.
      Stage E: 否则 union / total. status="ok" if total>0 else "zero_union",
        q4_evaluation_id 仍为 lowercase 64 hex.
    """
    t0 = time.perf_counter()

    # Stage 0: sample_level / scan_step 校验 (mode 0: 错误即 ValueError)
    if sample_level not in SAMPLE_GRADES:
        raise ValueError(
            f"sample_level 必须 ∈ {list(SAMPLE_GRADES)}, 实际 {sample_level!r}"
        )
    if not _is_strictly_real_finite_number(scan_step):
        raise ValueError(f"scan_step 必须有限数值 (且非 bool), 实际 {scan_step!r}")
    if float(scan_step) <= 0:
        raise ValueError(f"scan_step 必须 > 0, 实际 {scan_step}")

    # Stage A: prevalidation (NO evaluator call, NO identity computation)
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

    # Stage B0: 完整验证 identity_context (B1/B3) — 任意不合规 ValueError,
    # 0 stub calls 之前
    _validate_normal_identity_context(
        identity_context,
        sample_level=sample_level,
        scan_step=float(scan_step),
    )

    # Stage B1: 在 0 stub calls 之前生成 q4_evaluation_id (B1)
    q4_id = compute_q4_evaluation_id(
        candidate,
        sample_level=sample_level,
        scan_step=float(scan_step),
        identity_context=identity_context,
    )

    # Stage C: FY1 -> FY2 -> FY3 evaluator calls
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
        except Exception as exc:
            # B4: 包装 Exception (非 BaseException). KeyboardInterrupt /
            # SystemExit / GeneratorExit 原样传播.
            raise Q4EvaluationSystemError(
                failing_drone_id=drone_id,
                attempted_single_bomb_calls=attempted,
                completed_single_bomb_calls=completed,
                completed_drone_ids=tuple(drone_ids),
                completed_evaluations=tuple(drone_evs),
                original_exception_type=type(exc).__name__,
                original_exception_message=str(exc),
            ) from exc
        # B4: 验证 Q2 返回 contract
        try:
            _validate_q2_return_contract(ev, drone_id=drone_id)
        except Q2ReturnContractError as contract_error:
            raise Q4EvaluationSystemError(
                failing_drone_id=drone_id,
                attempted_single_bomb_calls=attempted,
                completed_single_bomb_calls=completed,
                completed_drone_ids=tuple(drone_ids),
                completed_evaluations=tuple(drone_evs),
                original_exception_type="Q2ReturnContractError",
                original_exception_message=str(contract_error),
            ) from contract_error
        drone_evs.append(ev)
        drone_ids.append(drone_id)
        completed += 1

    # Stage D: 聚合 Q2 statuses
    any_invalid = any(
        ev.status == "invalid" for ev in drone_evs
    )
    if any_invalid:
        elapsed = time.perf_counter() - t0
        invalid_ids = [
            drone_ids[i] for i, ev in enumerate(drone_evs)
            if ev.status == "invalid"
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
            q4_evaluation_id=q4_id,
            attempted_single_bomb_calls=attempted,
            completed_single_bomb_calls=completed,
        )

    # Stage E: union / total
    union = union_intervals(
        *(ev.intervals for ev in drone_evs),
        epsilon=INTERVAL_EPSILON_S,
    )
    total = total_union_duration(union)
    if total > 0:
        status = "ok"
    else:
        status = "zero_union"

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
