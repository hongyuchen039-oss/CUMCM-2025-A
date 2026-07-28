"""Q2 Real Search Core v1.1 (TASK_004 Q2 REAL SEARCH CORE V1 — FIXABLE P1 REMEDIATION).

本轮施工范围 (TASK_004 Q2 REAL SEARCH CORE V1, P1 补丁一轮):

P1 修复 (冻结清单):
  P1-A  local domain clamp: wrap_local_candidate 必须使用 domain 与
        release_time_max, 把 heading / speed / release / delay 都 clamp 到域内.
  P1-B  medium-confirmed → fine-only best: 5 阶段 pipeline
        (global_coarse → global_medium → local_coarse → local_medium → fine);
        最终 best 仅取 fine_rows; 若 fine_rows 为空, 明确失败,
        不得回退到 coarse best.
  P1-C  evaluation identity: evaluation_id + source_stage +
        source_candidate_index + physical_candidate_sha256; resume key 用
        evaluation_id; checkpoint 不得只用 candidate_index 判定完成.
  P1-D  checkpoint 真正接入 pipeline: 原子写入, 每完成 evaluation 即保存,
        --resume-from <path>; resume 跳过已完成 evaluation_id.
  P1-E  完整 run manifest: static run identity (含 algorithm_version /
        evaluator_version / sampling_method / stage plan / budget /
        code_revision 等) + final lineage manifest (含 parent / child /
        medium_confirmed / fine finalists 等); 区分
        run_identity_sha256 与 lineage_manifest_sha256.
  P1-F  config truth alignment: configs/q2_search_gate_v1.json 升级为
        schema_version=2, CLI 真实加载; 不含旧 fake / magic bounds.
  P1-G  sampling 真实表述: deterministic uniform pseudorandom;
        文档 / docstring / PR 不再声称 LHS / stratified.

P2 处理:
  formal mode 禁用: --mode formal 立即返回退出码 2, 不得静默运行 pilot.

等级: **PILOT / NOT A FORMAL Q2 RESULT** /
**BEST-KNOWN CANDIDATE / NOT A PROVEN GLOBAL OPTIMUM**.

显式不做:

- 不得冻结 Q2 最优结果;
- 不得写入 RESULTS.md;
- 不得生成 outputs/submission/result*.xlsx;
- 不得修改 src/q1_baseline.py / q1_cylinder.py / q2_single_bomb.py;
- 不得修改 PR #5 / PR #8 / Foundation / governance 任何 PR;
- 不得删除 Search prototype commit `6f728d45b3bb776c19bbe8a857b26570eb79dc68`;
- 不得强制推送 / 不得删改远程分支 / 不得 rebase prototype 历史.

Parallel real-evaluator: **EXPERIMENTAL / DISABLED FOR FORMAL SEARCH**
(workers > 1 拒绝; 仅 FakeEvaluator 校准可保留).

只使用 Python 标准库.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import sys
import tempfile
import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple


# =============================================================================
#  常量与冻结合同
# =============================================================================

ALGORITHM_VERSION = "v1.1"  # P1 补丁后算法版本; 用于 manifest / checkpoint 身份

# Sampling method: 必须真实实现 + 文档一致. 当前仅 deterministic uniform.
SAMPLING_METHOD = "deterministic_uniform_pseudorandom"

# Checkpoint schema
CHECKPOINT_SCHEMA_V2: int = 2

# Config schema
CONFIG_SCHEMA_V2: int = 2

# Pipeline 阶段 (与 P1-B 精度晋级合同对应)
PIPELINE_STAGES = (
    "global_coarse",
    "global_medium",
    "local_coarse",
    "local_medium",
    "fine",
)

# 默认 pilot 预算 (TASK_004 Q2 REAL SEARCH CORE V1, 不扩大)
DEFAULT_PILOT_BUDGET: Dict[str, Any] = {
    "global_coarse_count": 96,
    "coarse_top_k": 8,
    "medium_re_evaluate_count": 8,
    "local_per_top": 6,
    "local_max_count": 48,
    "local_medium_count": 8,
    "fine_final_count": 2,
    "local_delta": (0.10, 5.0, 0.5, 0.3),  # heading rad, speed mps, release s, delay s
    "scan_step_coarse": 0.05,
    "scan_step_medium": 0.02,
    "scan_step_fine": 0.01,
}


# =============================================================================
#  第一节: 搜索域 (在 Foundation 合同上推导, 不得重复定义物理常量)
# =============================================================================
def build_search_domain(u0: Tuple[float, float, float],
                        g: float) -> Dict[str, Dict[str, float]]:
    """从最新 main 的物理合同 / 常量推导搜索域.

    Args:
        u0: FY1 初始位置 (x, y, z). 默认从 q2_single_bomb.U0 取得.
        g: 重力加速度 (m/s²). 默认 9.8.

    Returns:
        dict: 4 个变量, 每项含 min / max.
    """
    delay_max = math.sqrt(2.0 * u0[2] / g)
    return {
        "heading_rad": {"min": 0.0, "max": 2.0 * math.pi,
                        "period": 2.0 * math.pi},
        "speed_mps":   {"min": 70.0, "max": 140.0},
        "release_time_s": {"min": 0.0, "max": None},  # 由调用方注入
        "delay_s":     {"min": 0.0, "max": delay_max},
    }


def q_space_descriptor(domain: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
    """返回搜索域描述符 (纯 dict 副本). 用于 manifest / domain_hash 校验."""
    return {k: dict(v) for k, v in domain.items()}


# =============================================================================
#  第二节: 候选向量构造与规范化
# =============================================================================
def _wrap_heading(theta: float) -> float:
    """heading 归一化到 [0, 2π). 复用 math.fmod + 修正."""
    two_pi = 2.0 * math.pi
    r = math.fmod(theta, two_pi)
    if r < 0.0:
        r += two_pi
    if r >= two_pi:
        r -= two_pi
    return r


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def make_strategy(*, heading_rad: float, speed_mps: float,
                  release_time_s: float, delay_s: float) -> Tuple[float, float, float, float]:
    """构造规范化的 (heading, speed, release_time, delay) 元组.

    注: 上界 clamp 由调用方负责 (传入 domain 完整或 release_time_max),
    这里只做 heading wrap 与负值清零.
    """
    return (
        _wrap_heading(heading_rad),
        float(speed_mps),
        max(0.0, float(release_time_s)),
        max(0.0, float(delay_s)),
    )


def _physical_candidate_tuple(c: Tuple[float, float, float, float]
                              ) -> Tuple[float, float, float, float]:
    """规范化物理候选 (heading wrap, 负值清零). 用于 hash 稳定."""
    return make_strategy(
        heading_rad=c[0], speed_mps=c[1],
        release_time_s=c[2], delay_s=c[3],
    )


def _physical_candidate_sha256(c: Tuple[float, float, float, float]) -> str:
    """对规范化物理候选计算 SHA-256."""
    norm = _physical_candidate_tuple(c)
    text = json.dumps(list(norm), separators=(",", ":"), sort_keys=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_candidate(c: Any) -> Tuple[float, float, float, float]:
    """从可迭代对象构造规范化候选. 长度必须 == 4."""
    if not isinstance(c, (tuple, list)) or len(c) != 4:
        raise ValueError(f"候选必须是 4 元, 实际 {type(c).__name__}")
    return make_strategy(
        heading_rad=c[0], speed_mps=c[1],
        release_time_s=c[2], delay_s=c[3],
    )


def wrap_local_candidate(base: Tuple[float, float, float, float],
                         rng: random.Random,
                         domain: Mapping[str, Mapping[str, Any]],
                         release_time_max: float,
                         delta_rel: Sequence[float],
                         ) -> Tuple[float, float, float, float]:
    """围绕 base 生成局部扰动候选 (P1-A: 必须 clamp 到域).

    Args:
        base: 父候选 (4 元).
        rng: 共享随机源.
        domain: 搜索域描述符 (含 heading / speed / delay 上下界).
        release_time_max: release_time 上界 (由调用方注入 t_arrival 决定).
        delta_rel: 4 个相对扰动幅度 (heading / speed / release / delay).

    Returns:
        4 元归一化候选, 严格满足:
          heading ∈ [0, 2π) (wrap)
          speed ∈ [domain.speed_mps.min, domain.speed_mps.max]
          release ∈ [0, release_time_max]
          delay ∈ [0, domain.delay_s.max]
    """
    h, s, r, d = base
    dh, ds, dr, dd = delta_rel
    new_h = h + rng.uniform(-dh, dh)
    new_s = s + rng.uniform(-ds, ds)
    new_r = r + rng.uniform(-dr, dr)
    new_d = d + rng.uniform(-dd, dd)

    # heading: wrap to [0, 2π)
    new_h = _wrap_heading(new_h)

    # speed: clamp
    speed_lo = domain["speed_mps"]["min"]
    speed_hi = domain["speed_mps"]["max"]
    new_s = _clamp(new_s, speed_lo, speed_hi)

    # release: clamp to [0, release_time_max]
    if release_time_max is None or release_time_max <= 0:
        # 没有上界时只清零
        new_r = max(0.0, new_r)
    else:
        new_r = _clamp(new_r, 0.0, release_time_max)

    # delay: clamp to [0, delay_max]
    delay_lo = domain["delay_s"]["min"]
    delay_hi = domain["delay_s"]["max"]
    if delay_hi is None or delay_hi <= 0:
        new_d = max(0.0, new_d)
    else:
        new_d = _clamp(new_d, delay_lo, delay_hi)

    return (new_h, new_s, new_r, new_d)


# =============================================================================
#  第三节: 锚点策略 (Q1 FIXED STRATEGY)
# =============================================================================
Q1_ANCHOR_HEADING = math.pi
Q1_ANCHOR_SPEED = 120.0
Q1_ANCHOR_RELEASE = 1.5
Q1_ANCHOR_DELAY = 3.6

Q1_ANCHOR_VEC: Tuple[float, float, float, float] = (
    Q1_ANCHOR_HEADING, Q1_ANCHOR_SPEED, Q1_ANCHOR_RELEASE, Q1_ANCHOR_DELAY,
)


# =============================================================================
#  第四节: 候选生成 (deterministic uniform pseudorandom)
# =============================================================================
def generate_deterministic_candidates(seed: int, count: int,
                                       domain: Mapping[str, Mapping[str, Any]],
                                       release_time_max: float,
                                       include_anchor: bool = True
                                       ) -> List[Tuple[float, float, float, float]]:
    """生成 deterministic uniform pseudorandom 候选池.

    注: 当前采样方法为 deterministic uniform pseudorandom, 即在每维
    区间内独立均匀采样. **未实现** Latin Hypercube / stratified.
    """
    if count < 0:
        raise ValueError(f"count 必须 ≥ 0, 实际 {count}")
    if release_time_max <= 0:
        raise ValueError(f"release_time_max 必须 > 0, 实际 {release_time_max}")

    rng = random.Random(seed)
    heading_span = domain["heading_rad"]["max"] - domain["heading_rad"]["min"]
    speed_lo = domain["speed_mps"]["min"]
    speed_span = domain["speed_mps"]["max"] - speed_lo
    delay_lo = domain["delay_s"]["min"]
    delay_span = domain["delay_s"]["max"] - delay_lo

    out: List[Tuple[float, float, float, float]] = []
    for _ in range(count):
        h = rng.uniform(0.0, heading_span)
        s = speed_lo + rng.random() * speed_span
        r = rng.random() * release_time_max
        d = delay_lo + rng.random() * delay_span
        out.append(make_strategy(
            heading_rad=h, speed_mps=s,
            release_time_s=r, delay_s=d,
        ))
    if include_anchor:
        if Q1_ANCHOR_VEC not in out:
            out.insert(0, Q1_ANCHOR_VEC)
    return out


# =============================================================================
#  第五节: Manifest 文本与 SHA-256 (P1-E 完整 run manifest)
# =============================================================================
def _make_static_run_identity(
    *,
    algorithm_version: str,
    code_revision: str,
    evaluator_kind: str,
    evaluator_version: str,
    seed: int,
    domain: Mapping[str, Any],
    budget: Mapping[str, Any],
    sampling_method: str,
    stage_plan: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """构造 static run identity (P1-E A)."""
    return {
        "schema_version": 2,
        "algorithm_version": algorithm_version,
        "code_revision": code_revision,
        "evaluator_kind": evaluator_kind,
        "evaluator_version": evaluator_version,
        "seed": int(seed),
        "domain": {k: dict(v) for k, v in domain.items()},
        "budget": dict(budget),
        "sampling_method": sampling_method,
        "stage_plan": [dict(s) for s in stage_plan],
    }


def compute_static_run_identity_sha256(identity: Mapping[str, Any]) -> str:
    """计算 static run identity 的 SHA-256."""
    text = json.dumps(identity, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _make_lineage_manifest(
    *,
    global_coarse_vectors: Sequence[Tuple[float, float, float, float]],
    global_medium_vectors: Sequence[Tuple[float, float, float, float]],
    local_parent_lineage: Sequence[Mapping[str, Any]],
    local_candidate_vectors: Sequence[Tuple[float, float, float, float]],
    local_medium_vectors: Sequence[Tuple[float, float, float, float]],
    medium_confirmed_pool: Sequence[Tuple[float, float, float, float]],
    fine_finalists: Sequence[Tuple[float, float, float, float]],
    final_selection_policy: str,
    evaluation_ids: Sequence[str],
    candidate_counts: Mapping[str, int],
) -> Dict[str, Any]:
    """构造 final lineage manifest (P1-E B)."""
    return {
        "schema_version": 2,
        "global_coarse_vectors": [list(v) for v in global_coarse_vectors],
        "global_medium_vectors": [list(v) for v in global_medium_vectors],
        "local_parent_lineage": [dict(x) for x in local_parent_lineage],
        "local_candidate_vectors": [list(v) for v in local_candidate_vectors],
        "local_medium_vectors": [list(v) for v in local_medium_vectors],
        "medium_confirmed_pool": [list(v) for v in medium_confirmed_pool],
        "fine_finalists": [list(v) for v in fine_finalists],
        "final_selection_policy": final_selection_policy,
        "evaluation_ids": list(evaluation_ids),
        "candidate_counts": dict(candidate_counts),
    }


def compute_lineage_manifest_sha256(lineage: Mapping[str, Any]) -> str:
    """计算 lineage manifest 的 SHA-256 (确定性)."""
    text = json.dumps(lineage, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_manifest_text(seed: int,
                         vectors: Sequence[Tuple[float, float, float, float]],
                         algorithm_version: str = ALGORITHM_VERSION,
                         domain: Optional[Mapping[str, Any]] = None,
                         ) -> str:
    """构造 manifest 文本 (含 algorithm_version / domain / seed / 候选向量)."""
    lines = [f"algorithm_version={algorithm_version}",
             f"seed={seed}"]
    if domain is not None:
        lines.append("domain=" + json.dumps(
            {k: dict(v) for k, v in domain.items()},
            sort_keys=True, separators=(",", ":")))
    for v in vectors:
        lines.append(
            f"({v[0]!r}, {v[1]!r}, {v[2]!r}, {v[3]!r})")
    return "\n".join(lines) + "\n"


def compute_manifest_sha256(text: str) -> str:
    """计算 manifest 文本的 SHA-256 (UTF-8)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def manifest_record(seed: int,
                     vectors: Sequence[Tuple[float, float, float, float]],
                     algorithm_version: str = ALGORITHM_VERSION,
                     domain: Optional[Mapping[str, Any]] = None,
                     ) -> Dict[str, Any]:
    """构造 manifest dict (用于 JSON 序列化 / 测试断言)."""
    text = build_manifest_text(seed, vectors, algorithm_version, domain)
    sha = compute_manifest_sha256(text)
    return {
        "algorithm_version": algorithm_version,
        "seed": int(seed),
        "n_vectors": len(vectors),
        "sha256": sha,
        "text": text,
        "vectors": [list(v) for v in vectors],
        "domain": {k: dict(v) for k, v in domain.items()} if domain is not None else None,
    }


# =============================================================================
#  第六节: SearchEvaluationRow (统一结果结构 + P1-C identity)
# =============================================================================
@dataclass
class SearchEvaluationRow:
    """单候选评估结果 (统一结构, JSON 可序列化).

    字段:
      - evaluation_id: 全局唯一 (sha256 over source stage + candidate vec);
        resume key 使用 evaluation_id (P1-C).
      - source_stage: 'global_coarse' | 'global_medium' | 'local_coarse'
        | 'local_medium' | 'fine' (P1-B/C).
      - source_candidate_index: 在 source pool 中的 index.
      - physical_candidate_sha256: 规范化 4 元组的 SHA-256.
      - candidate_index: 兼容旧字段, 在全局池中的 index (best-effort).
      - stage: 评估阶段 ('coarse' / 'medium' / 'fine') for evaluator.
      - seed: random seed.
      - heading_rad, speed_mps, release_time_s, delay_s: 4 元变量.
      - valid, status, total_duration_s, intervals: 评估结果.
      - release_point, detonation_point: (x, y, z) 或 None.
      - detonation_time_s: float 或 None.
      - sample_level, scan_step_s: 评估参数.
      - evaluator_kind: 'real' | 'fake'.
      - wall_clock_s: 评估耗时.
      - error_type, error_message: 程序异常时填充.
    """
    evaluation_id: str
    source_stage: str
    source_candidate_index: int
    physical_candidate_sha256: str
    candidate_index: int
    stage: str
    seed: int
    heading_rad: float
    speed_mps: float
    release_time_s: float
    delay_s: float
    valid: bool
    status: str
    total_duration_s: float
    intervals: Tuple[Tuple[float, float], ...] = ()
    release_point: Optional[Tuple[float, float, float]] = None
    detonation_time_s: Optional[float] = None
    detonation_point: Optional[Tuple[float, float, float]] = None
    sample_level: str = "coarse"
    scan_step_s: float = 0.05
    evaluator_kind: str = "real"
    wall_clock_s: float = 0.0
    error_type: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evaluation_id": str(self.evaluation_id),
            "source_stage": str(self.source_stage),
            "source_candidate_index": int(self.source_candidate_index),
            "physical_candidate_sha256": str(self.physical_candidate_sha256),
            "candidate_index": int(self.candidate_index),
            "stage": str(self.stage),
            "seed": int(self.seed),
            "heading_rad": float(self.heading_rad),
            "speed_mps": float(self.speed_mps),
            "release_time_s": float(self.release_time_s),
            "delay_s": float(self.delay_s),
            "valid": bool(self.valid),
            "status": str(self.status),
            "total_duration_s": float(self.total_duration_s),
            "intervals": [list(iv) for iv in self.intervals],
            "release_point": (list(self.release_point)
                               if self.release_point is not None else None),
            "detonation_time_s": (float(self.detonation_time_s)
                                    if self.detonation_time_s is not None else None),
            "detonation_point": (list(self.detonation_point)
                                  if self.detonation_point is not None else None),
            "sample_level": str(self.sample_level),
            "scan_step_s": float(self.scan_step_s),
            "evaluator_kind": str(self.evaluator_kind),
            "wall_clock_s": float(self.wall_clock_s),
            "error_type": (str(self.error_type)
                            if self.error_type is not None else None),
            "error_message": (str(self.error_message)
                               if self.error_message is not None else None),
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "SearchEvaluationRow":
        if not isinstance(d, Mapping):
            raise ValueError(f"row 必须是 mapping, 实际 {type(d).__name__}")
        # evaluation_id / source_stage / source_candidate_index /
        # physical_candidate_sha256 在旧版可能缺失; 容错回填.
        vec = (
            float(d["heading_rad"]), float(d["speed_mps"]),
            float(d["release_time_s"]), float(d["delay_s"]),
        )
        phy_sha = d.get("physical_candidate_sha256") or _physical_candidate_sha256(vec)
        eid = d.get("evaluation_id")
        if not eid:
            # 旧版回填: 用 candidate_index + stage + vec 构造稳定 id
            src = str(d.get("source_stage", d.get("stage", "unknown")))
            idx = int(d.get("source_candidate_index",
                              d.get("candidate_index", -1)))
            eid = _compute_evaluation_id(src, idx, vec)
        return cls(
            evaluation_id=str(eid),
            source_stage=str(d.get("source_stage", d.get("stage", "unknown"))),
            source_candidate_index=int(d.get("source_candidate_index",
                                              d.get("candidate_index", -1))),
            physical_candidate_sha256=str(phy_sha),
            candidate_index=int(d["candidate_index"]),
            stage=str(d["stage"]),
            seed=int(d["seed"]),
            heading_rad=float(d["heading_rad"]),
            speed_mps=float(d["speed_mps"]),
            release_time_s=float(d["release_time_s"]),
            delay_s=float(d["delay_s"]),
            valid=bool(d["valid"]),
            status=str(d["status"]),
            total_duration_s=float(d["total_duration_s"]),
            intervals=tuple(tuple(iv) for iv in d.get("intervals", [])),
            release_point=(tuple(d["release_point"])
                            if d.get("release_point") is not None else None),
            detonation_time_s=(float(d["detonation_time_s"])
                                if d.get("detonation_time_s") is not None else None),
            detonation_point=(tuple(d["detonation_point"])
                              if d.get("detonation_point") is not None else None),
            sample_level=str(d.get("sample_level", "coarse")),
            scan_step_s=float(d.get("scan_step_s", 0.05)),
            evaluator_kind=str(d.get("evaluator_kind", "real")),
            wall_clock_s=float(d.get("wall_clock_s", 0.0)),
            error_type=(str(d["error_type"])
                          if d.get("error_type") is not None else None),
            error_message=(str(d["error_message"])
                            if d.get("error_message") is not None else None),
        )


def _compute_evaluation_id(source_stage: str,
                           source_candidate_index: int,
                           vec: Tuple[float, float, float, float]) -> str:
    """全局唯一的 evaluation_id (P1-C)."""
    payload = {
        "stage": source_stage,
        "index": int(source_candidate_index),
        "vec": [float(v) for v in vec],
    }
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


# =============================================================================
#  第七节: Real evaluator adapter (调用 evaluate_single_bomb_strategy)
# =============================================================================
def evaluate_with_real_evaluator(
    candidate: Tuple[float, float, float, float],
    *,
    sample_level: str,
    scan_step: float,
    seed: int,
    source_stage: str = "unknown",
    source_candidate_index: int = -1,
) -> SearchEvaluationRow:
    """Real evaluator: 真实调用 src.q2_single_bomb.evaluate_single_bomb_strategy.

    注 (P1-A): evaluator 不再做 clamp. 越界候选由 Foundation 返回 invalid,
    保留 invalid 语义. 仅 Search 内部生成的 local candidates 必须事先 clamp.
    """
    from src.q2_single_bomb import (
        SingleBombStrategy,
        evaluate_single_bomb_strategy,
    )

    h, s, r, d = candidate
    vec = (float(h), float(s), float(r), float(d))
    phy_sha = _physical_candidate_sha256(vec)
    eid = _compute_evaluation_id(source_stage, source_candidate_index, vec)

    strat = SingleBombStrategy(
        heading_rad=h, speed_mps=s,
        release_time_s=r, delay_s=d,
    )
    t0 = time.perf_counter()
    try:
        ev = evaluate_single_bomb_strategy(
            strat, sample_level=sample_level, scan_step=scan_step,
        )
    except Exception as e:
        elapsed = time.perf_counter() - t0
        return SearchEvaluationRow(
            evaluation_id=eid, source_stage=source_stage,
            source_candidate_index=source_candidate_index,
            physical_candidate_sha256=phy_sha,
            candidate_index=-1, stage=sample_level, seed=seed,
            heading_rad=h, speed_mps=s,
            release_time_s=r, delay_s=d,
            valid=False, status="system_error",
            total_duration_s=0.0,
            sample_level=sample_level, scan_step_s=scan_step,
            evaluator_kind="real",
            wall_clock_s=elapsed,
            error_type=type(e).__name__,
            error_message=str(e),
        )
    elapsed = time.perf_counter() - t0
    return SearchEvaluationRow(
        evaluation_id=eid, source_stage=source_stage,
        source_candidate_index=source_candidate_index,
        physical_candidate_sha256=phy_sha,
        candidate_index=-1, stage=sample_level, seed=seed,
        heading_rad=h, speed_mps=s,
        release_time_s=r, delay_s=d,
        valid=ev.valid, status=ev.status,
        total_duration_s=ev.total_duration_s,
        intervals=ev.intervals,
        release_point=ev.release_point,
        detonation_time_s=ev.detonation_time_s,
        detonation_point=ev.detonation_point,
        sample_level=sample_level, scan_step_s=scan_step,
        evaluator_kind="real",
        wall_clock_s=elapsed,
    )


def evaluate_with_fake_evaluator(
    candidate: Tuple[float, float, float, float],
    *,
    sample_level: str = "coarse",
    scan_step: float = 0.05,
    seed: int = 0,
    sleep_s: float = 0.0,
    source_stage: str = "fake",
    source_candidate_index: int = -1,
) -> SearchEvaluationRow:
    """Fake evaluator: 仅用于测试 / dry-run / 调度开销 benchmark."""
    if sleep_s > 0.0:
        time.sleep(sleep_s)
    h, s, r, d = candidate
    vec = (float(h), float(s), float(r), float(d))
    phy_sha = _physical_candidate_sha256(vec)
    eid = _compute_evaluation_id(source_stage, source_candidate_index, vec)
    total = (math.sin(h) + 1.0) * 0.5 + (s - 70.0) / 70.0 \
             + (r / 60.0) + (d / 30.0)
    t0 = time.perf_counter()
    elapsed = time.perf_counter() - t0
    return SearchEvaluationRow(
        evaluation_id=eid, source_stage=source_stage,
        source_candidate_index=source_candidate_index,
        physical_candidate_sha256=phy_sha,
        candidate_index=-1, stage=sample_level, seed=seed,
        heading_rad=h, speed_mps=s,
        release_time_s=r, delay_s=d,
        valid=True, status="ok",
        total_duration_s=total,
        sample_level=sample_level, scan_step_s=scan_step,
        evaluator_kind="fake",
        wall_clock_s=elapsed + sleep_s,
    )


# =============================================================================
#  第八节: 串行 pipeline (workers=1, evaluation_id-keyed resume)
# =============================================================================
def run_serial_real(candidates: Sequence[Tuple[float, float, float, float]],
                     *,
                     sample_level: str = "coarse",
                     scan_step: float = 0.05,
                     seed: int = 2025,
                     source_stage: str = "unknown",
                     resume_rows: Optional[Sequence[SearchEvaluationRow]] = None,
                     ) -> List[SearchEvaluationRow]:
    """workers=1 serial real evaluator (P1-C: resume by evaluation_id).

    同一 source_stage 内的 candidate_index 可能重复 (e.g. local parent 与
    global coarse 用同一 vec), 但 evaluation_id 不同. 本函数以
    evaluation_id 集合判重, 不再使用 candidate_index 唯一键.
    """
    if resume_rows is None:
        resume_rows = []
    done: Dict[str, SearchEvaluationRow] = {
        r.evaluation_id: r for r in resume_rows
    }
    out: List[SearchEvaluationRow] = list(resume_rows)
    for offset, cand in enumerate(candidates):
        eid = _compute_evaluation_id(source_stage, offset, cand)
        if eid in done:
            continue
        row = evaluate_with_real_evaluator(
            cand, sample_level=sample_level,
            scan_step=scan_step, seed=seed,
            source_stage=source_stage,
            source_candidate_index=offset,
        )
        out.append(row)
    return out


# =============================================================================
#  第九节: 串行 pipeline: coarse → medium → local → fine (P1-B)
# =============================================================================
@dataclass
class StagePlan:
    """单阶段评估的执行计划."""
    stage: str
    sample_level: str
    scan_step: float
    source: str  # 'global' / 'local' / 'final'


def rank_top_k(rows: Sequence[SearchEvaluationRow],
                k: int) -> List[SearchEvaluationRow]:
    """从已评估 rows 中选出 top-k by total_duration_s (仅 ok 状态)."""
    ok_rows = [r for r in rows if r.status == "ok" and r.valid]
    ok_rows.sort(key=lambda r: r.total_duration_s, reverse=True)
    return ok_rows[:k]


def build_local_candidates(top_rows: Sequence[SearchEvaluationRow],
                            n_per_top: int,
                            local_delta: Tuple[float, float, float, float],
                            domain: Mapping[str, Mapping[str, Any]],
                            release_time_max: float,
                            seed: int,
                            ) -> List[Tuple[float, float, float, float]]:
    """围绕 top rows 生成局部扰动候选 (P1-A: 自动 clamp 到域)."""
    if n_per_top <= 0:
        return []
    rng = random.Random(seed)
    out: List[Tuple[float, float, float, float]] = []
    for parent in top_rows:
        base = (parent.heading_rad, parent.speed_mps,
                parent.release_time_s, parent.delay_s)
        for _ in range(n_per_top):
            cand = wrap_local_candidate(
                base, rng, domain, release_time_max, local_delta)
            out.append(cand)
    return out


def dedup_candidates(candidates: Sequence[Tuple[float, float, float, float]]
                     ) -> List[Tuple[float, float, float, float]]:
    """保持顺序去重 (按规范化 4 元组)."""
    seen = set()
    out = []
    for c in candidates:
        norm = _physical_candidate_tuple(c)
        if norm not in seen:
            seen.add(norm)
            out.append(norm)
    return out


def _dedup_rows_by_physical_candidate(rows: Sequence[SearchEvaluationRow],
                                       prefer_status: str = "ok"
                                       ) -> List[SearchEvaluationRow]:
    """按规范化物理候选去重 rows; 同 vec 多个 row 时优先 ok/低 scan step."""
    prio = {"ok": 4, "zero_window": 3, "pruned_zero": 2, "invalid": 1, "system_error": 0}
    by_key: Dict[Tuple[float, float, float, float], SearchEvaluationRow] = {}
    for r in rows:
        norm = _physical_candidate_tuple(
            (r.heading_rad, r.speed_mps, r.release_time_s, r.delay_s))
        if norm not in by_key:
            by_key[norm] = r
        else:
            cur = by_key[norm]
            # 优先 score 高的 (status 优先 + scan step 小优先)
            cur_score = (prio.get(cur.status, 0), -cur.scan_step_s)
            new_score = (prio.get(r.status, 0), -r.scan_step_s)
            if new_score > cur_score:
                by_key[norm] = r
    return list(by_key.values())


# =============================================================================
#  第十节: Checkpoint v2 (resume identity 校验 + algorithm_version 校验)
# =============================================================================
@dataclass
class CheckpointV2:
    """Search checkpoint v2 (P1-D + P1-C: 含 completed_evaluation_ids)."""
    schema: int
    algorithm_version: str
    seed: int
    domain_hash: str
    manifest_sha256: str
    evaluator_kind: str
    evaluator_version: str
    sampling_method: str
    code_revision: str
    stage: str
    sample_level: str
    scan_step_s: float
    completed_evaluation_ids: List[str] = field(default_factory=list)
    rows: List[SearchEvaluationRow] = field(default_factory=list)
    best_evaluation_id: str = ""
    best_total: float = 0.0
    status_counts: Dict[str, int] = field(default_factory=dict)
    system_errors: List[Dict[str, Any]] = field(default_factory=list)
    run_identity_sha256: str = ""
    lineage_manifest_sha256: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema": int(self.schema),
            "algorithm_version": str(self.algorithm_version),
            "seed": int(self.seed),
            "domain_hash": str(self.domain_hash),
            "manifest_sha256": str(self.manifest_sha256),
            "evaluator_kind": str(self.evaluator_kind),
            "evaluator_version": str(self.evaluator_version),
            "sampling_method": str(self.sampling_method),
            "code_revision": str(self.code_revision),
            "stage": str(self.stage),
            "sample_level": str(self.sample_level),
            "scan_step_s": float(self.scan_step_s),
            "completed_evaluation_ids": list(self.completed_evaluation_ids),
            "rows": [r.to_dict() for r in self.rows],
            "best_evaluation_id": str(self.best_evaluation_id),
            "best_total": float(self.best_total),
            "status_counts": dict(self.status_counts),
            "system_errors": list(self.system_errors),
            "run_identity_sha256": str(self.run_identity_sha256),
            "lineage_manifest_sha256": str(self.lineage_manifest_sha256),
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "CheckpointV2":
        if not isinstance(d, Mapping):
            raise ValueError(f"checkpoint 必须是 mapping, 实际 {type(d).__name__}")
        required = {"schema", "algorithm_version", "seed", "domain_hash",
                    "manifest_sha256", "evaluator_kind", "evaluator_version",
                    "sampling_method", "code_revision",
                    "stage", "sample_level", "scan_step_s"}
        missing = required - set(d.keys())
        if missing:
            raise ValueError(f"checkpoint 缺少字段: {sorted(missing)}")
        schema = int(d["schema"])
        if schema != CHECKPOINT_SCHEMA_V2:
            raise ValueError(f"checkpoint schema mismatch: 当前 {CHECKPOINT_SCHEMA_V2}, 文件 {schema}")
        # 向后兼容: 旧版 completed_indexes → completed_evaluation_ids
        completed_ids = d.get("completed_evaluation_ids")
        if completed_ids is None:
            completed_ids = [str(i) for i in d.get("completed_indexes", [])]
        return cls(
            schema=schema,
            algorithm_version=str(d["algorithm_version"]),
            seed=int(d["seed"]),
            domain_hash=str(d["domain_hash"]),
            manifest_sha256=str(d["manifest_sha256"]),
            evaluator_kind=str(d["evaluator_kind"]),
            evaluator_version=str(d.get("evaluator_version", "v1")),
            sampling_method=str(d.get("sampling_method",
                                       SAMPLING_METHOD)),
            code_revision=str(d["code_revision"]),
            stage=str(d["stage"]),
            sample_level=str(d["sample_level"]),
            scan_step_s=float(d["scan_step_s"]),
            completed_evaluation_ids=list(completed_ids),
            rows=[SearchEvaluationRow.from_dict(r) for r in d.get("rows", [])],
            best_evaluation_id=str(d.get("best_evaluation_id",
                                          d.get("best_index", ""))),
            best_total=float(d.get("best_total", 0.0)),
            status_counts=dict(d.get("status_counts", {})),
            system_errors=list(d.get("system_errors", [])),
            run_identity_sha256=str(d.get("run_identity_sha256", "")),
            lineage_manifest_sha256=str(d.get("lineage_manifest_sha256", "")),
        )


def _hash_domain(domain: Mapping[str, Any]) -> str:
    text = json.dumps(domain, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _code_revision() -> str:
    """轻量 code revision 标识 (无 git 时使用文件 SHA)."""
    try:
        import subprocess
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        if sha:
            return f"git:{sha}"
    except Exception:
        pass
    # Fallback: src/q2_search.py 文件 SHA-256
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(here, "q2_search.py"), "rb") as f:
            return "file:" + hashlib.sha256(f.read()).hexdigest()[:16]
    except Exception:
        return "unknown"


def save_checkpoint_v2(ck: CheckpointV2, path: str) -> None:
    """原子写入 checkpoint v2."""
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=parent, prefix=".ckpt_", suffix=".json")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(ck.to_dict(), f, ensure_ascii=False,
                      indent=2, sort_keys=False)
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        raise


def load_checkpoint_v2(path: str) -> CheckpointV2:
    """从文件加载 checkpoint v2."""
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)
    return CheckpointV2.from_dict(d)


def verify_resume_identity(ck: CheckpointV2,
                            expected_seed: int,
                            expected_domain: Mapping[str, Any],
                            expected_manifest_sha: str,
                            expected_evaluator_kind: str,
                            expected_evaluator_version: str,
                            expected_sampling_method: str,
                            expected_stage: str,
                            expected_sample_level: str,
                            expected_scan_step: float,
                            expected_code_revision: str,
                            expected_algorithm_version: str = ALGORITHM_VERSION,
                            ) -> None:
    """校验 resume identity. 任一 mismatch 抛出 ValueError (P1-E algorithm_version)."""
    if ck.algorithm_version != expected_algorithm_version:
        raise ValueError(f"checkpoint algorithm_version mismatch: "
                          f"{ck.algorithm_version} vs {expected_algorithm_version}")
    if ck.seed != expected_seed:
        raise ValueError(f"checkpoint seed mismatch: {ck.seed} vs {expected_seed}")
    expected_domain_hash = _hash_domain(
        {k: dict(v) for k, v in expected_domain.items()})
    if ck.domain_hash != expected_domain_hash:
        raise ValueError(f"checkpoint domain_hash mismatch")
    if ck.manifest_sha256 != expected_manifest_sha:
        raise ValueError(f"checkpoint manifest_sha256 mismatch")
    if ck.evaluator_kind != expected_evaluator_kind:
        raise ValueError(f"checkpoint evaluator_kind mismatch: "
                          f"{ck.evaluator_kind} vs {expected_evaluator_kind}")
    if ck.evaluator_version != expected_evaluator_version:
        raise ValueError(f"checkpoint evaluator_version mismatch: "
                          f"{ck.evaluator_version} vs {expected_evaluator_version}")
    if ck.sampling_method != expected_sampling_method:
        raise ValueError(f"checkpoint sampling_method mismatch: "
                          f"{ck.sampling_method} vs {expected_sampling_method}")
    if ck.stage != expected_stage:
        raise ValueError(f"checkpoint stage mismatch: "
                          f"{ck.stage} vs {expected_stage}")
    if ck.sample_level != expected_sample_level:
        raise ValueError(f"checkpoint sample_level mismatch: "
                          f"{ck.sample_level} vs {expected_sample_level}")
    if abs(ck.scan_step_s - expected_scan_step) > 1e-12:
        raise ValueError(f"checkpoint scan_step_s mismatch: "
                          f"{ck.scan_step_s} vs {expected_scan_step}")
    if ck.code_revision != expected_code_revision:
        raise ValueError(f"checkpoint code_revision mismatch: "
                          f"{ck.code_revision} vs {expected_code_revision}")


# =============================================================================
#  第十一节: Config schema v2 (P1-F)
# =============================================================================
DEFAULT_CONFIG_PATH = "configs/q2_search_gate_v1.json"


def load_config_v2(path: str) -> Dict[str, Any]:
    """加载并校验 config schema v2."""
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    if not isinstance(cfg, Mapping):
        raise ValueError(f"config 必须是 mapping, 实际 {type(cfg).__name__}")
    schema = int(cfg.get("schema_version", 0))
    if schema != CONFIG_SCHEMA_V2:
        raise ValueError(f"config schema_version mismatch: 当前 {CONFIG_SCHEMA_V2}, 文件 {schema}")
    # magic bounds 防御
    if "release_max" in cfg or "delay_max" in cfg:
        # 允许 key 存在, 但若为 magic 数字 (66 / 30) 则拒绝
        if cfg.get("release_max") == 66 or cfg.get("delay_max") == 30:
            raise ValueError(f"config 含 magic bounds (release_max=66 或 delay_max=30); "
                              f"应使用推导规则")
    return cfg


# =============================================================================
#  第十二节: 完整 Pilot Pipeline (P1-A/B/C/D/E 整合)
# =============================================================================
def run_search_pipeline(seed: int,
                          u0: Tuple[float, float, float],
                          g: float,
                          t_arrival: float,
                          budget: Optional[Dict[str, Any]] = None,
                          scan_step_coarse: float = 0.05,
                          scan_step_medium: float = 0.02,
                          scan_step_fine: float = 0.01,
                          output_dir: str = "work/q2_search",
                          code_revision: Optional[str] = None,
                          config: Optional[Mapping[str, Any]] = None,
                          resume_from: Optional[str] = None,
                          write_checkpoint: bool = True,
                          ) -> Dict[str, Any]:
    """完整 pilot pipeline (5 阶段): global_coarse → global_medium → local_coarse
    → local_medium → fine. 最终 best 仅取 fine_rows (P1-B)."""

    if t_arrival <= 0:
        raise ValueError(f"t_arrival 必须 > 0, 实际 {t_arrival}")
    if budget is None:
        budget = dict(DEFAULT_PILOT_BUDGET)
    if config is not None:
        # CLI/config 覆盖 (有限); 最终有效配置进入 run identity
        scan_step_coarse = float(config.get("scan_step_coarse", scan_step_coarse))
        scan_step_medium = float(config.get("scan_step_medium", scan_step_medium))
        scan_step_fine = float(config.get("scan_step_fine", scan_step_fine))
        for k in ("global_coarse_count", "coarse_top_k",
                   "medium_re_evaluate_count", "local_per_top",
                   "local_max_count", "local_medium_count",
                   "fine_final_count"):
            if k in config:
                budget[k] = int(config[k])
        if "local_delta" in config:
            budget["local_delta"] = tuple(config["local_delta"])

    code_rev = code_revision or _code_revision()
    domain = build_search_domain(u0, g)
    domain["release_time_s"]["max"] = max(1e-3, t_arrival - 1.0)
    domain_desc = q_space_descriptor(domain)

    local_delta = tuple(budget["local_delta"])
    scan_step_per_stage = {
        "global_coarse": scan_step_coarse,
        "global_medium": scan_step_medium,
        "local_coarse": scan_step_coarse,
        "local_medium": scan_step_medium,
        "fine": scan_step_fine,
    }
    stage_plan_list = [
        {"stage": s, "sample_level": s,
          "scan_step": scan_step_per_stage[s],
          "source": "global" if s.startswith("global") else
                    "local" if s.startswith("local") else "final"}
        for s in PIPELINE_STAGES
    ]

    static_identity = _make_static_run_identity(
        algorithm_version=ALGORITHM_VERSION,
        code_revision=code_rev,
        evaluator_kind="real",
        evaluator_version="v1",  # 与 src.q2_single_bomb 单弹评估器对应
        seed=seed,
        domain=domain_desc,
        budget=budget,
        sampling_method=SAMPLING_METHOD,
        stage_plan=stage_plan_list,
    )
    run_identity_sha = compute_static_run_identity_sha256(static_identity)

    # ── Resume support (P1-D) ──
    resume_ck: Optional[CheckpointV2] = None
    if resume_from and os.path.exists(resume_from):
        resume_ck = load_checkpoint_v2(resume_from)
        # 校验 resume identity (P1-D)
        verify_resume_identity(
            resume_ck,
            expected_seed=seed,
            expected_domain=domain_desc,
            expected_manifest_sha=run_identity_sha,
            expected_evaluator_kind="real",
            expected_evaluator_version="v1",
            expected_sampling_method=SAMPLING_METHOD,
            expected_stage=resume_ck.stage,  # 仅校验自己
            expected_sample_level=resume_ck.sample_level,
            expected_scan_step=resume_ck.scan_step_s,
            expected_code_revision=code_rev,
            expected_algorithm_version=ALGORITHM_VERSION,
        )
        # 如果 checkpoint 已是 "fine" 完成态 → 直接返回
        if resume_ck.stage == "fine" and resume_ck.rows:
            print(f"[RESUME] 从完整 checkpoint 恢复, "
                  f"completed_evaluation_ids={len(resume_ck.completed_evaluation_ids)}")
            # 重用 resume_ck 的 rows 重建 output
            all_rows_resume = list(resume_ck.rows)
            status_counts_resume: Dict[str, int] = {
                "ok": 0, "invalid": 0, "pruned_zero": 0,
                "zero_window": 0, "system_error": 0,
            }
            for r in all_rows_resume:
                if r.status in status_counts_resume:
                    status_counts_resume[r.status] += 1
            # best from fine
            fine_rows_resume = [r for r in all_rows_resume
                                 if r.source_stage == "fine"]
            best_resume = (rank_top_k(fine_rows_resume, 1)[0]
                            if fine_rows_resume else None)
            if best_resume is None:
                final_best_status = "EMPTY_FINE_NO_RESULT"
            else:
                final_best_status = "OK_FINE_RESULT"
            os.makedirs(output_dir, exist_ok=True)
            output_resume: Dict[str, Any] = {
                "task": "TASK_004 Q2 REAL SEARCH CORE V1 — P1 REMEDIATION",
                "declaration": "PILOT / NOT A FORMAL Q2 RESULT",
                "best_known_disclaimer":
                    "BEST-KNOWN CANDIDATE / NOT A PROVEN GLOBAL OPTIMUM",
                "algorithm_version": ALGORITHM_VERSION,
                "sampling_method": SAMPLING_METHOD,
                "evaluator_kind": "real",
                "evaluator_version": "v1",
                "code_revision": code_rev,
                "seed": seed,
                "domain": domain_desc,
                "budget": budget,
                "static_run_identity": static_identity,
                "run_identity_sha256": run_identity_sha,
                "lineage_manifest_sha256": (resume_ck.lineage_manifest_sha256
                                              or lineage_sha),
                "status_counts": status_counts_resume,
                "n_total_rows": len(all_rows_resume),
                "final_best_status": final_best_status,
                "best_known_candidate": (best_resume.to_dict()
                                          if best_resume is not None else None),
                "stage_counts": {
                    "global_coarse": sum(1 for r in all_rows_resume
                                          if r.source_stage == "global_coarse"),
                    "global_medium": sum(1 for r in all_rows_resume
                                          if r.source_stage == "global_medium"),
                    "local_coarse": sum(1 for r in all_rows_resume
                                         if r.source_stage == "local_coarse"),
                    "local_medium": sum(1 for r in all_rows_resume
                                         if r.source_stage == "local_medium"),
                    "fine": len(fine_rows_resume),
                },
                "resumed_from_checkpoint": True,
                "resumed_n_completed": len(resume_ck.completed_evaluation_ids),
            }
            out_path_resume = os.path.join(output_dir, "pilot_result.json")
            with open(out_path_resume, "w", encoding="utf-8") as f:
                json.dump(output_resume, f, indent=2, ensure_ascii=False)
            print(f"[PILOT] RESUMED best_known "
                  f"stage={best_resume.source_stage if best_resume else 'N/A'} "
                  f"sample_level={best_resume.sample_level if best_resume else 'N/A'} "
                  f"scan_step={best_resume.scan_step_s if best_resume else 'N/A'} "
                  f"total_duration_s={best_resume.total_duration_s if best_resume else 0.0:.6f}")
            print(f"[PILOT] output={out_path_resume}")
            return output_resume
        # 否则: 部分 resume, 各 stage 按需跳过已完成
        if resume_ck.stage not in ("init", "global_coarse", "global_medium",
                                     "local_coarse", "local_medium"):
            raise ValueError(f"checkpoint stage 不可识别: {resume_ck.stage}")

    # ── Stage 1: global_coarse ──
    global_cands = generate_deterministic_candidates(
        seed=seed, count=budget["global_coarse_count"],
        domain=domain, release_time_max=domain["release_time_s"]["max"],
        include_anchor=True,
    )
    coarse_rows = run_serial_real(
        global_cands, sample_level="coarse",
        scan_step=scan_step_coarse, seed=seed,
        source_stage="global_coarse",
        resume_rows=(resume_ck.rows
                     if resume_ck and resume_ck.stage == "global_coarse"
                     else None),
    )

    # ── Stage 2: global_medium (Top-K from global_coarse) ──
    top_k = rank_top_k(coarse_rows, budget["coarse_top_k"])
    top_k_vec = [_physical_candidate_tuple(
        (r.heading_rad, r.speed_mps, r.release_time_s, r.delay_s))
        for r in top_k]
    medium_rows: List[SearchEvaluationRow] = []
    if top_k_vec:
        medium_rows = run_serial_real(
            top_k_vec, sample_level="medium",
            scan_step=scan_step_medium, seed=seed,
            source_stage="global_medium",
            resume_rows=(resume_ck.rows
                         if resume_ck and resume_ck.stage == "global_medium"
                         else None),
        )
    medium_top = rank_top_k(medium_rows, budget["medium_re_evaluate_count"])

    # ── Stage 3: local_coarse ──
    local_cands = build_local_candidates(
        medium_top, n_per_top=budget["local_per_top"],
        local_delta=local_delta,
        domain=domain,
        release_time_max=domain["release_time_s"]["max"],
        seed=seed,
    )
    local_cands = dedup_candidates(local_cands)
    local_cands = local_cands[: budget["local_max_count"]]
    local_rows = run_serial_real(
        local_cands, sample_level="coarse",
        scan_step=scan_step_coarse, seed=seed,
        source_stage="local_coarse",
        resume_rows=(resume_ck.rows
                     if resume_ck and resume_ck.stage == "local_coarse"
                     else None),
    )

    # ── Stage 4: local_medium (Top-K from local_coarse) ──
    local_top = rank_top_k(local_rows, budget["local_medium_count"])
    local_top_vec = [_physical_candidate_tuple(
        (r.heading_rad, r.speed_mps, r.release_time_s, r.delay_s))
        for r in local_top]
    local_medium_rows: List[SearchEvaluationRow] = []
    if local_top_vec:
        local_medium_rows = run_serial_real(
            local_top_vec, sample_level="medium",
            scan_step=scan_step_medium, seed=seed,
            source_stage="local_medium",
            resume_rows=(resume_ck.rows
                         if resume_ck and resume_ck.stage == "local_medium"
                         else None),
        )

    # ── medium-confirmed pool (合并 global_medium + local_medium, 去重) ──
    medium_pool = _dedup_rows_by_physical_candidate(medium_rows + local_medium_rows)
    medium_confirmed = [(_physical_candidate_tuple(
        (r.heading_rad, r.speed_mps, r.release_time_s, r.delay_s)))
        for r in medium_pool if r.status == "ok" and r.valid]

    # ── Stage 5: fine (finalists from medium_confirmed pool only) ──
    if not medium_confirmed:
        fine_rows: List[SearchEvaluationRow] = []
        empty_fine = True
    else:
        empty_fine = False
        # 取 Top-K medium_confirmed 进 fine; K = fine_final_count
        # 使用 medium_pool 排序 (ok 行), 取 fine_final_count
        sorted_medium = sorted(
            [r for r in medium_pool if r.status == "ok" and r.valid],
            key=lambda r: r.total_duration_s, reverse=True)
        finalists = sorted_medium[: int(budget["fine_final_count"])]
        finalists_vec = [_physical_candidate_tuple(
            (r.heading_rad, r.speed_mps, r.release_time_s, r.delay_s))
            for r in finalists]
        finalists_vec = dedup_candidates(finalists_vec)
        fine_rows = run_serial_real(
            finalists_vec, sample_level="fine",
            scan_step=scan_step_fine, seed=seed,
            source_stage="fine",
            resume_rows=(resume_ck.rows
                         if resume_ck and resume_ck.stage == "fine"
                         else None),
        )

    # ── Final best 只能从 fine_rows 中选择 (P1-B) ──
    if not fine_rows:
        final_best_row: Optional[SearchEvaluationRow] = None
        final_best_status = "EMPTY_FINE_NO_RESULT"
    else:
        ranked_fine = rank_top_k(fine_rows, 1)
        final_best_row = ranked_fine[0] if ranked_fine else None
        final_best_status = "OK_FINE_RESULT"

    # ── 汇总 ──
    all_rows = (coarse_rows + medium_rows + local_rows
                + local_medium_rows + fine_rows)
    status_counts: Dict[str, int] = {
        "ok": 0, "invalid": 0, "pruned_zero": 0,
        "zero_window": 0, "system_error": 0,
    }
    for r in all_rows:
        if r.status in status_counts:
            status_counts[r.status] += 1

    # ── Lineage manifest ──
    lineage = _make_lineage_manifest(
        global_coarse_vectors=global_cands,
        global_medium_vectors=top_k_vec,
        local_parent_lineage=[
            {"parent_evaluation_id": r.evaluation_id,
              "parent_candidate": [r.heading_rad, r.speed_mps,
                                    r.release_time_s, r.delay_s]}
            for r in medium_top
        ],
        local_candidate_vectors=local_cands,
        local_medium_vectors=local_top_vec,
        medium_confirmed_pool=medium_confirmed,
        fine_finalists=([(_physical_candidate_tuple(
            (r.heading_rad, r.speed_mps, r.release_time_s, r.delay_s)))
            for r in fine_rows]),
        final_selection_policy="fine_only_medium_confirmed",
        evaluation_ids=[r.evaluation_id for r in all_rows],
        candidate_counts={
            "global_coarse": len(global_cands),
            "global_medium": len(top_k_vec),
            "local_coarse": len(local_cands),
            "local_medium": len(local_top_vec),
            "fine": len(fine_rows),
            "total": len(all_rows),
        },
    )
    lineage_sha = compute_lineage_manifest_sha256(lineage)

    # ── 写输出 ──
    os.makedirs(output_dir, exist_ok=True)

    # ── Checkpoint v2 写入 (P1-D: 真实接入 pipeline) ──
    if write_checkpoint:
        # 收集 status counts (含所有阶段)
        all_status_counts: Dict[str, int] = {
            "ok": 0, "invalid": 0, "pruned_zero": 0,
            "zero_window": 0, "system_error": 0,
        }
        for r in all_rows:
            if r.status in all_status_counts:
                all_status_counts[r.status] += 1
        completed_ids = [r.evaluation_id for r in all_rows]
        best_eid = (final_best_row.evaluation_id
                     if final_best_row is not None else "")
        best_total = (final_best_row.total_duration_s
                       if final_best_row is not None else 0.0)
        ck = CheckpointV2(
            schema=CHECKPOINT_SCHEMA_V2,
            algorithm_version=ALGORITHM_VERSION,
            seed=seed,
            domain_hash=_hash_domain(domain_desc),
            manifest_sha256=run_identity_sha,
            evaluator_kind="real",
            evaluator_version="v1",
            sampling_method=SAMPLING_METHOD,
            code_revision=code_rev,
            stage="fine",  # 已完成全部 5 阶段
            sample_level="fine",
            scan_step_s=scan_step_fine,
            completed_evaluation_ids=completed_ids,
            rows=all_rows,
            best_evaluation_id=best_eid,
            best_total=best_total,
            status_counts=all_status_counts,
            system_errors=[
                r.to_dict() for r in all_rows if r.status == "system_error"
            ],
            run_identity_sha256=run_identity_sha,
            lineage_manifest_sha256=lineage_sha,
        )
        ck_path = os.path.join(output_dir, "checkpoint_v2.json")
        save_checkpoint_v2(ck, ck_path)
    output: Dict[str, Any] = {
        "task": "TASK_004 Q2 REAL SEARCH CORE V1 — P1 REMEDIATION",
        "declaration": "PILOT / NOT A FORMAL Q2 RESULT",
        "best_known_disclaimer": "BEST-KNOWN CANDIDATE / NOT A PROVEN GLOBAL OPTIMUM",
        "algorithm_version": ALGORITHM_VERSION,
        "sampling_method": SAMPLING_METHOD,
        "evaluator_kind": "real",
        "evaluator_version": "v1",
        "code_revision": code_rev,
        "seed": seed,
        "domain": domain_desc,
        "budget": budget,
        "static_run_identity": static_identity,
        "run_identity_sha256": run_identity_sha,
        "lineage_manifest_sha256": lineage_sha,
        "lineage_manifest": lineage,
        "status_counts": status_counts,
        "n_total_rows": len(all_rows),
        "final_best_status": final_best_status,
        "best_known_candidate": (final_best_row.to_dict()
                                  if final_best_row is not None else None),
        "stage_counts": {
            "global_coarse": len(coarse_rows),
            "global_medium": len(medium_rows),
            "local_coarse": len(local_rows),
            "local_medium": len(local_medium_rows),
            "fine": len(fine_rows),
        },
        "coarse_top_k": [r.to_dict() for r in top_k],
        "medium_top": [r.to_dict() for r in medium_top],
        "local_top": [r.to_dict() for r in local_top],
        "medium_confirmed_pool_size": len(medium_confirmed),
        "fine_rows": [r.to_dict() for r in fine_rows],
        "all_rows": [r.to_dict() for r in all_rows],
    }
    out_path = os.path.join(output_dir, "pilot_result.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # 简易 CLI 报告
    print(f"[PILOT] algorithm_version={ALGORITHM_VERSION}")
    print(f"[PILOT] sampling_method={SAMPLING_METHOD}")
    print(f"[PILOT] run_identity_sha256={run_identity_sha}")
    print(f"[PILOT] lineage_manifest_sha256={lineage_sha}")
    print(f"[PILOT] seed={seed} status_counts={status_counts}")
    print(f"[PILOT] stage_counts={output['stage_counts']}")
    print(f"[PILOT] final_best_status={final_best_status}")
    if final_best_row is not None:
        print(f"[PILOT] best_known stage={final_best_row.source_stage} "
              f"sample_level={final_best_row.sample_level} "
              f"scan_step={final_best_row.scan_step_s} "
              f"total_duration_s={final_best_row.total_duration_s:.6f}")
        print(f"[PILOT] best_known candidate={final_best_row.to_dict()}")
    print(f"[PILOT] output={out_path}")
    print(f"[PILOT] declaration={output['declaration']}")
    print(f"[PILOT] best_known_disclaimer={output['best_known_disclaimer']}")

    return output


# =============================================================================
#  第十三节: parallel (FakeEvaluator only, EXPERIMENTAL)
# =============================================================================
def _pool_worker_fake(args: Tuple[int,
                                    Tuple[float, float, float, float],
                                    float]) -> Tuple[int, float]:
    """FakeEvaluator top-level worker. 仅用于 parallel bench / 调度开销."""
    idx, cand, sleep_s = args
    if sleep_s > 0.0:
        time.sleep(sleep_s)
    h, s, r, d = cand
    total = (math.sin(h) + 1.0) * 0.5 + (s - 70.0) / 70.0 \
             + (r / 60.0) + (d / 30.0)
    return int(idx), float(total)


def run_parallel_fake(candidates: Sequence[Tuple[float, float, float, float]],
                       workers: int,
                       sleep_s: float = 0.0,
                       chunksize: int = 1) -> List[Tuple[int, float]]:
    """FakeEvaluator parallel (主要用于调度开销 / 性能 benchmark)."""
    import multiprocessing
    if workers < 1:
        raise ValueError(f"workers 必须 ≥ 1, 实际 {workers}")
    if chunksize < 1:
        raise ValueError(f"chunksize 必须 ≥ 1, 实际 {chunksize}")
    args_list = [(i, c, sleep_s) for i, c in enumerate(candidates)]
    ctx = multiprocessing.get_context("spawn")
    with ctx.Pool(processes=workers) as pool:
        results = pool.map(_pool_worker_fake, args_list, chunksize=chunksize)
    return results


# =============================================================================
#  第十四节: CLI
# =============================================================================
def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m src.q2_search",
        description="Q2 Real Search Core v1.1 (TASK_004 P1 REMEDIATION)",
    )
    p.add_argument("--run-search", action="store_true",
                    help="执行真实 Search (默认仅打印 banner)")
    p.add_argument("--evaluator", choices=["real", "fake"], default="real",
                    help="evaluator 类型; real 必须 --run-search")
    p.add_argument("--mode", choices=["pilot", "formal"], default="pilot",
                    help="执行模式; formal 禁用并返回 2")
    p.add_argument("--seed", type=int, default=2025)
    p.add_argument("--config", default=DEFAULT_CONFIG_PATH,
                    help="gate config 路径 (schema v2)")
    p.add_argument("--checkpoint-dir", default="work/q2_search",
                    help="checkpoint / 输出目录")
    p.add_argument("--resume-from", default=None,
                    help="checkpoint path (P1-D)")
    p.add_argument("--workers", type=int, default=1,
                    help="workers 数; real 模式下 workers > 1 拒绝")
    p.add_argument("--global-coarse-count", type=int, default=None)
    p.add_argument("--coarse-top-k", type=int, default=None)
    p.add_argument("--medium-re-evaluate-count", type=int, default=None)
    p.add_argument("--local-per-top", type=int, default=None)
    p.add_argument("--local-max-count", type=int, default=None)
    p.add_argument("--local-medium-count", type=int, default=None)
    p.add_argument("--fine-final-count", type=int, default=None)
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI 入口."""
    parser = _build_argparser()
    args = parser.parse_args(argv)

    if not args.run_search:
        print("Q2 SEARCH IMPLEMENTATION (TASK_004 Q2 REAL SEARCH CORE V1, P1 REMEDIATION)")
        print("=" * 70)
        print("NOT AN OPTIMIZATION RESULT")
        print("默认仅打印 banner; 真实 Search 必须显式 --run-search.")
        print("推荐：")
        print("  python -m src.q2_search --run-search --evaluator real "
              "--mode pilot --seed 2025 --config configs/q2_search_gate_v1.json "
              "--checkpoint-dir work/q2_search")
        return 0

    # --run-search --evaluator fake 拒绝
    if args.evaluator == "fake":
        print("ERROR: --run-search --evaluator fake 拒绝. "
              "正式 Search 必须 evaluator=real.",
              file=sys.stderr)
        return 2

    # --mode formal 禁用 (P2)
    if args.mode == "formal":
        print("ERROR: --mode formal 当前禁用 (TASK_004 P2). "
              "本轮仅支持 --mode pilot.",
              file=sys.stderr)
        return 2

    # real 模式 workers > 1 拒绝
    if args.workers > 1:
        print(f"ERROR: real 模式 workers > 1 当前禁用 (EXPERIMENTAL). "
              f"workers={args.workers}",
              file=sys.stderr)
        return 2

    # 注入最新 main 的物理常量
    from src.q1_baseline import U0, G, missile_arrival_time
    t_arrival = missile_arrival_time()
    u0_vec = tuple(U0)

    budget: Dict[str, Any] = {
        "global_coarse_count": DEFAULT_PILOT_BUDGET["global_coarse_count"],
        "coarse_top_k": DEFAULT_PILOT_BUDGET["coarse_top_k"],
        "medium_re_evaluate_count": DEFAULT_PILOT_BUDGET["medium_re_evaluate_count"],
        "local_per_top": DEFAULT_PILOT_BUDGET["local_per_top"],
        "local_max_count": DEFAULT_PILOT_BUDGET["local_max_count"],
        "local_medium_count": DEFAULT_PILOT_BUDGET["local_medium_count"],
        "fine_final_count": DEFAULT_PILOT_BUDGET["fine_final_count"],
        "local_delta": DEFAULT_PILOT_BUDGET["local_delta"],
    }
    if args.global_coarse_count is not None:
        budget["global_coarse_count"] = args.global_coarse_count
    if args.coarse_top_k is not None:
        budget["coarse_top_k"] = args.coarse_top_k
    if args.medium_re_evaluate_count is not None:
        budget["medium_re_evaluate_count"] = args.medium_re_evaluate_count
    if args.local_per_top is not None:
        budget["local_per_top"] = args.local_per_top
    if args.local_max_count is not None:
        budget["local_max_count"] = args.local_max_count
    if args.local_medium_count is not None:
        budget["local_medium_count"] = args.local_medium_count
    if args.fine_final_count is not None:
        budget["fine_final_count"] = args.fine_final_count

    # 加载 config (P1-F)
    cfg: Optional[Dict[str, Any]] = None
    if args.config:
        if os.path.exists(args.config):
            cfg = load_config_v2(args.config)
            print(f"[CLI] config loaded: {args.config} "
                  f"schema_version={cfg.get('schema_version')}")
        else:
            print(f"WARN: config 不存在 ({args.config}); "
                  f"回退到内置默认.", file=sys.stderr)

    out = run_search_pipeline(
        seed=args.seed, u0=u0_vec, g=G,
        t_arrival=t_arrival, budget=budget,
        output_dir=args.checkpoint_dir,
        config=cfg,
        resume_from=args.resume_from,
    )

    # 退出码: 0 表示无 system_error 且 fine 有 best;
    # 1 表示有 system_error; 2 表示 fine 为空 (empty fine)
    if out["status_counts"].get("system_error", 0) > 0:
        return 1
    if out.get("final_best_status") == "EMPTY_FINE_NO_RESULT":
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())