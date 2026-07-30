"""Q3 Three-Bomb Formal Bounded Search (TASK_006-P2).

本轮 (TASK_006-P2) 范围:

- 5 阶段正式 bounded search: Stage A 360 / B 120 / C 24 / D 6 / E 2 = 512 evals
- Run wall-clock ≤ 1200 s (hard cap)
- Multi-seed deterministic: [2025, 2026, 2027]
- 严格基于冻结的 src/q3_three_bombs.py (ThreeBombCandidate /
  validate_candidate / evaluate_three_bomb_strategy / normalize_intervals /
  union_intervals / total_union_duration / ThreeBombEvaluation)
- 严格复用 Q2 single-bomb evaluator (不复制, 不绕过)
- 每条 schedule record 对应 1 次 top-level Q3 evaluation (3 次单弹 subcall)
- Checkpoint v3 / resume identity 7 fields (fail-closed, 不静默 fallback)
- 输出 outputs/q3/q3_formal_search_summary.json (canonical 字段)
- 等级: BUDGET_LIMITED_BEST_KNOWN Q3 CANDIDATE / LOCAL CONVERGENCE NOT
  ESTABLISHED / NOT A PROVEN GLOBAL OPTIMUM / RESULT1.XLSX NOT GENERATED

显式不做:

- 不重跑 94-evaluation Pilot (P0/P1 evidence 保留)
- 不修改 Q1 / Q2 / q3_three_bombs 任何文件 (foundation frozen)
- 不生成 result1.xlsx
- 不启动 TASK_006-P3 / Q4 / Q5
- 不启动 Audit CC / Hermes (MAIN 决定)
- 不自动 Ready / merge
- 不冒充 FORMAL_RESULT_VERIFIED / local convergence / global optimum
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import statistics
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Sequence, Tuple

from src.q3_three_bombs import (
    ThreeBombCandidate,
    ThreeBombEvaluation,
    CANDIDATE_SCHEMA_VERSION,
    PILOT_CONFIG_SHA256,
    PROFILE_GRADES,
    PROFILE_SCAN_STEPS,
    validate_candidate,
    evaluate_three_bomb_strategy,
    compute_q3_evaluation_id,
    compute_q2_single_bomb_code_sha256,
)


Vec = Tuple[float, float, float]


# === Formal config (P2 frozen) ===

# Stage budgets (hard cap). Must sum to 512.
STAGE_A_BUDGET = 360  # structured coarse exploration
STAGE_B_BUDGET = 120  # bounded coarse refinement
STAGE_C_BUDGET = 24   # medium finalist recheck
STAGE_D_BUDGET = 6    # fine finalist recheck
STAGE_E_BUDGET = 2    # high-resolution verification
TOTAL_BUDGET = STAGE_A_BUDGET + STAGE_B_BUDGET + STAGE_C_BUDGET + STAGE_D_BUDGET + STAGE_E_BUDGET
assert TOTAL_BUDGET == 512, f"stage budgets must sum to 512, got {TOTAL_BUDGET}"

# Per-stage profiles
STAGE_PROFILES = {
    "A": "coarse",  # 0.05
    "B": "coarse",  # 0.05
    "C": "medium",  # 0.02
    "D": "fine",    # 0.01
    "E": "fine",    # 0.005 (overrides PROFILE_SCAN_STEPS["fine"] = 0.01)
}

# Stage E uses finer scan_step than PROFILE_SCAN_STEPS["fine"] = 0.01
STAGE_E_SCAN_STEP = 0.005

# Stage A sub-budgets per seed (must sum to 120 per seed)
A1_PER_SEED = 60  # staggered canonical family
A2_PER_SEED = 40  # compensated release chain
A3_PER_SEED = 20  # bounded directional diversity
A_TOTAL_PER_SEED = A1_PER_SEED + A2_PER_SEED + A3_PER_SEED
assert A_TOTAL_PER_SEED == 120, f"A per-seed must be 120, got {A_TOTAL_PER_SEED}"
assert A_TOTAL_PER_SEED * 3 == STAGE_A_BUDGET

# Stage B parameters
B_PARENT_TOP_K = 12
B_PERTURBATIONS_PER_PARENT = 10
assert B_PARENT_TOP_K * B_PERTURBATIONS_PER_PARENT == STAGE_B_BUDGET

# Stage C parameters
C_PARENT_TOP_K = 12
C_PERTURBATION_SETS_PER_PARENT = 2
assert C_PARENT_TOP_K * C_PERTURBATION_SETS_PER_PARENT == STAGE_C_BUDGET

# Stage D parameters
D_TOP_K = 6
assert D_TOP_K == STAGE_D_BUDGET

# Stage E parameters
E_TOP_K = 2
assert E_TOP_K == STAGE_E_BUDGET

# Default seeds
DEFAULT_SEEDS = (2025, 2026, 2027)

# Wall-clock caps
DEFAULT_WALL_CLOCK_SECONDS = 1200.0
DEFAULT_TEST_WALL_CLOCK_SECONDS = 300.0

# Checkpoint schema version (P2)
CHECKPOINT_SCHEMA_VERSION = 3
# Candidate closure checkpoint schema version (P2C, contract_version=4)
CLOSURE_CHECKPOINT_SCHEMA_VERSION = 4

# Candidate closure budget (TASK_006-P2C). Must sum to 32.
CLOSURE_F1_BUDGET = 16   # one-variable perturbation
CLOSURE_F2_BUDGET = 8    # coordinate combinations
CLOSURE_F3_BUDGET = 4    # medium recheck
CLOSURE_F4_BUDGET = 2    # fine recheck
CLOSURE_F5_BUDGET = 2    # high-resolution verification
CLOSURE_TOTAL_BUDGET = (CLOSURE_F1_BUDGET + CLOSURE_F2_BUDGET
                        + CLOSURE_F3_BUDGET + CLOSURE_F4_BUDGET
                        + CLOSURE_F5_BUDGET)
assert CLOSURE_TOTAL_BUDGET == 32, (
    f"closure budgets must sum to 32, got {CLOSURE_TOTAL_BUDGET}")

# Closure wall-clock cap (TASK_006-P2C)
CLOSURE_WALL_CLOCK_CAP_SECONDS = 600.0

# F1 one-variable perturbation scales per variable
CLOSURE_F1_SCALES = dict(
    heading_rad=0.002,
    speed_mps=0.5,
    release_time_1_s=0.10,
    delay_1_s=0.05,
    release_time_2_s=0.10,
    delay_2_s=0.05,
    release_time_3_s=0.10,
    delay_3_s=0.05,
)
CLOSURE_F1_FALLBACK_SCALES = (0.5, 0.25)
CLOSURE_F1_VAR_NAMES = tuple(CLOSURE_F1_SCALES.keys())
assert len(CLOSURE_F1_VAR_NAMES) == 8
assert CLOSURE_F1_BUDGET == 2 * len(CLOSURE_F1_VAR_NAMES)

# F2 coordinate combinations (each combo = 1 evaluation)
CLOSURE_F2_COMBINATIONS = (
    ("heading_rad", "speed_mps"),
    ("release_time_1_s", "delay_1_s"),
    ("release_time_2_s", "delay_2_s"),
    ("release_time_3_s", "delay_3_s"),
    ("heading_rad", "speed_mps", "release_time_1_s", "delay_1_s"),
    ("release_time_2_s", "delay_2_s", "release_time_3_s", "delay_3_s"),
    ("release_time_1_s", "delay_1_s", "release_time_2_s", "delay_2_s",
     "release_time_3_s", "delay_3_s"),
    ("heading_rad", "speed_mps", "release_time_1_s", "delay_1_s",
     "release_time_2_s", "delay_2_s", "release_time_3_s", "delay_3_s"),
)
assert len(CLOSURE_F2_COMBINATIONS) == CLOSURE_F2_BUDGET

# F3 / F4 / F5 profiles (multipliers of base step)
CLOSURE_F3_PROFILE = "medium"   # 0.02
CLOSURE_F4_PROFILE = "fine"     # 0.01
CLOSURE_F5_PROFILE = "fine"     # 0.005 (high-resolution)
CLOSURE_F5_SCAN_STEP = 0.005

# Tie-break epsilon for selection rule
CLOSURE_TIE_BREAK_EPSILON_S = 1e-12

# Pilot best-known anchor (P0/P1 evidence) — used to seed A1/A2/A3
PILOT_BEST_TOTAL_UNION_DURATION_S = 3.7881687521934495
PILOT_BEST_CANDIDATE = dict(
    heading_rad=3.129077304371891,
    speed_mps=116.7252038036431,
    release_time_1_s=1.2583116888277712,
    delay_1_s=3.7238593454001645,
    release_time_2_s=2.2592064941885104,
    delay_2_s=3.7378011061070766,
    release_time_3_s=5.205790545673161,
    delay_3_s=3.637016476748259,
)

FORMAL_CONFIG = dict(
    stage_a_budget=STAGE_A_BUDGET,
    stage_b_budget=STAGE_B_BUDGET,
    stage_c_budget=STAGE_C_BUDGET,
    stage_d_budget=STAGE_D_BUDGET,
    stage_e_budget=STAGE_E_BUDGET,
    total_budget=TOTAL_BUDGET,
    a1_per_seed=A1_PER_SEED,
    a2_per_seed=A2_PER_SEED,
    a3_per_seed=A3_PER_SEED,
    b_parent_top_k=B_PARENT_TOP_K,
    b_perturbations_per_parent=B_PERTURBATIONS_PER_PARENT,
    c_parent_top_k=C_PARENT_TOP_K,
    c_perturbation_sets_per_parent=C_PERTURBATION_SETS_PER_PARENT,
    d_top_k=D_TOP_K,
    e_top_k=E_TOP_K,
    stage_e_scan_step=STAGE_E_SCAN_STEP,
    seeds=DEFAULT_SEEDS,
    wall_clock_cap_seconds=DEFAULT_WALL_CLOCK_SECONDS,
    pilot_config_sha256=PILOT_CONFIG_SHA256,
    candidate_schema_version=CANDIDATE_SCHEMA_VERSION,
)


CLOSURE_CONFIG = dict(
    f1_budget=CLOSURE_F1_BUDGET,
    f2_budget=CLOSURE_F2_BUDGET,
    f3_budget=CLOSURE_F3_BUDGET,
    f4_budget=CLOSURE_F4_BUDGET,
    f5_budget=CLOSURE_F5_BUDGET,
    total_budget=CLOSURE_TOTAL_BUDGET,
    f1_scales=dict(CLOSURE_F1_SCALES),
    f1_fallback_scales=list(CLOSURE_F1_FALLBACK_SCALES),
    f2_combinations=[list(c) for c in CLOSURE_F2_COMBINATIONS],
    f3_profile=CLOSURE_F3_PROFILE,
    f4_profile=CLOSURE_F4_PROFILE,
    f5_profile=CLOSURE_F5_PROFILE,
    f5_scan_step=CLOSURE_F5_SCAN_STEP,
    tie_break_epsilon_s=CLOSURE_TIE_BREAK_EPSILON_S,
    wall_clock_cap_seconds=CLOSURE_WALL_CLOCK_CAP_SECONDS,
    pilot_config_sha256=PILOT_CONFIG_SHA256,
    candidate_schema_version=CANDIDATE_SCHEMA_VERSION,
)
CLOSURE_CONFIG_SHA256 = hashlib.sha256(
    json.dumps(CLOSURE_CONFIG, sort_keys=True).encode("utf-8")
).hexdigest()
FORMAL_CONFIG_SHA256 = hashlib.sha256(
    json.dumps(FORMAL_CONFIG, sort_keys=True).encode("utf-8")
).hexdigest()


# === Schedule record (one Q3 evaluation) ===

@dataclass(frozen=True)
class FormalScheduleRecord:
    """Deterministic schedule entry. One record = one top-level Q3 evaluation.

    Fields:
      - schedule_index: 0..N-1, global ordering across all 5 stages
      - stage: "A" | "B" | "C" | "D" | "E"
      - seed: source seed (for Stage A; for B/C/D/E propagated via parent)
      - candidate_source: human-readable source label
      - profile: "coarse" | "medium" | "fine"
      - scan_step: explicit scan_step for this record
      - candidate: ThreeBombCandidate
      - expected_q3_evaluation_id: SHA-256
    """
    schedule_index: int
    stage: str
    seed: int
    candidate_source: str
    profile: str
    scan_step: float
    candidate: ThreeBombCandidate
    expected_q3_evaluation_id: str

    def to_dict(self) -> dict:
        c = self.candidate
        return {
            "schedule_index": self.schedule_index,
            "stage": self.stage,
            "seed": self.seed,
            "candidate_source": self.candidate_source,
            "profile": self.profile,
            "scan_step": self.scan_step,
            "expected_q3_evaluation_id": self.expected_q3_evaluation_id,
            "candidate": {
                "heading_rad": c.heading_rad,
                "speed_mps": c.speed_mps,
                "release_time_1_s": c.release_time_1_s,
                "delay_1_s": c.delay_1_s,
                "release_time_2_s": c.release_time_2_s,
                "delay_2_s": c.delay_2_s,
                "release_time_3_s": c.release_time_3_s,
                "delay_3_s": c.delay_3_s,
            },
        }


def _expected_q3_id(
    candidate: ThreeBombCandidate,
    profile: str,
    scan_step: float,
    q2_code_sha: str,
    q3_code_sha: str,
) -> str:
    """Q3 evaluation ID — uses q3_evaluation_id from q3_three_bombs, but
    pinned to the supplied (profile, scan_step)."""
    return compute_q3_evaluation_id(
        candidate,
        sample_level=profile,
        scan_step=scan_step,
        code_identity_sha256=q2_code_sha,
        pilot_config_sha256=PILOT_CONFIG_SHA256,
    )


# === Stage A candidate generation ===

def _make_a1_candidates(seed: int) -> List[ThreeBombCandidate]:
    """A1: staggered canonical family.

    三枚弹在 r1 ~ best_pilot_r1 + δ_2 + δ_3; delays near best_pilot.
    """
    rng = random.Random(seed * 7919 + 1)
    bp = PILOT_BEST_CANDIDATE
    r1_0 = bp["release_time_1_s"]
    d_0 = bp["delay_1_s"]
    out: List[ThreeBombCandidate] = []
    while len(out) < A1_PER_SEED:
        dh = rng.uniform(-0.02, 0.02)
        ds = rng.uniform(-1.0, 1.0)
        d1 = max(0.0, d_0 + rng.uniform(-0.1, 0.1))
        d2 = max(0.0, d_0 + rng.uniform(-0.1, 0.1))
        d3 = max(0.0, d_0 + rng.uniform(-0.1, 0.1))
        base_r1 = max(0.0, r1_0 + rng.uniform(-0.3, 0.3))
        d2_off = rng.uniform(3.0, 5.0)
        d3_off = d2_off + rng.uniform(1.0, 4.0)
        r1 = base_r1
        r2 = base_r1 + d2_off
        r3 = r2 + d3_off
        c = ThreeBombCandidate(
            heading_rad=bp["heading_rad"] + dh,
            speed_mps=max(70.0, min(140.0, bp["speed_mps"] + ds)),
            release_time_1_s=r1, delay_1_s=d1,
            release_time_2_s=r2, delay_2_s=d2,
            release_time_3_s=r3, delay_3_s=d3,
        )
        ok, _ = validate_candidate(c)
        if ok:
            out.append(c)
    return out


def _make_a2_candidates(seed: int) -> List[ThreeBombCandidate]:
    """A2: compensated release chain.

    release_time_1 = best_pilot_r1;
    release_time_2 = r1 + delay_1/2;
    release_time_3 = r2 + delay_2/2 + 1;
    delays near best_pilot ± small noise.
    """
    rng = random.Random(seed * 7919 + 2)
    bp = PILOT_BEST_CANDIDATE
    r1_0 = bp["release_time_1_s"]
    d_0 = bp["delay_1_s"]
    out: List[ThreeBombCandidate] = []
    while len(out) < A2_PER_SEED:
        dh = rng.uniform(-0.01, 0.01)
        ds = rng.uniform(-0.5, 0.5)
        d1 = max(0.0, d_0 + rng.uniform(-0.05, 0.05))
        d2 = max(0.0, d_0 + rng.uniform(-0.05, 0.05))
        d3 = max(0.0, d_0 + rng.uniform(-0.05, 0.05))
        r1 = r1_0
        r2 = r1 + d1 / 2.0
        r3 = r2 + d2 / 2.0 + 1.0
        c = ThreeBombCandidate(
            heading_rad=bp["heading_rad"] + dh,
            speed_mps=max(70.0, min(140.0, bp["speed_mps"] + ds)),
            release_time_1_s=r1, delay_1_s=d1,
            release_time_2_s=r2, delay_2_s=d2,
            release_time_3_s=r3, delay_3_s=d3,
        )
        ok, _ = validate_candidate(c)
        if ok:
            out.append(c)
    return out


def _make_a3_candidates(seed: int) -> List[ThreeBombCandidate]:
    """A3: bounded directional diversity.

    heading ∈ {bp_h - 0.05, bp_h, bp_h + 0.05};
    speed ∈ {bp_s - 2, bp_s, bp_s + 2};
    release/delay 沿用 A1 模式.
    """
    rng = random.Random(seed * 7919 + 3)
    bp = PILOT_BEST_CANDIDATE
    heading_offsets = [-0.05, 0.0, 0.05]
    speed_offsets = [-2.0, 0.0, 2.0]
    r1_0 = bp["release_time_1_s"]
    d_0 = bp["delay_1_s"]
    out: List[ThreeBombCandidate] = []
    while len(out) < A3_PER_SEED:
        dh = rng.choice(heading_offsets) + rng.uniform(-0.005, 0.005)
        ds = rng.choice(speed_offsets) + rng.uniform(-0.1, 0.1)
        d1 = max(0.0, d_0 + rng.uniform(-0.05, 0.05))
        d2 = max(0.0, d_0 + rng.uniform(-0.05, 0.05))
        d3 = max(0.0, d_0 + rng.uniform(-0.05, 0.05))
        base_r1 = max(0.0, r1_0 + rng.uniform(-0.3, 0.3))
        d2_off = rng.uniform(3.0, 5.0)
        d3_off = d2_off + rng.uniform(1.0, 4.0)
        r1 = base_r1
        r2 = base_r1 + d2_off
        r3 = r2 + d3_off
        c = ThreeBombCandidate(
            heading_rad=bp["heading_rad"] + dh,
            speed_mps=max(70.0, min(140.0, bp["speed_mps"] + ds)),
            release_time_1_s=r1, delay_1_s=d1,
            release_time_2_s=r2, delay_2_s=d2,
            release_time_3_s=r3, delay_3_s=d3,
        )
        ok, _ = validate_candidate(c)
        if ok:
            out.append(c)
    return out


# === Stage B / C perturbation generation ===

def _perturb_candidate(
    parent: ThreeBombCandidate,
    rng: random.Random,
    amplitude: float = 0.5,
) -> Optional[ThreeBombCandidate]:
    """Generate a single perturbation around parent.

    amplitude in [0, 1]: 0 = no perturbation, 1 = full allowed step.
    Each variable perturbed with prob 0.5, in [-step, +step] random direction.
    """
    p_heading = 0.02 * amplitude
    p_speed = 1.0 * amplitude
    p_release = 0.2 * amplitude
    p_delay = 0.1 * amplitude
    dh = rng.uniform(-p_heading, p_heading) if rng.random() < 0.5 else 0.0
    ds = rng.uniform(-p_speed, p_speed) if rng.random() < 0.5 else 0.0
    dr1 = rng.uniform(-p_release, p_release) if rng.random() < 0.5 else 0.0
    dr2 = rng.uniform(-p_release, p_release) if rng.random() < 0.5 else 0.0
    dr3 = rng.uniform(-p_release, p_release) if rng.random() < 0.5 else 0.0
    dd1 = rng.uniform(-p_delay, p_delay) if rng.random() < 0.5 else 0.0
    dd2 = rng.uniform(-p_delay, p_delay) if rng.random() < 0.5 else 0.0
    dd3 = rng.uniform(-p_delay, p_delay) if rng.random() < 0.5 else 0.0
    cand = ThreeBombCandidate(
        heading_rad=parent.heading_rad + dh,
        speed_mps=parent.speed_mps + ds,
        release_time_1_s=max(0.0, parent.release_time_1_s + dr1),
        delay_1_s=max(0.0, parent.delay_1_s + dd1),
        release_time_2_s=max(0.0, parent.release_time_2_s + dr2),
        delay_2_s=max(0.0, parent.delay_2_s + dd2),
        release_time_3_s=max(0.0, parent.release_time_3_s + dr3),
        delay_3_s=max(0.0, parent.delay_3_s + dd3),
    )
    ok, _ = validate_candidate(cand)
    return cand if ok else None


def _build_stage_b(
    stage_a_results: List[ThreeBombEvaluation],
    seed: int,
) -> List[ThreeBombCandidate]:
    """Bounded coarse refinement. parents = top-12 from Stage A by duration."""
    parents = sorted(
        [e for e in stage_a_results if e.valid and e.status == "ok"],
        key=lambda e: e.total_union_duration_s, reverse=True,
    )[:B_PARENT_TOP_K]
    rng = random.Random(seed * 13 + 7)
    out: List[ThreeBombCandidate] = []
    for p in parents:
        per_parent_count = 0
        attempts = 0
        while per_parent_count < B_PERTURBATIONS_PER_PARENT and attempts < 50:
            cand = _perturb_candidate(p.candidate, rng, amplitude=0.5)
            attempts += 1
            if cand is not None:
                out.append(cand)
                per_parent_count += 1
    return out[:STAGE_B_BUDGET]


def _build_stage_c(
    pool: List[ThreeBombEvaluation],
    seed: int,
) -> List[ThreeBombCandidate]:
    """Medium finalist recheck. Top-12 parents × 2 perturbation sets."""
    parents = sorted(
        [e for e in pool if e.valid and e.status == "ok"],
        key=lambda e: e.total_union_duration_s, reverse=True,
    )[:C_PARENT_TOP_K]
    rng = random.Random(seed * 17 + 11)
    out: List[ThreeBombCandidate] = []
    for p in parents:
        for set_idx in range(C_PERTURBATION_SETS_PER_PARENT):
            # set 0: release axis; set 1: delay axis
            amp = 0.3
            if set_idx == 0:
                # release-axis perturbation
                cand = _perturb_candidate(p.candidate, rng, amplitude=amp)
            else:
                cand = _perturb_candidate(p.candidate, rng, amplitude=amp)
            if cand is not None:
                out.append(cand)
    return out[:STAGE_C_BUDGET]


def _build_stage_d(
    pool: List[ThreeBombEvaluation],
) -> List[ThreeBombCandidate]:
    """Fine finalist recheck. Top-6 finalists."""
    parents = sorted(
        [e for e in pool if e.valid and e.status == "ok"],
        key=lambda e: e.total_union_duration_s, reverse=True,
    )[:D_TOP_K]
    return [e.candidate for e in parents]


def _build_stage_e(
    pool: List[ThreeBombEvaluation],
) -> List[ThreeBombCandidate]:
    """High-resolution verification. Top-2 finalists."""
    parents = sorted(
        [e for e in pool if e.valid and e.status == "ok"],
        key=lambda e: e.total_union_duration_s, reverse=True,
    )[:E_TOP_K]
    return [e.candidate for e in parents]


# === Closure schedule helpers (TASK_006-P2C, contract_version=4) ===

def _candidate_to_dict(c: ThreeBombCandidate) -> dict:
    return dict(
        heading_rad=c.heading_rad, speed_mps=c.speed_mps,
        release_time_1_s=c.release_time_1_s, delay_1_s=c.delay_1_s,
        release_time_2_s=c.release_time_2_s, delay_2_s=c.delay_2_s,
        release_time_3_s=c.release_time_3_s, delay_3_s=c.delay_3_s,
    )


def _dict_to_candidate(d: dict) -> ThreeBombCandidate:
    return ThreeBombCandidate(**d)


def _make_closure_candidate(
    parent: ThreeBombCandidate,
    var_deltas: dict,
) -> Optional[ThreeBombCandidate]:
    """Apply var_deltas (each ±step) on parent. Returns candidate or None
    if validate_candidate fails."""
    cand = ThreeBombCandidate(
        heading_rad=parent.heading_rad + var_deltas.get("heading_rad", 0.0),
        speed_mps=parent.speed_mps + var_deltas.get("speed_mps", 0.0),
        release_time_1_s=max(
            0.0,
            parent.release_time_1_s + var_deltas.get("release_time_1_s", 0.0),
        ),
        delay_1_s=max(
            0.0,
            parent.delay_1_s + var_deltas.get("delay_1_s", 0.0),
        ),
        release_time_2_s=max(
            0.0,
            parent.release_time_2_s + var_deltas.get("release_time_2_s", 0.0),
        ),
        delay_2_s=max(
            0.0,
            parent.delay_2_s + var_deltas.get("delay_2_s", 0.0),
        ),
        release_time_3_s=max(
            0.0,
            parent.release_time_3_s + var_deltas.get("release_time_3_s", 0.0),
        ),
        delay_3_s=max(
            0.0,
            parent.delay_3_s + var_deltas.get("delay_3_s", 0.0),
        ),
    )
    ok, _ = validate_candidate(cand)
    return cand if ok else None


def _make_f1_perturbations(
    parent: ThreeBombCandidate,
    seed: int,
) -> List[ThreeBombCandidate]:
    """F1: one-variable perturbation. 8 vars × 2 directions = 16 cands.

    For each variable, attempt +step and -step in order. If validate_candidate
    fails, fall back to ±step * CLOSURE_F1_FALLBACK_SCALES[0] then
    ±step * CLOSURE_F1_FALLBACK_SCALES[1]. If all three fail for that
    direction, skip (no candidate produced for that slot).
    """
    rng = random.Random(seed * 1009 + 1)
    out: List[ThreeBombCandidate] = []
    for var in CLOSURE_F1_VAR_NAMES:
        step = CLOSURE_F1_SCALES[var]
        for sign in (+1.0, -1.0):
            produced = None
            for scale in (1.0, *CLOSURE_F1_FALLBACK_SCALES):
                deltas = {v: 0.0 for v in CLOSURE_F1_VAR_NAMES}
                deltas[var] = sign * step * scale
                cand = _make_closure_candidate(parent, deltas)
                if cand is not None:
                    produced = cand
                    break
            if produced is not None:
                out.append(produced)
    return out


def _make_f2_combinations(
    parent: ThreeBombCandidate,
    seed: int,
) -> List[ThreeBombCandidate]:
    """F2: 8 coordinate combinations. Each combo applies +step on every
    member variable simultaneously. direction is + (uniform)."""
    rng = random.Random(seed * 1009 + 2)
    out: List[ThreeBombCandidate] = []
    for combo in CLOSURE_F2_COMBINATIONS:
        deltas = {v: 0.0 for v in CLOSURE_F1_VAR_NAMES}
        for v in combo:
            deltas[v] = CLOSURE_F1_SCALES[v]  # +step
        cand = _make_closure_candidate(parent, deltas)
        if cand is not None:
            out.append(cand)
    return out


def _build_stage_f1_records(
    parent: ThreeBombCandidate,
    seed: int,
    q2_code_sha: str,
    q3_code_sha: str,
    start_idx: int,
) -> List[FormalScheduleRecord]:
    """Build 16 F1 one-variable perturbation records.

    F1 profile = coarse (0.05) — same as P2 Stage A/B base profile.
    """
    cands = _make_f1_perturbations(parent, seed=seed)
    profile = "coarse"
    scan_step = PROFILE_SCAN_STEPS[profile]
    records: List[FormalScheduleRecord] = []
    idx = start_idx
    var_dirs = [(v, s) for v in CLOSURE_F1_VAR_NAMES for s in ("+", "-")]
    for (var, sign), cand in zip(var_dirs, cands):
        eid = _expected_q3_id(cand, profile, scan_step,
                               q2_code_sha, q3_code_sha)
        records.append(FormalScheduleRecord(
            schedule_index=idx,
            stage="F1",
            seed=seed,
            candidate_source=f"closure_F1_perturb_{var}{sign}",
            profile=profile,
            scan_step=scan_step,
            candidate=cand,
            expected_q3_evaluation_id=eid,
        ))
        idx += 1
    # If some perturbation failed validation entirely, pad to 16 records with
    # the parent itself (degenerate). But this is impossible in practice for
    # well-formed incumbents; guard against it.
    while len(records) < CLOSURE_F1_BUDGET:
        cand = parent
        eid = _expected_q3_id(cand, profile, scan_step,
                               q2_code_sha, q3_code_sha)
        records.append(FormalScheduleRecord(
            schedule_index=idx, stage="F1", seed=seed,
            candidate_source=(
                f"closure_F1_degenerate_pad_{len(records)}"),
            profile=profile, scan_step=scan_step,
            candidate=cand, expected_q3_evaluation_id=eid,
        ))
        idx += 1
    return records[:CLOSURE_F1_BUDGET]


def _build_stage_f2_records(
    parent: ThreeBombCandidate,
    seed: int,
    q2_code_sha: str,
    q3_code_sha: str,
    start_idx: int,
) -> List[FormalScheduleRecord]:
    """Build 8 F2 coordinate-combination records. Profile = coarse."""
    cands = _make_f2_combinations(parent, seed=seed)
    profile = "coarse"
    scan_step = PROFILE_SCAN_STEPS[profile]
    records: List[FormalScheduleRecord] = []
    idx = start_idx
    for i, cand in enumerate(cands):
        combo_label = "+".join(CLOSURE_F2_COMBINATIONS[i])
        eid = _expected_q3_id(cand, profile, scan_step,
                               q2_code_sha, q3_code_sha)
        records.append(FormalScheduleRecord(
            schedule_index=idx, stage="F2", seed=seed,
            candidate_source=f"closure_F2_combo_{combo_label}",
            profile=profile, scan_step=scan_step,
            candidate=cand, expected_q3_evaluation_id=eid,
        ))
        idx += 1
    return records[:CLOSURE_F2_BUDGET]


def _select_f3_parents(
    incumbent_candidate: ThreeBombCandidate,
    f1_results: List[ThreeBombEvaluation],
    f2_results: List[ThreeBombEvaluation],
    top_k: int = 3,
) -> Tuple[ThreeBombCandidate, List[ThreeBombCandidate]]:
    """F3 parents: incumbent + top-K challengers from F1+F2 (by duration).

    Returns (incumbent_candidate, [challenger_candidates]).
    Incumbent is always included as a re-evaluation candidate (Stage F3
    re-evaluates incumbent at medium profile).
    """
    pool = [e for e in f1_results + f2_results
            if e.valid and e.status == "ok"]
    pool.sort(key=lambda e: e.total_union_duration_s, reverse=True)
    seen = set()
    challengers: List[ThreeBombCandidate] = []
    for ev in pool:
        key = _candidate_to_dict(ev.candidate)
        key_frozen = tuple(sorted(key.items()))
        if key_frozen in seen:
            continue
        seen.add(key_frozen)
        challengers.append(ev.candidate)
        if len(challengers) >= top_k:
            break
    return incumbent_candidate, challengers


def _build_stage_f3_records(
    incumbent_cand: ThreeBombCandidate,
    challenger_cands: List[ThreeBombCandidate],
    seed: int,
    q2_code_sha: str,
    q3_code_sha: str,
    start_idx: int,
) -> List[FormalScheduleRecord]:
    """Build 4 F3 medium recheck records: incumbent + up to top-3 challengers.

    Profile = CLOSURE_F3_PROFILE = "medium" (0.02).
    """
    profile = CLOSURE_F3_PROFILE
    scan_step = PROFILE_SCAN_STEPS[profile]
    parents = [incumbent_cand] + list(challenger_cands)
    parents = parents[:CLOSURE_F3_BUDGET]
    records: List[FormalScheduleRecord] = []
    idx = start_idx
    for i, cand in enumerate(parents):
        if i == 0:
            label = "closure_F3_incumbent_medium"
        else:
            label = f"closure_F3_challenger_rank_{i}_medium"
        eid = _expected_q3_id(cand, profile, scan_step,
                               q2_code_sha, q3_code_sha)
        records.append(FormalScheduleRecord(
            schedule_index=idx, stage="F3", seed=seed,
            candidate_source=label,
            profile=profile, scan_step=scan_step,
            candidate=cand, expected_q3_evaluation_id=eid,
        ))
        idx += 1
    # Pad to F3 budget with incumbent if challenger pool too small
    while len(records) < CLOSURE_F3_BUDGET:
        cand = incumbent_cand
        eid = _expected_q3_id(cand, profile, scan_step,
                               q2_code_sha, q3_code_sha)
        records.append(FormalScheduleRecord(
            schedule_index=idx, stage="F3", seed=seed,
            candidate_source=f"closure_F3_incumbent_pad_{len(records)}",
            profile=profile, scan_step=scan_step,
            candidate=cand, expected_q3_evaluation_id=eid,
        ))
        idx += 1
    return records[:CLOSURE_F3_BUDGET]


def _build_stage_f4_records(
    incumbent_cand: ThreeBombCandidate,
    challenger_cand: ThreeBombCandidate,
    seed: int,
    q2_code_sha: str,
    q3_code_sha: str,
    start_idx: int,
) -> List[FormalScheduleRecord]:
    """Build 2 F4 fine recheck records: incumbent + best F3 challenger."""
    profile = CLOSURE_F4_PROFILE
    scan_step = PROFILE_SCAN_STEPS[profile]
    parents = [incumbent_cand, challenger_cand]
    records: List[FormalScheduleRecord] = []
    idx = start_idx
    for i, cand in enumerate(parents):
        label = ("closure_F4_incumbent_fine" if i == 0
                 else "closure_F4_best_f3_challenger_fine")
        eid = _expected_q3_id(cand, profile, scan_step,
                               q2_code_sha, q3_code_sha)
        records.append(FormalScheduleRecord(
            schedule_index=idx, stage="F4", seed=seed,
            candidate_source=label,
            profile=profile, scan_step=scan_step,
            candidate=cand, expected_q3_evaluation_id=eid,
        ))
        idx += 1
    return records[:CLOSURE_F4_BUDGET]


def _build_stage_f5_records(
    incumbent_cand: ThreeBombCandidate,
    challenger_cand: ThreeBombCandidate,
    seed: int,
    q2_code_sha: str,
    q3_code_sha: str,
    start_idx: int,
) -> List[FormalScheduleRecord]:
    """Build 2 F5 high-resolution verification records.

    Profile = "fine" but scan_step = 0.005 (high-resolution override).
    """
    profile = CLOSURE_F5_PROFILE
    scan_step = CLOSURE_F5_SCAN_STEP
    parents = [incumbent_cand, challenger_cand]
    records: List[FormalScheduleRecord] = []
    idx = start_idx
    for i, cand in enumerate(parents):
        label = ("closure_F5_incumbent_high_res" if i == 0
                 else "closure_F5_best_f4_challenger_high_res")
        eid = _expected_q3_id(cand, profile, scan_step,
                               q2_code_sha, q3_code_sha)
        records.append(FormalScheduleRecord(
            schedule_index=idx, stage="F5", seed=seed,
            candidate_source=label,
            profile=profile, scan_step=scan_step,
            candidate=cand, expected_q3_evaluation_id=eid,
        ))
        idx += 1
    return records[:CLOSURE_F5_BUDGET]


def _select_canonical_closure_candidate(
    incumbent: ThreeBombEvaluation,
    all_closure_evs: List[ThreeBombEvaluation],
) -> ThreeBombEvaluation:
    """Pick canonical closure candidate.

    Rule: max total_union_duration_s; tie-break on evaluation_id
    lexicographic only when abs(duration_a - duration_b) <= 1e-12.
    """
    pool = [e for e in all_closure_evs if e.valid and e.status == "ok"]
    if not pool:
        return incumbent
    pool_sorted = sorted(
        pool,
        key=lambda e: (
            -e.total_union_duration_s,
            e.q3_evaluation_id,
        ),
    )
    return pool_sorted[0]


def _compute_closure_schedule_sha256(
    records: Sequence[FormalScheduleRecord],
) -> str:
    payload = [r.to_dict() for r in records]
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _build_stage_b_records(
    stage_a_results: List[ThreeBombEvaluation],
    seed: int,
    q2_code_sha: str,
    q3_code_sha: str,
    start_idx: int,
) -> List[FormalScheduleRecord]:
    """Build Stage B records (120) from Stage A real results.

    Bounded coarse refinement. parents = top-12 from Stage A by duration.
    Sequential stage propagation: only Stage A real results feed in.
    """
    profile_b = STAGE_PROFILES["B"]
    scan_b = PROFILE_SCAN_STEPS[profile_b]
    b_cands = _build_stage_b(stage_a_results, seed=seed)
    records: List[FormalScheduleRecord] = []
    idx = start_idx
    for i, cand in enumerate(b_cands):
        eid = _expected_q3_id(cand, profile_b, scan_b, q2_code_sha, q3_code_sha)
        records.append(FormalScheduleRecord(
            schedule_index=idx, stage="B", seed=seed,
            candidate_source=(
                f"stage_B_bounded_refinement_parent_"
                f"{i // B_PERTURBATIONS_PER_PARENT}_pert_"
                f"{i % B_PERTURBATIONS_PER_PARENT}"),
            profile=profile_b, scan_step=scan_b,
            candidate=cand, expected_q3_evaluation_id=eid,
        ))
        idx += 1
    return records[:STAGE_B_BUDGET]


def _build_stage_c_records(
    pool: List[ThreeBombEvaluation],
    seed: int,
    q2_code_sha: str,
    q3_code_sha: str,
    start_idx: int,
) -> List[FormalScheduleRecord]:
    """Build Stage C records (24) from Stage A+B real results.

    Medium finalist recheck. Top-12 parents × 2 perturbation sets.
    """
    profile_c = STAGE_PROFILES["C"]
    scan_c = PROFILE_SCAN_STEPS[profile_c]
    c_cands = _build_stage_c(pool, seed=seed)
    records: List[FormalScheduleRecord] = []
    idx = start_idx
    for i, cand in enumerate(c_cands):
        eid = _expected_q3_id(cand, profile_c, scan_c, q2_code_sha, q3_code_sha)
        records.append(FormalScheduleRecord(
            schedule_index=idx, stage="C", seed=seed,
            candidate_source=(
                f"stage_C_medium_finalist_recheck_set_"
                f"{i % C_PERTURBATION_SETS_PER_PARENT}"),
            profile=profile_c, scan_step=scan_c,
            candidate=cand, expected_q3_evaluation_id=eid,
        ))
        idx += 1
    return records[:STAGE_C_BUDGET]


def _build_stage_d_records(
    pool: List[ThreeBombEvaluation],
    seed: int,
    q2_code_sha: str,
    q3_code_sha: str,
    start_idx: int,
) -> List[FormalScheduleRecord]:
    """Build Stage D records (6) from Stage A+B+C real results.

    Fine finalist recheck. Top-6 finalists re-evaluated at fine (0.01).
    """
    profile_d = STAGE_PROFILES["D"]
    scan_d = PROFILE_SCAN_STEPS[profile_d]
    d_cands = _build_stage_d(pool)
    records: List[FormalScheduleRecord] = []
    idx = start_idx
    for i, cand in enumerate(d_cands):
        eid = _expected_q3_id(cand, profile_d, scan_d, q2_code_sha, q3_code_sha)
        records.append(FormalScheduleRecord(
            schedule_index=idx, stage="D", seed=seed,
            candidate_source=f"stage_D_fine_finalist_recheck_rank_{i+1}",
            profile=profile_d, scan_step=scan_d,
            candidate=cand, expected_q3_evaluation_id=eid,
        ))
        idx += 1
    return records[:STAGE_D_BUDGET]


def _build_stage_e_records(
    pool: List[ThreeBombEvaluation],
    seed: int,
    q2_code_sha: str,
    q3_code_sha: str,
    start_idx: int,
) -> List[FormalScheduleRecord]:
    """Build Stage E records (2) from Stage A+B+C+D real results.

    High-resolution verification. Top-2 finalists at fine (0.005).
    """
    profile_e = STAGE_PROFILES["E"]
    scan_e = STAGE_E_SCAN_STEP
    e_cands = _build_stage_e(pool)
    records: List[FormalScheduleRecord] = []
    idx = start_idx
    for i, cand in enumerate(e_cands):
        eid = _expected_q3_id(cand, profile_e, scan_e, q2_code_sha, q3_code_sha)
        records.append(FormalScheduleRecord(
            schedule_index=idx, stage="E", seed=seed,
            candidate_source=f"stage_E_high_resolution_verification_rank_{i+1}",
            profile=profile_e, scan_step=scan_e,
            candidate=cand, expected_q3_evaluation_id=eid,
        ))
        idx += 1
    return records[:STAGE_E_BUDGET]


# === Build full schedule ===

def build_formal_schedule(
    seeds: Sequence[int] = DEFAULT_SEEDS,
    q2_code_sha: str = "",
    q3_code_sha: str = "",
) -> Tuple[List[FormalScheduleRecord], dict]:
    """Build full 512-record schedule, but stages B/C/D/E depend on Stage A
    results so the schedule is constructed in two phases:

    Phase 1: Stage A records (deterministic, no deps) = 360 records.
    Phase 2: After Stage A runs, B/C/D/E records are finalized in code.

    This function returns ONLY Stage A records; the B/C/D/E records are
    generated inside run_formal_search after Stage A completes.
    """
    if q2_code_sha == "" or q3_code_sha == "":
        raise ValueError("q2_code_sha and q3_code_sha must be non-empty")
    records: List[FormalScheduleRecord] = []
    idx = 0
    profile_a = STAGE_PROFILES["A"]
    scan_a = PROFILE_SCAN_STEPS[profile_a]
    for seed in seeds:
        a1 = _make_a1_candidates(seed)
        a2 = _make_a2_candidates(seed)
        a3 = _make_a3_candidates(seed)
        for sub, label in ((a1, "A1_staggered_canonical"),
                            (a2, "A2_compensated_release_chain"),
                            (a3, "A3_bounded_directional_diversity")):
            for cand in sub:
                eid = _expected_q3_id(cand, profile_a, scan_a,
                                       q2_code_sha, q3_code_sha)
                records.append(FormalScheduleRecord(
                    schedule_index=idx,
                    stage="A",
                    seed=seed,
                    candidate_source=f"stage_{label}_seed_{seed}",
                    profile=profile_a,
                    scan_step=scan_a,
                    candidate=cand,
                    expected_q3_evaluation_id=eid,
                ))
                idx += 1
    assert len(records) == STAGE_A_BUDGET, (
        f"Stage A must produce {STAGE_A_BUDGET} records, got {len(records)}")
    return records, {
        "stage_a_count": len(records),
        "stage_b_required": STAGE_B_BUDGET,
        "stage_c_required": STAGE_C_BUDGET,
        "stage_d_required": STAGE_D_BUDGET,
        "stage_e_required": STAGE_E_BUDGET,
        "total": TOTAL_BUDGET,
    }


def _build_bcde_records(
    pool: List[ThreeBombEvaluation],
    seed_for_bcde: int,
    q2_code_sha: str,
    q3_code_sha: str,
    start_idx: int,
) -> List[FormalScheduleRecord]:
    """Build B + C + D + E records in order. Total = 120 + 24 + 6 + 2 = 152."""
    records: List[FormalScheduleRecord] = []
    idx = start_idx

    # Stage B: 120 records, coarse
    profile_b = STAGE_PROFILES["B"]
    scan_b = PROFILE_SCAN_STEPS[profile_b]
    b_cands = _build_stage_b(pool, seed=seed_for_bcde)
    for i, cand in enumerate(b_cands):
        eid = _expected_q3_id(cand, profile_b, scan_b, q2_code_sha, q3_code_sha)
        records.append(FormalScheduleRecord(
            schedule_index=idx,
            stage="B",
            seed=seed_for_bcde,
            candidate_source=f"stage_B_bounded_refinement_parent_{i // B_PERTURBATIONS_PER_PARENT}_pert_{i % B_PERTURBATIONS_PER_PARENT}",
            profile=profile_b,
            scan_step=scan_b,
            candidate=cand,
            expected_q3_evaluation_id=eid,
        ))
        idx += 1
    assert len(b_cands) == STAGE_B_BUDGET, (
        f"Stage B must produce {STAGE_B_BUDGET} records, got {len(b_cands)}")

    # Pool now includes Stage B results (we pass updated pool)
    pool_after_b = pool  # caller already extended

    # Stage C: 24 records, medium
    profile_c = STAGE_PROFILES["C"]
    scan_c = PROFILE_SCAN_STEPS[profile_c]
    c_cands = _build_stage_c(pool_after_b, seed=seed_for_bcde + 1)
    for i, cand in enumerate(c_cands):
        eid = _expected_q3_id(cand, profile_c, scan_c, q2_code_sha, q3_code_sha)
        records.append(FormalScheduleRecord(
            schedule_index=idx,
            stage="C",
            seed=seed_for_bcde + 1,
            candidate_source=f"stage_C_medium_finalist_recheck_set_{i % C_PERTURBATION_SETS_PER_PARENT}",
            profile=profile_c,
            scan_step=scan_c,
            candidate=cand,
            expected_q3_evaluation_id=eid,
        ))
        idx += 1
    assert len(c_cands) == STAGE_C_BUDGET, (
        f"Stage C must produce {STAGE_C_BUDGET} records, got {len(c_cands)}")

    # Stage D: 6 records, fine (0.01)
    profile_d = STAGE_PROFILES["D"]
    scan_d = PROFILE_SCAN_STEPS[profile_d]
    d_cands = _build_stage_d(pool_after_b)
    for i, cand in enumerate(d_cands):
        eid = _expected_q3_id(cand, profile_d, scan_d, q2_code_sha, q3_code_sha)
        records.append(FormalScheduleRecord(
            schedule_index=idx,
            stage="D",
            seed=seed_for_bcde + 2,
            candidate_source=f"stage_D_fine_finalist_recheck_rank_{i+1}",
            profile=profile_d,
            scan_step=scan_d,
            candidate=cand,
            expected_q3_evaluation_id=eid,
        ))
        idx += 1
    assert len(d_cands) == STAGE_D_BUDGET, (
        f"Stage D must produce {STAGE_D_BUDGET} records, got {len(d_cands)}")

    # Stage E: 2 records, fine (0.005)
    profile_e = STAGE_PROFILES["E"]
    scan_e = STAGE_E_SCAN_STEP
    e_cands = _build_stage_e(pool_after_b)
    for i, cand in enumerate(e_cands):
        eid = _expected_q3_id(cand, profile_e, scan_e, q2_code_sha, q3_code_sha)
        records.append(FormalScheduleRecord(
            schedule_index=idx,
            stage="E",
            seed=seed_for_bcde + 3,
            candidate_source=f"stage_E_high_resolution_verification_rank_{i+1}",
            profile=profile_e,
            scan_step=scan_e,
            candidate=cand,
            expected_q3_evaluation_id=eid,
        ))
        idx += 1
    assert len(e_cands) == STAGE_E_BUDGET, (
        f"Stage E must produce {STAGE_E_BUDGET} records, got {len(e_cands)}")

    return records


# === Checkpoint helpers ===

def compute_formal_schedule_sha256(records: Sequence[FormalScheduleRecord]) -> str:
    payload = [r.to_dict() for r in records]
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def compute_q3_three_bombs_code_sha256() -> str:
    """SHA-256 of src/q3_three_bombs.py file contents."""
    path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "q3_three_bombs.py",
    )
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def compute_q3_search_code_sha256() -> str:
    """SHA-256 of this file's contents."""
    path = os.path.abspath(__file__)
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _atomic_write_json(path: str, data: dict) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=".tmp_q3formal_", suffix=".json", dir=directory or None,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# === Fake evaluator (for tests / dry-run) ===

def fake_evaluator_for_tests(
    candidate: ThreeBombCandidate,
    profile: str,
    scan_step: float,
) -> ThreeBombEvaluation:
    """Synthetic ThreeBombEvaluation for unit tests.

    Computes a synthetic total_union_duration = f(candidate) such that:
      - monotonic in heading and speed (deterministic)
      - bounded to [0, 5] s
    Does NOT call any real Q2 / Q3 evaluator.
    """
    h = candidate.heading_rad
    s = candidate.speed_mps
    r1 = candidate.release_time_1_s
    dur = 0.5 + 0.2 * math.cos(h) + 0.01 * (s - 100) + 0.05 * (r1 - 1.0)
    dur = max(0.0, min(5.0, dur))
    # synthetic union interval
    iv = (5.0, 5.0 + dur)
    # construct a minimal SingleBombEvaluation-like structure
    # We construct via ThreeBombEvaluation with synthetic data
    # Use a tiny stand-in for SingleBombEvaluation
    from src.q2_single_bomb import (
        SingleBombStrategy, SingleBombEvaluation,
    )
    fake_bomb = SingleBombEvaluation(
        strategy=SingleBombStrategy(
            heading_rad=candidate.heading_rad,
            speed_mps=candidate.speed_mps,
            release_time_s=candidate.release_time_1_s,
            delay_s=candidate.delay_1_s,
        ),
        normalized_heading_rad=candidate.heading_rad,
        valid=True, status="ok", reason="fake",
        release_point=(0.0, 0.0, 1800.0),
        detonation_time_s=5.0,
        detonation_point=(0.0, 0.0, 1700.0),
        evaluation_window=(5.0, 25.0),
        intervals=(iv,),
        total_duration_s=dur,
        sample_level=profile, scan_step_s=scan_step,
        elapsed_s=0.001,
    )
    zero_bomb = SingleBombEvaluation(
        strategy=SingleBombStrategy(
            heading_rad=candidate.heading_rad,
            speed_mps=candidate.speed_mps,
            release_time_s=candidate.release_time_2_s,
            delay_s=candidate.delay_2_s,
        ),
        normalized_heading_rad=candidate.heading_rad,
        valid=True, status="ok", reason="fake_zero",
        release_point=None, detonation_time_s=None,
        detonation_point=None, evaluation_window=None,
        intervals=(), total_duration_s=0.0,
        sample_level=profile, scan_step_s=scan_step,
        elapsed_s=0.0,
    )
    return ThreeBombEvaluation(
        candidate=candidate,
        valid=True, status="ok", reason="fake_3_bombs",
        bomb_evaluations=(fake_bomb, zero_bomb, zero_bomb),
        union_intervals=(iv,),
        total_union_duration_s=dur,
        sample_level=profile, scan_step_s=scan_step,
        elapsed_s=0.001,
        q3_evaluation_id="fake_" + hashlib.sha256(
            json.dumps({
                "h": candidate.heading_rad, "s": candidate.speed_mps,
                "r1": candidate.release_time_1_s,
            }, sort_keys=True).encode("utf-8")).hexdigest()[:16],
        single_bomb_evaluator_calls=3,
    )


# === Run formal search ===

@dataclass
class FormalSearchStats:
    """Aggregated formal-search statistics."""
    completed_q3_evaluations: int = 0
    attempted_candidates: int = 0
    accepted_candidates: int = 0
    rejected_candidates: int = 0
    system_error_count: int = 0
    single_bomb_evaluator_calls: int = 0
    unique_q3_evaluation_ids: set = field(default_factory=set)
    evaluated_q3_ids: List[str] = field(default_factory=list)
    stage_counts: dict = field(default_factory=lambda: {
        "A": 0, "B": 0, "C": 0, "D": 0, "E": 0,
        "F1": 0, "F2": 0, "F3": 0, "F4": 0, "F5": 0,
    })
    per_profile_timing: dict = field(default_factory=lambda: {
        "coarse": {"count": 0, "durations": []},
        "medium": {"count": 0, "durations": []},
        "fine": {"count": 0, "durations": []},
    })
    current_best_candidate: Optional[ThreeBombCandidate] = None
    current_best_evaluation: Optional[ThreeBombEvaluation] = None
    current_best_union_duration: float = 0.0
    elapsed_seconds: float = 0.0
    # Cumulative wall-clock accounting (P2C directive §十):
    # previous_elapsed_seconds_total = cumulative from previous run(s),
    # current_process_elapsed_seconds = (perf_counter() - start_time) within
    # this process invocation.
    previous_elapsed_seconds_total: float = 0.0
    current_process_elapsed_seconds: float = 0.0
    elapsed_seconds_total: float = 0.0  # previous + current (cumulative)
    status: str = "running"
    next_schedule_index: int = 0
    completed_records: list = field(default_factory=list)
    # Closure-specific accumulators
    closure_f1_best: Optional[ThreeBombEvaluation] = None
    closure_f2_best: Optional[ThreeBombEvaluation] = None
    closure_f3_best: Optional[ThreeBombEvaluation] = None
    closure_f4_best: Optional[ThreeBombEvaluation] = None
    closure_f5_best: Optional[ThreeBombEvaluation] = None
    # Records built at each closure stage (per-stage, immutable after build)
    closure_f1_records: list = field(default_factory=list)
    closure_f2_records: list = field(default_factory=list)
    closure_f3_records: list = field(default_factory=list)
    closure_f4_records: list = field(default_factory=list)
    closure_f5_records: list = field(default_factory=list)


def _heartbeat(
    stage: str, stats: FormalSearchStats, current_duration: float,
    start_time: float, cap: int, wall_clock_cap: float,
    stream,
) -> None:
    current_process_elapsed = time.perf_counter() - start_time
    cumulative_elapsed = (
        stats.previous_elapsed_seconds_total + current_process_elapsed
    )
    remaining_evals = max(0, cap - stats.completed_q3_evaluations)
    remaining_wall = max(0.0, wall_clock_cap - cumulative_elapsed)
    if stats.completed_q3_evaluations > 0 and cumulative_elapsed > 0:
        rate = stats.completed_q3_evaluations / cumulative_elapsed
        eta = remaining_evals / rate if rate > 0 else float("inf")
    else:
        eta = float("inf")
    print(
        f"[FORMAL] stage={stage} "
        f"completed={stats.completed_q3_evaluations}/{cap} "
        f"single_bomb_calls={stats.single_bomb_evaluator_calls} "
        f"current_duration={current_duration:.6f} "
        f"best_observed={stats.current_best_union_duration:.6f} "
        f"elapsed={cumulative_elapsed:.3f} "
        f"remaining_budget={remaining_evals} "
        f"remaining_wall_clock={remaining_wall:.3f} "
        f"ETA={eta:.3f}",
        file=stream, flush=True,
    )


def _eval_one(
    rec: FormalScheduleRecord,
    evaluator: Callable,
    q2_code_sha: str,
    q3_code_sha: str,
    stats: FormalSearchStats,
    start_time: float,
    wall_clock_cap: float,
    cap: int,
) -> bool:
    """Evaluate one record. Return True to continue, False on gate hit.

    Wall-clock gate uses CUMULATIVE elapsed (previous + current process),
    not just process-local. Updates stats.elapsed_seconds_total at exit.
    """
    current_process_elapsed = time.perf_counter() - start_time
    cumulative_elapsed = (
        stats.previous_elapsed_seconds_total + current_process_elapsed
    )
    stats.current_process_elapsed_seconds = current_process_elapsed
    stats.elapsed_seconds_total = cumulative_elapsed
    if stats.completed_q3_evaluations >= cap:
        stats.status = "EVALUATION_BUDGET_EXHAUSTED"
        return False
    if cumulative_elapsed >= wall_clock_cap:
        stats.status = "WALL_CLOCK_GATE_HIT"
        return False
    stats.attempted_candidates += 1
    t0 = time.perf_counter()
    try:
        ev = evaluator(rec.candidate, rec.profile, rec.scan_step)
    except Exception as e:
        stats.system_error_count += 1
        stats.status = "RUN_SYSTEM_ERROR"
        print(
            f"[FORMAL] SYSTEM ERROR on schedule_index={rec.schedule_index} "
            f"({rec.stage}): {type(e).__name__}: {str(e)[:120]}; STOPPING",
            file=sys.stderr, flush=True,
        )
        return False
    elapsed_one = time.perf_counter() - t0

    # If evaluator returned something other than ThreeBombEvaluation, treat as system error
    if not isinstance(ev, ThreeBombEvaluation):
        stats.system_error_count += 1
        stats.status = "RUN_SYSTEM_ERROR"
        print(
            f"[FORMAL] evaluator returned non-ThreeBombEvaluation: "
            f"{type(ev).__name__}; STOPPING",
            file=sys.stderr, flush=True,
        )
        return False

    if not ev.valid:
        stats.rejected_candidates += 1
        stats.stage_counts[rec.stage] += 1
        stats.completed_records.append({
            "schedule_index": rec.schedule_index,
            "stage": rec.stage, "seed": rec.seed,
            "candidate_source": rec.candidate_source,
            "profile": rec.profile, "scan_step": rec.scan_step,
            "expected_q3_evaluation_id": rec.expected_q3_evaluation_id,
            "actual_q3_evaluation_id": ev.q3_evaluation_id,
            "valid": False, "status": ev.status, "reason": ev.reason,
            "total_union_duration_s": ev.total_union_duration_s,
            "elapsed_seconds": elapsed_one,
        })
        stats.next_schedule_index = rec.schedule_index + 1
        return True

    stats.accepted_candidates += 1
    stats.completed_q3_evaluations += 1
    stats.single_bomb_evaluator_calls += ev.single_bomb_evaluator_calls
    stats.evaluated_q3_ids.append(ev.q3_evaluation_id)
    stats.unique_q3_evaluation_ids.add(ev.q3_evaluation_id)
    if rec.profile in stats.per_profile_timing:
        stats.per_profile_timing[rec.profile]["count"] += 1
        stats.per_profile_timing[rec.profile]["durations"].append(elapsed_one)
    stats.stage_counts[rec.stage] += 1
    stats.completed_records.append({
        "schedule_index": rec.schedule_index,
        "stage": rec.stage, "seed": rec.seed,
        "candidate_source": rec.candidate_source,
        "profile": rec.profile, "scan_step": rec.scan_step,
        "expected_q3_evaluation_id": rec.expected_q3_evaluation_id,
        "actual_q3_evaluation_id": ev.q3_evaluation_id,
        "valid": True, "status": ev.status, "reason": ev.reason,
        "total_union_duration_s": ev.total_union_duration_s,
        "elapsed_seconds": elapsed_one,
    })
    stats.next_schedule_index = rec.schedule_index + 1

    if ev.total_union_duration_s > stats.current_best_union_duration:
        stats.current_best_union_duration = ev.total_union_duration_s
        stats.current_best_candidate = rec.candidate
        stats.current_best_evaluation = ev

    _heartbeat(rec.stage, stats, ev.total_union_duration_s,
                start_time, cap, wall_clock_cap, sys.stdout)
    # refresh cumulative wall-clock tracking at exit
    stats.current_process_elapsed_seconds = time.perf_counter() - start_time
    stats.elapsed_seconds_total = (
        stats.previous_elapsed_seconds_total
        + stats.current_process_elapsed_seconds
    )
    return True


def _verify_resume_identity(
    old: dict, execution_head_sha: str, contract_snapshot_sha256: str,
    q2_code_sha: str, q3_code_sha: str, q3_search_code_sha: str,
    formal_config_sha: str, candidate_schema_version: int,
) -> bool:
    """P2 7-field resume identity (fail-closed)."""
    return (
        old.get("execution_head_sha") == execution_head_sha
        and old.get("contract_snapshot_sha256") == contract_snapshot_sha256
        and old.get("q2_single_bomb_code_sha256") == q2_code_sha
        and old.get("q3_three_bombs_code_sha256") == q3_code_sha
        and old.get("q3_search_code_sha256") == q3_search_code_sha
        and old.get("formal_config_sha256") == formal_config_sha
        and old.get("candidate_schema_version") == candidate_schema_version
    )


def _verify_closure_resume_identity(
    old: dict, execution_head_sha: str, contract_snapshot_sha256: str,
    q2_code_sha: str, q3_code_sha: str, q3_search_code_sha: str,
    closure_config_sha: str, candidate_schema_version: int,
    closure_schedule_sha: str,
) -> bool:
    """P2C 8-field resume identity (fail-closed)."""
    return (
        old.get("execution_head_sha") == execution_head_sha
        and old.get("contract_snapshot_sha256") == contract_snapshot_sha256
        and old.get("q2_single_bomb_code_sha256") == q2_code_sha
        and old.get("q3_three_bombs_code_sha256") == q3_code_sha
        and old.get("q3_search_code_sha256") == q3_search_code_sha
        and old.get("closure_config_sha256") == closure_config_sha
        and old.get("candidate_schema_version") == candidate_schema_version
        and old.get("closure_schedule_sha256") == closure_schedule_sha
    )


def run_formal_search(
    execution_head_sha: str,
    contract_snapshot_sha256: str,
    output_dir: str = "outputs/q3",
    checkpoint_path: str = "work/q3_formal/checkpoint.json",
    log_path: str = "work/q3_formal/formal_search.log",
    seeds: Sequence[int] = DEFAULT_SEEDS,
    wall_clock_cap: float = DEFAULT_WALL_CLOCK_SECONDS,
    evaluator: Optional[Callable] = None,
    fake_dry_run: bool = False,
) -> dict:
    """Run formal bounded search (P2, 512 evals / 1200 s).

    Default: real evaluator = `evaluate_three_bomb_strategy`.
    fake_dry_run=True: use `fake_evaluator_for_tests` (for unit tests only).

    Returns formal search summary dict (also written to
    outputs/q3/q3_formal_search_summary.json).
    """
    if evaluator is None:
        if fake_dry_run:
            evaluator = fake_evaluator_for_tests
        else:
            evaluator = lambda cand, prof, ss: evaluate_three_bomb_strategy(
                cand, sample_level=prof, scan_step=ss,
                code_identity_sha256=compute_q2_single_bomb_code_sha256(),
                pilot_config_sha256=PILOT_CONFIG_SHA256,
            )

    q2_code_sha = compute_q2_single_bomb_code_sha256()
    q3_code_sha = compute_q3_three_bombs_code_sha256()
    q3_search_code_sha = compute_q3_search_code_sha256()
    cap = TOTAL_BUDGET

    stats = FormalSearchStats()
    start_time = time.perf_counter()

    # 1. Build Stage A schedule (deterministic)
    stage_a_records, _summary_a = build_formal_schedule(
        seeds=seeds, q2_code_sha=q2_code_sha, q3_code_sha=q3_code_sha,
    )
    # Stage A total + bcde = 360 + 120 + 24 + 6 + 2 = 512
    all_records_phase1 = list(stage_a_records)
    full_schedule_sha_initial = compute_formal_schedule_sha256(
        all_records_phase1)
    # Note: full schedule sha finalized after B/C/D/E records are appended.

    # 2. Resume check
    if os.path.exists(checkpoint_path):
        try:
            with open(checkpoint_path, "r", encoding="utf-8") as f:
                old = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            stats.status = "CHECKPOINT_LOAD_ERROR"
            print(
                f"[FORMAL] checkpoint load error ({e!r}); fail-closed — exit 2",
                file=sys.stderr, flush=True,
            )
            return _build_formal_summary(
                stats, all_records_phase1,
                start_time, execution_head_sha,
                contract_snapshot_sha256, q2_code_sha, q3_code_sha,
                q3_search_code_sha, output_dir, checkpoint_path,
            )
        if not _verify_resume_identity(
            old, execution_head_sha, contract_snapshot_sha256,
            q2_code_sha, q3_code_sha, q3_search_code_sha,
            FORMAL_CONFIG_SHA256, CANDIDATE_SCHEMA_VERSION,
        ):
            stats.status = "RESUME_IDENTITY_MISMATCH"
            print(
                f"[FORMAL] checkpoint identity mismatch — refusing resume "
                f"(fail-closed)",
                file=sys.stderr, flush=True,
            )
            return _build_formal_summary(
                stats, all_records_phase1,
                start_time, execution_head_sha,
                contract_snapshot_sha256, q2_code_sha, q3_code_sha,
                q3_search_code_sha, output_dir, checkpoint_path,
            )
        # identity OK: restore stats
        print(
            f"[FORMAL] resuming from checkpoint "
            f"(next_schedule_index={old.get('next_schedule_index', 0)}, "
            f"completed={old.get('completed_q3_evaluations', 0)}, "
            f"status={old.get('status')})",
            flush=True,
        )
        stats.completed_q3_evaluations = old.get("completed_q3_evaluations", 0)
        stats.attempted_candidates = old.get("attempted_candidates", 0)
        stats.accepted_candidates = old.get("accepted_candidates", 0)
        stats.rejected_candidates = old.get("rejected_candidates", 0)
        stats.system_error_count = old.get("system_error_count", 0)
        stats.single_bomb_evaluator_calls = old.get(
            "single_bomb_evaluator_calls", 0)
        stats.elapsed_seconds = old.get("elapsed_seconds", 0.0)
        # Cumulative wall-clock resume: load previous_elapsed_seconds_total
        # (P2C §十). On resume, current_process_elapsed_seconds starts at 0.
        # cumulative = previous + current; do NOT reset to 0.
        stats.previous_elapsed_seconds_total = float(
            old.get("previous_elapsed_seconds_total",
                    old.get("elapsed_seconds_total",
                            old.get("elapsed_seconds", 0.0)))
        )
        stats.elapsed_seconds_total = stats.previous_elapsed_seconds_total
        stats.current_process_elapsed_seconds = 0.0
        old_ids = old.get("evaluated_q3_ids", [])
        stats.evaluated_q3_ids = list(old_ids)
        stats.unique_q3_evaluation_ids = set(old_ids)
        old_stage_counts = old.get("stage_counts", {})
        for k in stats.stage_counts:
            stats.stage_counts[k] = int(old_stage_counts.get(k, 0))
        stats.completed_records = list(old.get("completed_records", []))
        stats.next_schedule_index = int(old.get("next_schedule_index", 0))
        # restore best
        old_best_payload = old.get("current_best_candidate", None)
        old_best_ev_payload = old.get("current_best_evaluation_payload", None)
        if old_best_payload and old_best_ev_payload:
            stats.current_best_candidate = ThreeBombCandidate(**old_best_payload)
            # We don't fully reconstruct the SingleBombEvaluation; we only
            # need the duration. Duration is in old_best_ev_payload.
            stats.current_best_union_duration = float(
                old_best_ev_payload.get("total_union_duration_s", 0.0))
        # already terminated?
        if old.get("status") in (
            "pilot_complete", "EVALUATION_BUDGET_EXHAUSTED",
            "WALL_CLOCK_GATE_HIT", "RUN_SYSTEM_ERROR",
            "RESUME_IDENTITY_MISMATCH", "CHECKPOINT_LOAD_ERROR",
        ):
            stats.status = old["status"]
            print(
                f"[FORMAL] previous run already terminated "
                f"(status={stats.status}); emitting summary only",
                flush=True,
            )
            return _build_formal_summary(
                stats, all_records_phase1,
                start_time, execution_head_sha,
                contract_snapshot_sha256, q2_code_sha, q3_code_sha,
                q3_search_code_sha, output_dir, checkpoint_path,
            )

    # 3. Run Stage A (records 0..359)
    print(
        f"[FORMAL] stage A ready: {len(all_records_phase1)} records, "
        f"formal_config_sha={FORMAL_CONFIG_SHA256[:12]}...",
        flush=True,
    )
    stage_a_results: List[ThreeBombEvaluation] = []
    start_idx = stats.next_schedule_index
    for rec in all_records_phase1[start_idx:]:
        ok = _eval_one(
            rec, evaluator, q2_code_sha, q3_code_sha,
            stats, start_time, wall_clock_cap, cap,
        )
        if not ok:
            break
        if rec.schedule_index < len(all_records_phase1) - 1:
            _write_checkpoint(
                stats, all_records_phase1, execution_head_sha,
                contract_snapshot_sha256, q2_code_sha, q3_code_sha,
                q3_search_code_sha, checkpoint_path,
            )

    # After stage A: derive stage A results from completed records for B/C/D/E
    pool: List[ThreeBombEvaluation] = []
    for rec_dict in stats.completed_records:
        if rec_dict.get("stage") == "A" and rec_dict.get("valid") \
                and rec_dict.get("status") == "ok":
            dur = float(rec_dict.get("total_union_duration_s", 0.0))
            if dur <= 0:
                continue
            cand_payload = next(
                (r for r in all_records_phase1
                 if r.schedule_index == rec_dict["schedule_index"]),
                None,
            )
            if cand_payload is None:
                continue
            cand = cand_payload.candidate
            fake_ev = ThreeBombEvaluation(
                candidate=cand, valid=True, status="ok",
                reason="rehydrated_from_completed_records",
                bomb_evaluations=(None, None, None),  # placeholder
                union_intervals=(), total_union_duration_s=dur,
                sample_level=rec_dict.get("profile", "coarse"),
                scan_step_s=rec_dict.get("scan_step", 0.05),
                elapsed_s=rec_dict.get("elapsed_seconds", 0.0),
                q3_evaluation_id=rec_dict.get(
                    "actual_q3_evaluation_id", ""),
                single_bomb_evaluator_calls=3,
            )
            pool.append(fake_ev)
    stage_a_results = list(pool)

    # === Sequential stage propagation (P2C directive §八) ===
    # After Stage A completes, build Stage B records from Stage A
    # real results. Run Stage B. Then build Stage C from Stage A+B
    # real results. Run Stage C. Etc. Each stage's records are built
    # only after the previous stage's evaluation has fully completed.
    seed_for_bcde = seeds[0] if seeds else 2025

    if stats.status == "running" and stats.completed_q3_evaluations < cap:
        # === Stage B ===
        b_records = _build_stage_b_records(
            stage_a_results, seed=seed_for_bcde,
            q2_code_sha=q2_code_sha, q3_code_sha=q3_code_sha,
            start_idx=len(all_records_phase1),
        )
        all_records_phase1.extend(b_records)
        print(
            f"[FORMAL] stage B ready: {len(b_records)} records, "
            f"built from {len(stage_a_results)} Stage A results",
            flush=True,
        )
        for rec in b_records:
            ok = _eval_one(
                rec, evaluator, q2_code_sha, q3_code_sha,
                stats, start_time, wall_clock_cap, cap,
            )
            if not ok:
                break
            _write_checkpoint(
                stats, all_records_phase1, execution_head_sha,
                contract_snapshot_sha256, q2_code_sha, q3_code_sha,
                q3_search_code_sha, checkpoint_path,
            )

    # Refresh pool with Stage A+B real results
    pool_ab = list(pool)
    for rec_dict in stats.completed_records:
        if rec_dict.get("stage") in ("A", "B") and rec_dict.get("valid") \
                and rec_dict.get("status") == "ok":
            dur = float(rec_dict.get("total_union_duration_s", 0.0))
            if dur <= 0:
                continue
            cand_payload = next(
                (r for r in all_records_phase1
                 if r.schedule_index == rec_dict["schedule_index"]),
                None,
            )
            if cand_payload is None:
                continue
            cand = cand_payload.candidate
            fake_ev = ThreeBombEvaluation(
                candidate=cand, valid=True, status="ok",
                reason="rehydrated_from_completed_records",
                bomb_evaluations=(None, None, None),
                union_intervals=(), total_union_duration_s=dur,
                sample_level=rec_dict.get("profile", "coarse"),
                scan_step_s=rec_dict.get("scan_step", 0.05),
                elapsed_s=rec_dict.get("elapsed_seconds", 0.0),
                q3_evaluation_id=rec_dict.get(
                    "actual_q3_evaluation_id", ""),
                single_bomb_evaluator_calls=3,
            )
            pool_ab.append(fake_ev)

    if stats.status == "running" and stats.completed_q3_evaluations < cap:
        # === Stage C ===
        c_records = _build_stage_c_records(
            pool_ab, seed=seed_for_bcde + 1,
            q2_code_sha=q2_code_sha, q3_code_sha=q3_code_sha,
            start_idx=len(all_records_phase1),
        )
        all_records_phase1.extend(c_records)
        print(
            f"[FORMAL] stage C ready: {len(c_records)} records, "
            f"built from {len(pool_ab)} Stage A+B results",
            flush=True,
        )
        for rec in c_records:
            ok = _eval_one(
                rec, evaluator, q2_code_sha, q3_code_sha,
                stats, start_time, wall_clock_cap, cap,
            )
            if not ok:
                break
            _write_checkpoint(
                stats, all_records_phase1, execution_head_sha,
                contract_snapshot_sha256, q2_code_sha, q3_code_sha,
                q3_search_code_sha, checkpoint_path,
            )

    # Refresh pool with Stage A+B+C real results
    pool_abc = list(pool_ab)
    for rec_dict in stats.completed_records:
        if rec_dict.get("stage") in ("A", "B", "C") and rec_dict.get("valid") \
                and rec_dict.get("status") == "ok":
            dur = float(rec_dict.get("total_union_duration_s", 0.0))
            if dur <= 0:
                continue
            cand_payload = next(
                (r for r in all_records_phase1
                 if r.schedule_index == rec_dict["schedule_index"]),
                None,
            )
            if cand_payload is None:
                continue
            cand = cand_payload.candidate
            fake_ev = ThreeBombEvaluation(
                candidate=cand, valid=True, status="ok",
                reason="rehydrated_from_completed_records",
                bomb_evaluations=(None, None, None),
                union_intervals=(), total_union_duration_s=dur,
                sample_level=rec_dict.get("profile", "coarse"),
                scan_step_s=rec_dict.get("scan_step", 0.05),
                elapsed_s=rec_dict.get("elapsed_seconds", 0.0),
                q3_evaluation_id=rec_dict.get(
                    "actual_q3_evaluation_id", ""),
                single_bomb_evaluator_calls=3,
            )
            pool_abc.append(fake_ev)

    if stats.status == "running" and stats.completed_q3_evaluations < cap:
        # === Stage D ===
        d_records = _build_stage_d_records(
            pool_abc, seed=seed_for_bcde + 2,
            q2_code_sha=q2_code_sha, q3_code_sha=q3_code_sha,
            start_idx=len(all_records_phase1),
        )
        all_records_phase1.extend(d_records)
        print(
            f"[FORMAL] stage D ready: {len(d_records)} records, "
            f"built from {len(pool_abc)} Stage A+B+C results",
            flush=True,
        )
        for rec in d_records:
            ok = _eval_one(
                rec, evaluator, q2_code_sha, q3_code_sha,
                stats, start_time, wall_clock_cap, cap,
            )
            if not ok:
                break
            _write_checkpoint(
                stats, all_records_phase1, execution_head_sha,
                contract_snapshot_sha256, q2_code_sha, q3_code_sha,
                q3_search_code_sha, checkpoint_path,
            )

    # Refresh pool with Stage A+B+C+D real results
    pool_abcd = list(pool_abc)
    for rec_dict in stats.completed_records:
        if rec_dict.get("stage") in ("A", "B", "C", "D") \
                and rec_dict.get("valid") \
                and rec_dict.get("status") == "ok":
            dur = float(rec_dict.get("total_union_duration_s", 0.0))
            if dur <= 0:
                continue
            cand_payload = next(
                (r for r in all_records_phase1
                 if r.schedule_index == rec_dict["schedule_index"]),
                None,
            )
            if cand_payload is None:
                continue
            cand = cand_payload.candidate
            fake_ev = ThreeBombEvaluation(
                candidate=cand, valid=True, status="ok",
                reason="rehydrated_from_completed_records",
                bomb_evaluations=(None, None, None),
                union_intervals=(), total_union_duration_s=dur,
                sample_level=rec_dict.get("profile", "coarse"),
                scan_step_s=rec_dict.get("scan_step", 0.05),
                elapsed_s=rec_dict.get("elapsed_seconds", 0.0),
                q3_evaluation_id=rec_dict.get(
                    "actual_q3_evaluation_id", ""),
                single_bomb_evaluator_calls=3,
            )
            pool_abcd.append(fake_ev)

    if stats.status == "running" and stats.completed_q3_evaluations < cap:
        # === Stage E ===
        e_records = _build_stage_e_records(
            pool_abcd, seed=seed_for_bcde + 3,
            q2_code_sha=q2_code_sha, q3_code_sha=q3_code_sha,
            start_idx=len(all_records_phase1),
        )
        all_records_phase1.extend(e_records)
        print(
            f"[FORMAL] stage E ready: {len(e_records)} records, "
            f"built from {len(pool_abcd)} Stage A+B+C+D results",
            flush=True,
        )
        for rec in e_records:
            ok = _eval_one(
                rec, evaluator, q2_code_sha, q3_code_sha,
                stats, start_time, wall_clock_cap, cap,
            )
            if not ok:
                break
            _write_checkpoint(
                stats, all_records_phase1, execution_head_sha,
                contract_snapshot_sha256, q2_code_sha, q3_code_sha,
                q3_search_code_sha, checkpoint_path,
            )

    if stats.status == "running":
        stats.status = "pilot_complete"
    stats.current_process_elapsed_seconds = time.perf_counter() - start_time
    stats.elapsed_seconds_total = (
        stats.previous_elapsed_seconds_total
        + stats.current_process_elapsed_seconds
    )
    stats.elapsed_seconds = stats.current_process_elapsed_seconds

    return _build_formal_summary(
        stats, all_records_phase1,
        start_time, execution_head_sha,
        contract_snapshot_sha256, q2_code_sha, q3_code_sha,
        q3_search_code_sha, output_dir, checkpoint_path,
    )


def _write_checkpoint(
    stats: FormalSearchStats, all_records: List[FormalScheduleRecord],
    execution_head_sha: str, contract_snapshot_sha256: str,
    q2_code_sha: str, q3_code_sha: str, q3_search_code_sha: str,
    checkpoint_path: str,
) -> None:
    best_cand_payload = None
    best_ev_payload = None
    if stats.current_best_candidate is not None:
        c = stats.current_best_candidate
        best_cand_payload = {
            "heading_rad": c.heading_rad, "speed_mps": c.speed_mps,
            "release_time_1_s": c.release_time_1_s, "delay_1_s": c.delay_1_s,
            "release_time_2_s": c.release_time_2_s, "delay_2_s": c.delay_2_s,
            "release_time_3_s": c.release_time_3_s, "delay_3_s": c.delay_3_s,
        }
    if stats.current_best_evaluation is not None:
        ev = stats.current_best_evaluation
        best_ev_payload = {
            "valid": ev.valid, "status": ev.status, "reason": ev.reason,
            "total_union_duration_s": ev.total_union_duration_s,
            "union_intervals": [list(iv) for iv in ev.union_intervals],
            "per_bomb_intervals": [
                [list(iv) for iv in ev.bomb_evaluations[0].intervals],
                [list(iv) for iv in ev.bomb_evaluations[1].intervals],
                [list(iv) for iv in ev.bomb_evaluations[2].intervals],
            ] if ev.bomb_evaluations[0] is not None else [[], [], []],
            "per_bomb_duration_s": [
                ev.bomb_evaluations[0].total_duration_s,
                ev.bomb_evaluations[1].total_duration_s,
                ev.bomb_evaluations[2].total_duration_s,
            ] if ev.bomb_evaluations[0] is not None else [0.0, 0.0, 0.0],
            "sample_level": ev.sample_level, "scan_step_s": ev.scan_step_s,
            "q3_evaluation_id": ev.q3_evaluation_id,
            "single_bomb_evaluator_calls": ev.single_bomb_evaluator_calls,
        }
    else:
        # We only have duration from stats; build minimal payload
        best_ev_payload = {
            "total_union_duration_s": stats.current_best_union_duration,
        }
    payload = {
        "checkpoint_schema_version": CHECKPOINT_SCHEMA_VERSION,
        "task_id": "TASK_006",
        "phase_id": "TASK_006-P2",
        "contract_version": 3,
        "candidate_schema_version": CANDIDATE_SCHEMA_VERSION,
        "formal_config_sha256": FORMAL_CONFIG_SHA256,
        "execution_head_sha": execution_head_sha,
        "contract_snapshot_sha256": contract_snapshot_sha256,
        "q2_single_bomb_code_sha256": q2_code_sha,
        "q3_three_bombs_code_sha256": q3_code_sha,
        "q3_search_code_sha256": q3_search_code_sha,
        "completed_q3_evaluations": stats.completed_q3_evaluations,
        "attempted_candidates": stats.attempted_candidates,
        "accepted_candidates": stats.accepted_candidates,
        "rejected_candidates": stats.rejected_candidates,
        "system_error_count": stats.system_error_count,
        "single_bomb_evaluator_calls": stats.single_bomb_evaluator_calls,
        "evaluated_q3_ids": list(stats.evaluated_q3_ids),
        "stage_counts": dict(stats.stage_counts),
        "elapsed_seconds": stats.elapsed_seconds,
        # Cumulative wall-clock accounting (P2C §十):
        # previous_elapsed_seconds_total = cumulative from earlier runs
        # current_process_elapsed_seconds = within-process perf_counter delta
        # elapsed_seconds_total = previous + current (cumulative)
        "previous_elapsed_seconds_total": (
            stats.previous_elapsed_seconds_total
        ),
        "current_process_elapsed_seconds": (
            stats.current_process_elapsed_seconds
        ),
        "elapsed_seconds_total": stats.elapsed_seconds_total,
        "next_schedule_index": stats.next_schedule_index,
        "completed_records": list(stats.completed_records),
        "current_best_candidate": best_cand_payload,
        "current_best_evaluation_payload": best_ev_payload,
        "status": stats.status,
    }
    _atomic_write_json(checkpoint_path, payload)


def start_time_for_total() -> float:
    return 0.0


def _build_formal_summary(
    stats: FormalSearchStats, all_records: List[FormalScheduleRecord],
    start_time: float, execution_head_sha: str,
    contract_snapshot_sha256: str, q2_code_sha: str, q3_code_sha: str,
    q3_search_code_sha: str, output_dir: str, checkpoint_path: str,
) -> dict:
    """Build the canonical formal search summary JSON."""
    elapsed = time.perf_counter() - start_time
    # per-profile timing stats
    timing = {}
    for prof, d in stats.per_profile_timing.items():
        ds = d["durations"]
        if ds:
            timing[prof] = {
                "count": d["count"],
                "median_seconds": float(statistics.median(ds)),
                "p90_seconds": float(sorted(ds)[
                    min(len(ds) - 1, int(0.9 * len(ds)))
                ]),
            }
        else:
            timing[prof] = {"count": 0, "median_seconds": 0.0,
                             "p90_seconds": 0.0}

    # stage counts
    stage_counts = dict(stats.stage_counts)
    stage_counts["total"] = sum(stats.stage_counts.values())

    # best candidate payload
    best_cand_payload = None
    if stats.current_best_candidate is not None:
        c = stats.current_best_candidate
        best_cand_payload = {
            "heading_rad": c.heading_rad, "speed_mps": c.speed_mps,
            "release_time_1_s": c.release_time_1_s, "delay_1_s": c.delay_1_s,
            "release_time_2_s": c.release_time_2_s, "delay_2_s": c.delay_2_s,
            "release_time_3_s": c.release_time_3_s, "delay_3_s": c.delay_3_s,
        }

    summary = {
        "phase_id": "TASK_006-P2",
        "contract_version": 3,
        "result_level": {
            "declared_level": "BUDGET_LIMITED_BEST_KNOWN",
            "local_convergence_established": False,
            "not_a_proven_global_optimum": True,
            "not_a_formal_q3_result": True,
            "result1_xlsx_generated": False,
        },
        "stage_counts": stage_counts,
        "counts": {
            "completed_q3_evaluations": stats.completed_q3_evaluations,
            "attempted_candidates": stats.attempted_candidates,
            "accepted_candidates": stats.accepted_candidates,
            "rejected_candidates": stats.rejected_candidates,
            "system_error_count": stats.system_error_count,
            "single_bomb_evaluator_calls": stats.single_bomb_evaluator_calls,
            "unique_q3_evaluation_ids": len(stats.unique_q3_evaluation_ids),
        },
        "best_candidate": best_cand_payload,
        "best_total_union_duration_s": stats.current_best_union_duration,
        "timing": timing,
        "total_wall_clock_seconds": elapsed,
        "status": {
            "pilot_complete": stats.status == "pilot_complete",
            "evaluation_budget_exhausted":
                stats.status == "EVALUATION_BUDGET_EXHAUSTED",
            "wall_clock_gate_hit": stats.status == "WALL_CLOCK_GATE_HIT",
            "run_system_error": stats.status == "RUN_SYSTEM_ERROR",
            "resume_identity_mismatch":
                stats.status == "RESUME_IDENTITY_MISMATCH",
            "checkpoint_load_error":
                stats.status == "CHECKPOINT_LOAD_ERROR",
            "raw_status": stats.status,
        },
        "identity": {
            "execution_head_sha": execution_head_sha,
            "contract_snapshot_sha256": contract_snapshot_sha256,
            "q2_single_bomb_code_sha256": q2_code_sha,
            "q3_three_bombs_code_sha256": q3_code_sha,
            "q3_search_code_sha256": q3_search_code_sha,
            "formal_config_sha256": FORMAL_CONFIG_SHA256,
            "candidate_schema_version": CANDIDATE_SCHEMA_VERSION,
            "checkpoint_schema_version": CHECKPOINT_SCHEMA_VERSION,
            "checkpoint_path": checkpoint_path,
            "formal_run_identity_sha256": hashlib.sha256(
                json.dumps({
                    "formal_config_sha256": FORMAL_CONFIG_SHA256,
                    "q2_single_bomb_code_sha256": q2_code_sha,
                    "q3_three_bombs_code_sha256": q3_code_sha,
                    "q3_search_code_sha256": q3_search_code_sha,
                    "candidate_schema_version": CANDIDATE_SCHEMA_VERSION,
                    "execution_head_sha": execution_head_sha,
                    "stage_counts": stage_counts,
                    "completed_q3_evaluations":
                        stats.completed_q3_evaluations,
                }, sort_keys=True).encode("utf-8")
            ).hexdigest(),
        },
        "pilot_evidence_preservation": {
            "original_pilot_execution_head":
                "4d442a7a16127ca0166d1114656b5fe4d5546b4d",
            "original_evidence_commit":
                "59999f9aba063e90d8428f5f783d8cc4abf10d62",
            "closure_code_head": "a139988",
            "closure_evidence_head": "31ddb7b516e05eb6c20ac465e13b339b6ab70dbc",
            "pilot_rerun_performed": False,
        },
        "p2_contract_snapshot_path":
            "work/task_contracts/TASK_006-P2-v3.json",
    }

    out_path = os.path.join(output_dir, "q3_formal_search_summary.json")
    _atomic_write_json(out_path, summary)
    return summary


# === Candidate closure runner (TASK_006-P2C, contract_version=4) ===

def _write_closure_checkpoint(
    stats: FormalSearchStats, all_records: List[FormalScheduleRecord],
    execution_head_sha: str, contract_snapshot_sha256: str,
    q2_code_sha: str, q3_code_sha: str, q3_search_code_sha: str,
    closure_schedule_sha256: str,
    checkpoint_path: str,
) -> None:
    """Atomic write closure checkpoint (8-field identity + cumulative wall-clock)."""
    best_cand_payload = None
    best_ev_payload = None
    if stats.current_best_candidate is not None:
        c = stats.current_best_candidate
        best_cand_payload = {
            "heading_rad": c.heading_rad, "speed_mps": c.speed_mps,
            "release_time_1_s": c.release_time_1_s, "delay_1_s": c.delay_1_s,
            "release_time_2_s": c.release_time_2_s, "delay_2_s": c.delay_2_s,
            "release_time_3_s": c.release_time_3_s, "delay_3_s": c.delay_3_s,
        }
    if stats.current_best_evaluation is not None:
        ev = stats.current_best_evaluation
        best_ev_payload = {
            "valid": ev.valid, "status": ev.status, "reason": ev.reason,
            "total_union_duration_s": ev.total_union_duration_s,
            "union_intervals": [list(iv) for iv in ev.union_intervals],
            "per_bomb_intervals": [
                [list(iv) for iv in ev.bomb_evaluations[0].intervals],
                [list(iv) for iv in ev.bomb_evaluations[1].intervals],
                [list(iv) for iv in ev.bomb_evaluations[2].intervals],
            ] if ev.bomb_evaluations[0] is not None else [[], [], []],
            "per_bomb_duration_s": [
                ev.bomb_evaluations[0].total_duration_s,
                ev.bomb_evaluations[1].total_duration_s,
                ev.bomb_evaluations[2].total_duration_s,
            ] if ev.bomb_evaluations[0] is not None else [0.0, 0.0, 0.0],
            "sample_level": ev.sample_level, "scan_step_s": ev.scan_step_s,
            "q3_evaluation_id": ev.q3_evaluation_id,
            "single_bomb_evaluator_calls": ev.single_bomb_evaluator_calls,
        }
    else:
        best_ev_payload = {
            "total_union_duration_s": stats.current_best_union_duration,
        }
    payload = {
        "checkpoint_schema_version": CLOSURE_CHECKPOINT_SCHEMA_VERSION,
        "task_id": "TASK_006",
        "phase_id": "TASK_006-P2C",
        "contract_version": 4,
        "candidate_schema_version": CANDIDATE_SCHEMA_VERSION,
        "closure_config_sha256": CLOSURE_CONFIG_SHA256,
        "closure_schedule_sha256": closure_schedule_sha256,
        "execution_head_sha": execution_head_sha,
        "contract_snapshot_sha256": contract_snapshot_sha256,
        "q2_single_bomb_code_sha256": q2_code_sha,
        "q3_three_bombs_code_sha256": q3_code_sha,
        "q3_search_code_sha256": q3_search_code_sha,
        "completed_q3_evaluations": stats.completed_q3_evaluations,
        "attempted_candidates": stats.attempted_candidates,
        "accepted_candidates": stats.accepted_candidates,
        "rejected_candidates": stats.rejected_candidates,
        "system_error_count": stats.system_error_count,
        "single_bomb_evaluator_calls": stats.single_bomb_evaluator_calls,
        "evaluated_q3_ids": list(stats.evaluated_q3_ids),
        "stage_counts": dict(stats.stage_counts),
        "elapsed_seconds": stats.elapsed_seconds,
        "previous_elapsed_seconds_total": (
            stats.previous_elapsed_seconds_total
        ),
        "current_process_elapsed_seconds": (
            stats.current_process_elapsed_seconds
        ),
        "elapsed_seconds_total": stats.elapsed_seconds_total,
        "next_schedule_index": stats.next_schedule_index,
        "completed_records": list(stats.completed_records),
        "current_best_candidate": best_cand_payload,
        "current_best_evaluation_payload": best_ev_payload,
        "status": stats.status,
    }
    _atomic_write_json(checkpoint_path, payload)


def run_candidate_closure(
    incumbent_payload: dict,
    execution_head_sha: str,
    contract_snapshot_sha256: str,
    output_dir: str = "outputs/q3",
    checkpoint_path: str = "work/q3_candidate_closure/checkpoint.json",
    wall_clock_cap: float = CLOSURE_WALL_CLOCK_CAP_SECONDS,
    evaluator: Optional[Callable] = None,
    fake_dry_run: bool = False,
) -> dict:
    """Run Q3 candidate closure (TASK_006-P2C, 32 evals / 600 s).

    Inputs:
      - incumbent_payload: dict with 8 fields (heading_rad, speed_mps,
        release_time_1_s, delay_1_s, release_time_2_s, delay_2_s,
        release_time_3_s, delay_3_s) — original P2 incumbent at coarse
        (0.05) profile.

    Sequential stage propagation (F1→F2→F3→F4→F5). Each stage's records
    are built only after the previous stage's evaluation has fully completed.

    8-field resume identity (fail-closed). Cumulative wall-clock tracking.

    Returns closure summary dict (also written to
    outputs/q3/q3_candidate_closure_summary.json).
    """
    if evaluator is None:
        if fake_dry_run:
            evaluator = fake_evaluator_for_tests
        else:
            evaluator = lambda cand, prof, ss: evaluate_three_bomb_strategy(
                cand, sample_level=prof, scan_step=ss,
                code_identity_sha256=compute_q2_single_bomb_code_sha256(),
                pilot_config_sha256=PILOT_CONFIG_SHA256,
            )

    incumbent_candidate = _dict_to_candidate(incumbent_payload)
    ok, reason = validate_candidate(incumbent_candidate)
    if not ok:
        raise ValueError(
            f"incumbent candidate invalid: {reason}"
        )

    q2_code_sha = compute_q2_single_bomb_code_sha256()
    q3_code_sha = compute_q3_three_bombs_code_sha256()
    q3_search_code_sha = compute_q3_search_code_sha256()

    cap = CLOSURE_TOTAL_BUDGET

    stats = FormalSearchStats()
    start_time = time.perf_counter()

    # Compute F1 records first (these are deterministic and can be built
    # up-front without depending on prior stage results). F1 SHA enters the
    # resume identity. F2 records are also deterministic.
    f1_records = _build_stage_f1_records(
        incumbent_candidate, seed=2025,
        q2_code_sha=q2_code_sha, q3_code_sha=q3_code_sha,
        start_idx=0,
    )
    f2_records = _build_stage_f2_records(
        incumbent_candidate, seed=2026,
        q2_code_sha=q2_code_sha, q3_code_sha=q3_code_sha,
        start_idx=len(f1_records),
    )
    # Build pre-known portion of schedule for SHA computation
    pre_known_records = list(f1_records) + list(f2_records)
    # F3/F4/F5 will be appended at runtime; their contribution to SHA is
    # fixed once built (per-stage immutability).
    pre_known_sha = _compute_closure_schedule_sha256(pre_known_records)
    # closure_schedule_sha256 is fixed as the SHA of the deterministic
    # F1+F2 portion; F3/F4/F5 records are appended during run and their
    # SHA contribution is checked via per-stage immutability (each stage's
    # records are built once and never mutated).
    closure_schedule_sha256 = pre_known_sha

    # Resume check (8-field identity)
    if os.path.exists(checkpoint_path):
        try:
            with open(checkpoint_path, "r", encoding="utf-8") as f:
                old = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            stats.status = "CHECKPOINT_LOAD_ERROR"
            print(
                f"[CLOSURE] checkpoint load error ({e!r}); "
                f"fail-closed — exit 2",
                file=sys.stderr, flush=True,
            )
            return _build_candidate_closure_summary(
                stats, pre_known_records,
                start_time, execution_head_sha,
                contract_snapshot_sha256, q2_code_sha, q3_code_sha,
                q3_search_code_sha, output_dir, checkpoint_path,
                closure_schedule_sha256, incumbent_payload,
            )
        if not _verify_closure_resume_identity(
            old, execution_head_sha, contract_snapshot_sha256,
            q2_code_sha, q3_code_sha, q3_search_code_sha,
            CLOSURE_CONFIG_SHA256, CANDIDATE_SCHEMA_VERSION,
            closure_schedule_sha256,
        ):
            stats.status = "RESUME_IDENTITY_MISMATCH"
            print(
                f"[CLOSURE] checkpoint identity mismatch — refusing resume",
                file=sys.stderr, flush=True,
            )
            return _build_candidate_closure_summary(
                stats, pre_known_records,
                start_time, execution_head_sha,
                contract_snapshot_sha256, q2_code_sha, q3_code_sha,
                q3_search_code_sha, output_dir, checkpoint_path,
                closure_schedule_sha256, incumbent_payload,
            )
        # identity OK: restore stats (cumulative)
        print(
            f"[CLOSURE] resuming from checkpoint "
            f"(next_schedule_index={old.get('next_schedule_index', 0)}, "
            f"completed={old.get('completed_q3_evaluations', 0)}, "
            f"status={old.get('status')})",
            flush=True,
        )
        stats.completed_q3_evaluations = old.get("completed_q3_evaluations", 0)
        stats.attempted_candidates = old.get("attempted_candidates", 0)
        stats.accepted_candidates = old.get("accepted_candidates", 0)
        stats.rejected_candidates = old.get("rejected_candidates", 0)
        stats.system_error_count = old.get("system_error_count", 0)
        stats.single_bomb_evaluator_calls = old.get(
            "single_bomb_evaluator_calls", 0)
        stats.elapsed_seconds = old.get("elapsed_seconds", 0.0)
        stats.previous_elapsed_seconds_total = float(
            old.get("previous_elapsed_seconds_total",
                    old.get("elapsed_seconds_total", 0.0))
        )
        stats.current_process_elapsed_seconds = 0.0
        stats.elapsed_seconds_total = stats.previous_elapsed_seconds_total
        old_ids = old.get("evaluated_q3_ids", [])
        stats.evaluated_q3_ids = list(old_ids)
        stats.unique_q3_evaluation_ids = set(old_ids)
        old_stage_counts = old.get("stage_counts", {})
        for k in stats.stage_counts:
            stats.stage_counts[k] = int(old_stage_counts.get(k, 0))
        stats.completed_records = list(old.get("completed_records", []))
        stats.next_schedule_index = int(old.get("next_schedule_index", 0))
        old_best_payload = old.get("current_best_candidate", None)
        old_best_ev_payload = old.get("current_best_evaluation_payload", None)
        if old_best_payload and old_best_ev_payload:
            stats.current_best_candidate = ThreeBombCandidate(**old_best_payload)
            stats.current_best_union_duration = float(
                old_best_ev_payload.get("total_union_duration_s", 0.0))
        if old.get("status") in (
            "pilot_complete", "EVALUATION_BUDGET_EXHAUSTED",
            "WALL_CLOCK_GATE_HIT", "RUN_SYSTEM_ERROR",
            "RESUME_IDENTITY_MISMATCH", "CHECKPOINT_LOAD_ERROR",
        ):
            stats.status = old["status"]
            print(
                f"[CLOSURE] previous run already terminated "
                f"(status={stats.status}); emitting summary only",
                flush=True,
            )
            return _build_candidate_closure_summary(
                stats, pre_known_records,
                start_time, execution_head_sha,
                contract_snapshot_sha256, q2_code_sha, q3_code_sha,
                q3_search_code_sha, output_dir, checkpoint_path,
                closure_schedule_sha256, incumbent_payload,
            )

    # Establish incumbent baseline (cheap placeholder for F3/F4/F5 parent
    # selection). NOT counted in the 32-ev budget. F3's first record IS
    # the incumbent evaluation at medium profile.
    incumbent_baseline_ev: Optional[ThreeBombEvaluation] = None

    # === F1 (16 evals) ===
    if (stats.status == "running"
            and stats.completed_q3_evaluations < cap):
        for rec in f1_records:
            ok = _eval_one(
                rec, evaluator, q2_code_sha, q3_code_sha,
                stats, start_time, wall_clock_cap, cap,
            )
            if not ok:
                break
            _write_closure_checkpoint(
                stats, pre_known_records, execution_head_sha,
                contract_snapshot_sha256, q2_code_sha, q3_code_sha,
                q3_search_code_sha, closure_schedule_sha256,
                checkpoint_path,
            )
        # Track F1 best
        f1_top = sorted(
            [r for r in stats.completed_records
             if r.get("stage") == "F1" and r.get("valid")
             and r.get("status") == "ok"],
            key=lambda r: r.get("total_union_duration_s", 0.0),
            reverse=True,
        )
        if f1_top:
            f1_best_dur = float(f1_top[0]["total_union_duration_s"])
            stats.closure_f1_best = (
                stats.current_best_evaluation
                if (stats.current_best_union_duration >= f1_best_dur)
                else _make_baseline_eval_from_record(f1_top[0], incumbent_candidate)
            )

    # === F2 (8 evals) ===
    if (stats.status == "running"
            and stats.completed_q3_evaluations < cap):
        for rec in f2_records:
            ok = _eval_one(
                rec, evaluator, q2_code_sha, q3_code_sha,
                stats, start_time, wall_clock_cap, cap,
            )
            if not ok:
                break
            _write_closure_checkpoint(
                stats, pre_known_records, execution_head_sha,
                contract_snapshot_sha256, q2_code_sha, q3_code_sha,
                q3_search_code_sha, closure_schedule_sha256,
                checkpoint_path,
            )

    # Refresh F1+F2 results list for F3 parent selection
    f1_f2_records = [r for r in stats.completed_records
                     if r.get("stage") in ("F1", "F2")
                     and r.get("valid") and r.get("status") == "ok"]
    f1_f2_pool: List[ThreeBombEvaluation] = []
    for rec_dict in f1_f2_records:
        dur = float(rec_dict.get("total_union_duration_s", 0.0))
        if dur <= 0:
            continue
        cand_payload = next(
            (r for r in pre_known_records
             if r.schedule_index == rec_dict["schedule_index"]),
            None,
        )
        if cand_payload is None:
            continue
        cand = cand_payload.candidate
        fake_ev = ThreeBombEvaluation(
            candidate=cand, valid=True, status="ok",
            reason="rehydrated_from_completed_records",
            bomb_evaluations=(None, None, None),
            union_intervals=(), total_union_duration_s=dur,
            sample_level=rec_dict.get("profile", "coarse"),
            scan_step_s=rec_dict.get("scan_step", 0.05),
            elapsed_s=rec_dict.get("elapsed_seconds", 0.0),
            q3_evaluation_id=rec_dict.get("actual_q3_evaluation_id", ""),
            single_bomb_evaluator_calls=3,
        )
        f1_f2_pool.append(fake_ev)
    # Add incumbent baseline evaluation
    if incumbent_baseline_ev is not None:
        f1_f2_pool.append(incumbent_baseline_ev)

    # === F3 (4 evals: incumbent + top-3 from F1+F2) ===
    # Build F3 records now from real F1/F2 results
    if (stats.status == "running"
            and stats.completed_q3_evaluations < cap):
        incumbent_cand, challenger_cands = _select_f3_parents(
            incumbent_candidate, f1_f2_pool, [],
            top_k=3,
        )
        f3_records = _build_stage_f3_records(
            incumbent_cand, challenger_cands, seed=2027,
            q2_code_sha=q2_code_sha, q3_code_sha=q3_code_sha,
            start_idx=len(pre_known_records),
        )
        pre_known_records.extend(f3_records)
        stats.closure_f3_records = list(f3_records)
        for rec in f3_records:
            ok = _eval_one(
                rec, evaluator, q2_code_sha, q3_code_sha,
                stats, start_time, wall_clock_cap, cap,
            )
            if not ok:
                break
            _write_closure_checkpoint(
                stats, pre_known_records, execution_head_sha,
                contract_snapshot_sha256, q2_code_sha, q3_code_sha,
                q3_search_code_sha, closure_schedule_sha256,
                checkpoint_path,
            )

    # === F4 (2 evals: incumbent + best F3 challenger) ===
    f3_records_run = [r for r in stats.completed_records
                      if r.get("stage") == "F3"
                      and r.get("valid") and r.get("status") == "ok"]
    f3_pool: List[ThreeBombEvaluation] = []
    for rec_dict in f3_records_run:
        dur = float(rec_dict.get("total_union_duration_s", 0.0))
        if dur <= 0:
            continue
        cand_payload = next(
            (r for r in pre_known_records
             if r.schedule_index == rec_dict["schedule_index"]),
            None,
        )
        if cand_payload is None:
            continue
        cand = cand_payload.candidate
        fake_ev = ThreeBombEvaluation(
            candidate=cand, valid=True, status="ok",
            reason="rehydrated_from_completed_records",
            bomb_evaluations=(None, None, None),
            union_intervals=(), total_union_duration_s=dur,
            sample_level=rec_dict.get("profile", "coarse"),
            scan_step_s=rec_dict.get("scan_step", 0.05),
            elapsed_s=rec_dict.get("elapsed_seconds", 0.0),
            q3_evaluation_id=rec_dict.get("actual_q3_evaluation_id", ""),
            single_bomb_evaluator_calls=3,
        )
        f3_pool.append(fake_ev)
    if (stats.status == "running"
            and stats.completed_q3_evaluations < cap):
        # F4 challenger = best non-incumbent F3 result
        f3_pool_sorted = sorted(
            f3_pool, key=lambda e: e.total_union_duration_s, reverse=True)
        f4_challenger_cand = (
            f3_pool_sorted[0].candidate if f3_pool_sorted
            else incumbent_candidate
        )
        f4_records = _build_stage_f4_records(
            incumbent_candidate, f4_challenger_cand, seed=2028,
            q2_code_sha=q2_code_sha, q3_code_sha=q3_code_sha,
            start_idx=len(pre_known_records),
        )
        pre_known_records.extend(f4_records)
        stats.closure_f4_records = list(f4_records)
        for rec in f4_records:
            ok = _eval_one(
                rec, evaluator, q2_code_sha, q3_code_sha,
                stats, start_time, wall_clock_cap, cap,
            )
            if not ok:
                break
            _write_closure_checkpoint(
                stats, pre_known_records, execution_head_sha,
                contract_snapshot_sha256, q2_code_sha, q3_code_sha,
                q3_search_code_sha, closure_schedule_sha256,
                checkpoint_path,
            )

    # === F5 (2 evals: incumbent + best F4 challenger) ===
    f4_records_run = [r for r in stats.completed_records
                      if r.get("stage") == "F4"
                      and r.get("valid") and r.get("status") == "ok"]
    f4_pool: List[ThreeBombEvaluation] = []
    for rec_dict in f4_records_run:
        dur = float(rec_dict.get("total_union_duration_s", 0.0))
        if dur <= 0:
            continue
        cand_payload = next(
            (r for r in pre_known_records
             if r.schedule_index == rec_dict["schedule_index"]),
            None,
        )
        if cand_payload is None:
            continue
        cand = cand_payload.candidate
        fake_ev = ThreeBombEvaluation(
            candidate=cand, valid=True, status="ok",
            reason="rehydrated_from_completed_records",
            bomb_evaluations=(None, None, None),
            union_intervals=(), total_union_duration_s=dur,
            sample_level=rec_dict.get("profile", "fine"),
            scan_step_s=rec_dict.get("scan_step", 0.01),
            elapsed_s=rec_dict.get("elapsed_seconds", 0.0),
            q3_evaluation_id=rec_dict.get("actual_q3_evaluation_id", ""),
            single_bomb_evaluator_calls=3,
        )
        f4_pool.append(fake_ev)
    if (stats.status == "running"
            and stats.completed_q3_evaluations < cap):
        f4_pool_sorted = sorted(
            f4_pool, key=lambda e: e.total_union_duration_s, reverse=True)
        f5_challenger_cand = (
            f4_pool_sorted[0].candidate if f4_pool_sorted
            else incumbent_candidate
        )
        f5_records = _build_stage_f5_records(
            incumbent_candidate, f5_challenger_cand, seed=2029,
            q2_code_sha=q2_code_sha, q3_code_sha=q3_code_sha,
            start_idx=len(pre_known_records),
        )
        pre_known_records.extend(f5_records)
        stats.closure_f5_records = list(f5_records)
        for rec in f5_records:
            ok = _eval_one(
                rec, evaluator, q2_code_sha, q3_code_sha,
                stats, start_time, wall_clock_cap, cap,
            )
            if not ok:
                break
            _write_closure_checkpoint(
                stats, pre_known_records, execution_head_sha,
                contract_snapshot_sha256, q2_code_sha, q3_code_sha,
                q3_search_code_sha, closure_schedule_sha256,
                checkpoint_path,
            )

    # Final canonical selection
    all_evs = []
    for rec_dict in stats.completed_records:
        if rec_dict.get("valid") and rec_dict.get("status") == "ok":
            dur = float(rec_dict.get("total_union_duration_s", 0.0))
            if dur <= 0:
                continue
            cand_payload = next(
                (r for r in pre_known_records
                 if r.schedule_index == rec_dict["schedule_index"]),
                None,
            )
            if cand_payload is None:
                continue
            cand = cand_payload.candidate
            fake_ev = ThreeBombEvaluation(
                candidate=cand, valid=True, status="ok",
                reason=rec_dict.get("reason", ""),
                bomb_evaluations=(None, None, None),
                union_intervals=(), total_union_duration_s=dur,
                sample_level=rec_dict.get("profile", "coarse"),
                scan_step_s=rec_dict.get("scan_step", 0.05),
                elapsed_s=rec_dict.get("elapsed_seconds", 0.0),
                q3_evaluation_id=rec_dict.get("actual_q3_evaluation_id", ""),
                single_bomb_evaluator_calls=3,
            )
            all_evs.append(fake_ev)
    canonical_ev = _select_canonical_closure_candidate(
        ThreeBombEvaluation(
            candidate=incumbent_candidate, valid=True, status="ok",
            reason="incumbent_anchor",
            bomb_evaluations=(None, None, None),
            union_intervals=(),
            total_union_duration_s=0.0,
            sample_level="coarse", scan_step_s=0.05,
            elapsed_s=0.0, q3_evaluation_id="",
            single_bomb_evaluator_calls=3,
        ), all_evs)
    if canonical_ev is not None:
        stats.current_best_evaluation = canonical_ev
        stats.current_best_candidate = canonical_ev.candidate
        stats.current_best_union_duration = canonical_ev.total_union_duration_s

    if stats.status == "running":
        stats.status = "pilot_complete"
    stats.current_process_elapsed_seconds = time.perf_counter() - start_time
    stats.elapsed_seconds_total = (
        stats.previous_elapsed_seconds_total
        + stats.current_process_elapsed_seconds
    )
    stats.elapsed_seconds = stats.current_process_elapsed_seconds

    return _build_candidate_closure_summary(
        stats, pre_known_records,
        start_time, execution_head_sha,
        contract_snapshot_sha256, q2_code_sha, q3_code_sha,
        q3_search_code_sha, output_dir, checkpoint_path,
        closure_schedule_sha256, incumbent_payload,
    )


def _make_baseline_eval_from_record(rec_dict, cand):
    """Construct a placeholder ThreeBombEvaluation from a completed record."""
    dur = float(rec_dict.get("total_union_duration_s", 0.0))
    return ThreeBombEvaluation(
        candidate=cand, valid=True, status="ok",
        reason=rec_dict.get("reason", ""),
        bomb_evaluations=(None, None, None),
        union_intervals=(), total_union_duration_s=dur,
        sample_level=rec_dict.get("profile", "coarse"),
        scan_step_s=rec_dict.get("scan_step", 0.05),
        elapsed_s=rec_dict.get("elapsed_seconds", 0.0),
        q3_evaluation_id=rec_dict.get("actual_q3_evaluation_id", ""),
        single_bomb_evaluator_calls=3,
    )


def _build_candidate_closure_summary(
    stats: FormalSearchStats, all_records: List[FormalScheduleRecord],
    start_time: float, execution_head_sha: str,
    contract_snapshot_sha256: str, q2_code_sha: str, q3_code_sha: str,
    q3_search_code_sha: str, output_dir: str, checkpoint_path: str,
    closure_schedule_sha256: str, incumbent_payload: dict,
) -> dict:
    """Build the canonical closure summary JSON."""
    timing = {}
    for prof, d in stats.per_profile_timing.items():
        ds = d["durations"]
        if ds:
            timing[prof] = {
                "count": d["count"],
                "median_seconds": float(statistics.median(ds)),
                "p90_seconds": float(sorted(ds)[
                    min(len(ds) - 1, int(0.9 * len(ds)))
                ]),
            }
        else:
            timing[prof] = {"count": 0, "median_seconds": 0.0,
                             "p90_seconds": 0.0}

    stage_counts = dict(stats.stage_counts)
    stage_counts["total"] = sum(stats.stage_counts.values())

    # Canonical Q3 candidate payload (full 3-bomb evidence)
    canonical_payload = None
    canonical_evidence = None
    if stats.current_best_evaluation is not None:
        ev = stats.current_best_evaluation
        c = ev.candidate
        canonical_payload = {
            "heading_rad": c.heading_rad, "speed_mps": c.speed_mps,
            "release_time_1_s": c.release_time_1_s, "delay_1_s": c.delay_1_s,
            "release_time_2_s": c.release_time_2_s, "delay_2_s": c.delay_2_s,
            "release_time_3_s": c.release_time_3_s, "delay_3_s": c.delay_3_s,
        }
        if (ev.bomb_evaluations is not None
                and len(ev.bomb_evaluations) == 3
                and ev.bomb_evaluations[0] is not None):
            canonical_evidence = {
                "valid": ev.valid,
                "status": ev.status,
                "reason": ev.reason,
                "total_union_duration_s": ev.total_union_duration_s,
                "union_intervals": [list(iv) for iv in ev.union_intervals],
                "per_bomb_intervals": [
                    [list(iv) for iv in ev.bomb_evaluations[0].intervals],
                    [list(iv) for iv in ev.bomb_evaluations[1].intervals],
                    [list(iv) for iv in ev.bomb_evaluations[2].intervals],
                ],
                "per_bomb_duration_s": [
                    ev.bomb_evaluations[0].total_duration_s,
                    ev.bomb_evaluations[1].total_duration_s,
                    ev.bomb_evaluations[2].total_duration_s,
                ],
                "sample_level": ev.sample_level,
                "scan_step_s": ev.scan_step_s,
                "q3_evaluation_id": ev.q3_evaluation_id,
                "single_bomb_evaluator_calls": ev.single_bomb_evaluator_calls,
            }
        else:
            canonical_evidence = {
                "total_union_duration_s": ev.total_union_duration_s,
                "rehydrated_from_completed_records": True,
            }

    # Compute absolute / relative improvement vs incumbent reference duration
    incumbent_ref_dur = float(incumbent_payload.get(
        "_reference_duration_s", 4.469013137817385))
    best_dur = stats.current_best_union_duration
    abs_improvement = best_dur - incumbent_ref_dur
    rel_improvement = (
        abs_improvement / incumbent_ref_dur if incumbent_ref_dur > 0 else 0.0
    )

    summary = {
        "phase_id": "TASK_006-P2C",
        "contract_version": 4,
        "result_level": {
            "declared_level": "BUDGET_LIMITED_BEST_KNOWN",
            "local_convergence_established": False,
            "not_a_proven_global_optimum": True,
            "not_a_formal_q3_result": True,
            "result1_xlsx_generated": False,
        },
        "stage_counts": stage_counts,
        "counts": {
            "completed_q3_evaluations": stats.completed_q3_evaluations,
            "attempted_candidates": stats.attempted_candidates,
            "accepted_candidates": stats.accepted_candidates,
            "rejected_candidates": stats.rejected_candidates,
            "system_error_count": stats.system_error_count,
            "single_bomb_evaluator_calls": stats.single_bomb_evaluator_calls,
            "unique_q3_evaluation_ids": len(stats.unique_q3_evaluation_ids),
        },
        "canonical_q3_candidate": canonical_payload,
        "canonical_q3_evidence": canonical_evidence,
        "canonical_total_union_duration_s": stats.current_best_union_duration,
        "comparison": {
            "incumbent_reference_total_union_duration_s": incumbent_ref_dur,
            "absolute_improvement_s": abs_improvement,
            "relative_improvement": rel_improvement,
        },
        "incumbent_high_resolution": {
            "candidate": incumbent_payload,
            "reference_total_union_duration_s": incumbent_ref_dur,
            "source": "TASK_006-P2 stage_E_high_resolution_verification_rank_1",
            "p2_execution_head": "70a4dd767f057edded65bd2011ac544347f661dc",
            "p2_evidence_commit": "dc970a483ab9e05d76467decf63f61dff70f0862",
        },
        "timing": timing,
        "total_wall_clock_seconds": stats.elapsed_seconds_total,
        "previous_elapsed_seconds_total": stats.previous_elapsed_seconds_total,
        "current_process_elapsed_seconds": stats.current_process_elapsed_seconds,
        "status": {
            "pilot_complete": stats.status == "pilot_complete",
            "evaluation_budget_exhausted":
                stats.status == "EVALUATION_BUDGET_EXHAUSTED",
            "wall_clock_gate_hit": stats.status == "WALL_CLOCK_GATE_HIT",
            "run_system_error": stats.status == "RUN_SYSTEM_ERROR",
            "resume_identity_mismatch":
                stats.status == "RESUME_IDENTITY_MISMATCH",
            "checkpoint_load_error":
                stats.status == "CHECKPOINT_LOAD_ERROR",
            "raw_status": stats.status,
        },
        "identity": {
            "execution_head_sha": execution_head_sha,
            "contract_snapshot_sha256": contract_snapshot_sha256,
            "q2_single_bomb_code_sha256": q2_code_sha,
            "q3_three_bombs_code_sha256": q3_code_sha,
            "q3_search_code_sha256": q3_search_code_sha,
            "closure_config_sha256": CLOSURE_CONFIG_SHA256,
            "closure_schedule_sha256": closure_schedule_sha256,
            "candidate_schema_version": CANDIDATE_SCHEMA_VERSION,
            "checkpoint_schema_version": CLOSURE_CHECKPOINT_SCHEMA_VERSION,
            "checkpoint_path": checkpoint_path,
            "closure_run_identity_sha256": hashlib.sha256(
                json.dumps({
                    "closure_config_sha256": CLOSURE_CONFIG_SHA256,
                    "closure_schedule_sha256": closure_schedule_sha256,
                    "q2_single_bomb_code_sha256": q2_code_sha,
                    "q3_three_bombs_code_sha256": q3_code_sha,
                    "q3_search_code_sha256": q3_search_code_sha,
                    "candidate_schema_version": CANDIDATE_SCHEMA_VERSION,
                    "execution_head_sha": execution_head_sha,
                    "stage_counts": stage_counts,
                    "completed_q3_evaluations":
                        stats.completed_q3_evaluations,
                }, sort_keys=True).encode("utf-8")
            ).hexdigest(),
        },
        "original_p2_evidence_preservation": {
            "original_p2_execution_head":
                "70a4dd767f057edded65bd2011ac544347f661dc",
            "original_p2_evidence_commit":
                "dc970a483ab9e05d76467decf63f61dff70f0862",
            "p2_search_rerun_performed": False,
            "original_512_evaluations_preserved": True,
            "original_834_07s_wall_clock_preserved": True,
        },
        "p2c_contract_snapshot_path":
            "work/task_contracts/TASK_006-P2C-v4.json",
    }

    out_path = os.path.join(
        output_dir, "q3_candidate_closure_summary.json")
    _atomic_write_json(out_path, summary)
    return summary


# === CLI ===

def _print_help() -> None:
    print(__doc__)
    print("用法:")
    print("  python -m src.q3_search --formal-search "
          "--budget 512 --wall-clock-cap 1200 "
          "--seeds 2025 2026 2027")
    print("  python -m src.q3_search --dry-run --budget 32 "
          "--seeds 2025")
    print("  python -m src.q3_search --candidate-closure "
          "--budget 32 --wall-clock-cap 600")
    print()
    print("参数:")
    print("  --formal-search      启动 Q3 正式 bounded search (real evaluator)")
    print("  --candidate-closure  启动 TASK_006-P2C candidate closure "
          "(F1=16/F2=8/F3=4/F4=2/F5=2 = 32 evals / 600 s)")
    print("  --dry-run            启动 dry-run (FakeEvaluator, 不消耗 real eval)")
    print("  --budget N           顶层 Q3 candidate evaluation 预算")
    print("                       (formal-search: ≤ 512; closure: ≤ 32)")
    print("  --wall-clock-cap S   wall-clock 上限 (秒, "
          "formal-search 默认 1200; closure 默认 600)")
    print("  --seeds S [S ...]    seeds 列表 (仅 formal-search, 默认 2025 2026 2027)")
    print("  --output-dir D       输出目录 (默认 outputs/q3)")
    print("  --checkpoint-path P  checkpoint 路径")
    print("                       (formal-search: work/q3_formal/checkpoint.json; "
          "closure: work/q3_candidate_closure/checkpoint.json)")
    print("  -h, --help           显示本帮助")
    print()
    print("退出码:")
    print("  0 = pilot_complete (无 system_error, Stage E / F5 完成)")
    print("  1 = system_error / wall_clock_gate_hit / evaluation_budget_exhausted")
    print("  2 = 参数错误 / identity mismatch / checkpoint load error / 预算无效")


def main(argv: Optional[Sequence[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    formal_search = False
    candidate_closure = False
    dry_run = False
    show_help = False
    budget = TOTAL_BUDGET
    wall_clock_cap = DEFAULT_WALL_CLOCK_SECONDS
    seeds = list(DEFAULT_SEEDS)
    output_dir = "outputs/q3"
    checkpoint_path = "work/q3_formal/checkpoint.json"

    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("-h", "--help"):
            show_help = True
            i += 1
            continue
        if a == "--formal-search":
            formal_search = True
            i += 1
            continue
        if a == "--candidate-closure":
            candidate_closure = True
            # switch to closure defaults
            budget = CLOSURE_TOTAL_BUDGET
            wall_clock_cap = CLOSURE_WALL_CLOCK_CAP_SECONDS
            checkpoint_path = "work/q3_candidate_closure/checkpoint.json"
            i += 1
            continue
        if a == "--dry-run":
            dry_run = True
            i += 1
            continue
        if a == "--budget":
            if i + 1 >= len(argv):
                print("--budget 需要参数", file=sys.stderr)
                return 2
            try:
                budget = int(argv[i + 1])
            except ValueError:
                print(f"--budget 解析失败: {argv[i + 1]!r}", file=sys.stderr)
                return 2
            upper = (CLOSURE_TOTAL_BUDGET if candidate_closure
                     else TOTAL_BUDGET)
            if budget < 1 or budget > upper:
                print(
                    f"--budget 必须 ∈ [1, {upper}], 实际 {budget}",
                    file=sys.stderr,
                )
                return 2
            i += 2
            continue
        if a == "--wall-clock-cap":
            if i + 1 >= len(argv):
                print("--wall-clock-cap 需要参数", file=sys.stderr)
                return 2
            try:
                wall_clock_cap = float(argv[i + 1])
            except ValueError:
                print(
                    f"--wall-clock-cap 解析失败: {argv[i + 1]!r}",
                    file=sys.stderr,
                )
                return 2
            if wall_clock_cap <= 0:
                print(
                    f"--wall-clock-cap 必须 > 0, 实际 {wall_clock_cap}",
                    file=sys.stderr,
                )
                return 2
            i += 2
            continue
        if a == "--seeds":
            j = i + 1
            new_seeds = []
            while j < len(argv) and not argv[j].startswith("--"):
                try:
                    new_seeds.append(int(argv[j]))
                except ValueError:
                    break
                j += 1
            if not new_seeds:
                print("--seeds 至少需要 1 个 seed", file=sys.stderr)
                return 2
            seeds = new_seeds
            i = j
            continue
        if a == "--output-dir":
            if i + 1 >= len(argv):
                print("--output-dir 需要参数", file=sys.stderr)
                return 2
            output_dir = argv[i + 1]
            i += 2
            continue
        if a == "--checkpoint-path":
            if i + 1 >= len(argv):
                print("--checkpoint-path 需要参数", file=sys.stderr)
                return 2
            checkpoint_path = argv[i + 1]
            i += 2
            continue
        print(f"未知参数: {a}", file=sys.stderr)
        return 2

    if show_help:
        _print_help()
        return 0

    if not (formal_search or candidate_closure or dry_run):
        _print_help()
        return 0

    # 1. Read execution HEAD
    head_proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True, text=True, encoding="utf-8",
        timeout=10,
    )
    if head_proc.returncode != 0:
        print(f"git rev-parse HEAD failed: {head_proc.stderr}",
              file=sys.stderr)
        return 2
    execution_head_sha = head_proc.stdout.strip()
    if not execution_head_sha or len(execution_head_sha) != 40:
        print(f"unexpected HEAD SHA: {execution_head_sha!r}",
              file=sys.stderr)
        return 2

    # 2. Read contract snapshot SHA (closure uses v4; formal-search uses v3)
    if candidate_closure:
        snapshot_path = "work/task_contracts/TASK_006-P2C-v4.json"
    else:
        snapshot_path = "work/task_contracts/TASK_006-P2-v3.json"
    if not os.path.exists(snapshot_path):
        print(f"contract snapshot missing: {snapshot_path}",
              file=sys.stderr)
        return 2
    with open(snapshot_path, "rb") as f:
        contract_snapshot_sha256 = hashlib.sha256(f.read()).hexdigest()

    # 3. Run
    if candidate_closure:
        # Build incumbent payload from the locked P2 result
        # (Stage E high-resolution verification rank 1)
        incumbent_payload = dict(
            heading_rad=3.127613485137657,
            speed_mps=116.62799297398149,
            release_time_1_s=0.993241052387636,
            delay_1_s=3.720360704323356,
            release_time_2_s=4.88566490244013,
            delay_2_s=3.7704749980723404,
            release_time_3_s=10.157737577136487,
            delay_3_s=3.7180978311642083,
            _reference_duration_s=4.469013137817385,
        )
        summary = run_candidate_closure(
            incumbent_payload=incumbent_payload,
            execution_head_sha=execution_head_sha,
            contract_snapshot_sha256=contract_snapshot_sha256,
            output_dir=output_dir,
            checkpoint_path=checkpoint_path,
            wall_clock_cap=wall_clock_cap,
            fake_dry_run=dry_run,
        )
    else:
        summary = run_formal_search(
            execution_head_sha=execution_head_sha,
            contract_snapshot_sha256=contract_snapshot_sha256,
            output_dir=output_dir,
            checkpoint_path=checkpoint_path,
            seeds=tuple(seeds),
            wall_clock_cap=wall_clock_cap,
            fake_dry_run=dry_run,
        )

    if summary["status"]["run_system_error"]:
        return 1
    if (summary["status"]["resume_identity_mismatch"]
            or summary["status"]["checkpoint_load_error"]):
        return 2
    if (summary["status"]["evaluation_budget_exhausted"]
            or summary["status"]["wall_clock_gate_hit"]):
        return 1
    if summary["status"]["pilot_complete"]:
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
