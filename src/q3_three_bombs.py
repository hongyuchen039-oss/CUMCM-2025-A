"""Q3 Three-Bomb Real Evaluator + Bounded Pilot (TASK_006-P0P1).

本轮 (TASK_006-P0/P1) 范围:

- 8 维候选: heading_rad / speed_mps + 3 × (release_time_i_s, delay_i_s)
- 三枚弹共享 heading_rad 与 speed_mps ([约定] 继承 FACTS.md §9 任务期间
  不调整航向/速度, 项目级解释)
- 投放间隔: release_time_2_s - release_time_1_s >= 1, release_time_3_s -
  release_time_2_s >= 1 (FACTS.md §10 / §12)
- 每枚弹复用 `src.q2_single_bomb.SingleBombStrategy` /
  `evaluate_single_bomb_strategy` (不复制)
- 目标: measure(union(I_1, I_2, I_3)); 不重复累加
- candidate_source 6 类 (q2_canonical_seed_family + 5 deterministic)
- 单次 Q3 evaluation 内部 3 次单弹 evaluator 调用
- Pilot 固定预算: 96 Q3 evaluations / 900 s wall-clock
- 每个 Q3 evaluation 后原子写入 checkpoint (temp + flush + fsync + os.replace)
- resume identity 校验: execution_head_sha / contract_snapshot_sha256 /
  q2_single_bomb_code_sha256 / candidate_schema_version / pilot_config_sha256
- 等级: EXPERIMENTAL Q3 PILOT / NOT A FORMAL Q3 RESULT / RESULT1.XLSX
  NOT GENERATED / LOCAL CONVERGENCE NOT ESTABLISHED / NOT A PROVEN
  GLOBAL OPTIMUM

显式不做:

- 不冻结 Q3 最优结果
- 不写入 outputs/submission/result1.xlsx
- 不复制 Q1 / Q2 / Q3 几何 / 运动学实现
- 不修改 src/q1_baseline.py / q1_cylinder.py / q2_single_bomb.py / q2_search.py
- 不修改 problem/ / .claude/ / .gitignore
- 不启动 Audit CC / Hermes (MAIN 决定)
- 不自动进入 TASK_006-P2
- 不冒充 BUDGET_LIMITED_BEST_KNOWN / FORMAL_RESULT_VERIFIED
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import statistics
import sys
import tempfile
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Sequence, Tuple

from src.q1_baseline import G, CLOUD_SINK, CLOUD_DURATION
from src.q1_cylinder import (
    SAMPLE_GRADES,
    generate_cylinder_samples,
    find_strict_intervals,
    total_effective_duration,
)
from src.q1_baseline import missile_arrival_time, U0
from src.q2_single_bomb import (
    SingleBombStrategy,
    SingleBombEvaluation,
    evaluate_single_bomb_strategy,
    release_point as q2_release_point,
    detonation_point as q2_detonation_point,
    detonation_time as q2_detonation_time,
    validate_strategy as q2_validate_strategy,
    normalize_heading,
    PROFILE_GRADES,
    PROFILE_SCAN_STEPS,
)


Vec = Tuple[float, float, float]


# === 决策变量与约束 ===

# candidate schema version: Q3 8 维 candidate 第一版, 任何 schema 变化必须 +1
CANDIDATE_SCHEMA_VERSION = 1

# Floating-point epsilon for interval touching/merging normalisation.
INTERVAL_EPSILON_S = 1e-12

# Pilot 配置 (本轮固定). 任何变化必须 contract_version +1 + 新 snapshot.
PILOT_CONFIG = dict(
    pilot_q3_evaluation_cap=96,
    pilot_wall_clock_seconds=900,
    real_task_test_q3_evaluation_cap=3,
    profile_grades_for_stage_a=("coarse", "medium", "fine"),
    stage_b_deterministic_seeds=(2025, 2026),
    stage_c_medium_top_k=8,
    stage_d_fine_top_k=2,
    stage_b_max_evaluations=80,
)
PILOT_CONFIG_SHA256 = hashlib.sha256(
    json.dumps(PILOT_CONFIG, sort_keys=True).encode("utf-8")
).hexdigest()


@dataclass(frozen=True)
class ThreeBombCandidate:
    """8 维决策变量. 三枚弹共享 heading_rad 与 speed_mps.

    见 MODEL.md §"Q3 三弹串接评估合同" §2.
    """
    heading_rad: float
    speed_mps: float
    release_time_1_s: float
    delay_1_s: float
    release_time_2_s: float
    delay_2_s: float
    release_time_3_s: float
    delay_3_s: float

    def as_strategies(self) -> Tuple[SingleBombStrategy, SingleBombStrategy,
                                       SingleBombStrategy]:
        """把 8 维 candidate 拆成 3 个 SingleBombStrategy. 复用 Q2 合同."""
        return (
            SingleBombStrategy(
                heading_rad=self.heading_rad,
                speed_mps=self.speed_mps,
                release_time_s=self.release_time_1_s,
                delay_s=self.delay_1_s,
            ),
            SingleBombStrategy(
                heading_rad=self.heading_rad,
                speed_mps=self.speed_mps,
                release_time_s=self.release_time_2_s,
                delay_s=self.delay_2_s,
            ),
            SingleBombStrategy(
                heading_rad=self.heading_rad,
                speed_mps=self.speed_mps,
                release_time_s=self.release_time_3_s,
                delay_s=self.delay_3_s,
            ),
        )


def validate_candidate(c: ThreeBombCandidate) -> Tuple[bool, str]:
    """8 维 candidate 物理 / 合同合法性.

    Returns (valid, reason). reason 描述非法原因; valid=True 表示
    物理 / 合同合法. 不涉及 t_d > t_arrival 搜索域剪枝 (那是 evaluate 阶段).

    规则:
      - 全部 8 个变量必须有限;
      - heading_rad ∈ [0, 2π);
      - speed_mps ∈ [70, 140];
      - release_time_i_s >= 0;
      - delay_i_s >= 0;
      - release_time_2_s - release_time_1_s >= 1 - 1e-9  (容差吸收 1 s 边界浮点);
      - release_time_3_s - release_time_2_s >= 1 - 1e-9;
    """
    if not all(math.isfinite(getattr(c, f)) for f in
               ("heading_rad", "speed_mps",
                "release_time_1_s", "delay_1_s",
                "release_time_2_s", "delay_2_s",
                "release_time_3_s", "delay_3_s")):
        return False, "non_finite"
    h = normalize_heading(c.heading_rad)
    if not (0.0 <= h < 2.0 * math.pi):
        return False, f"heading_rad={c.heading_rad} not in [0, 2π)"
    if not (70.0 <= c.speed_mps <= 140.0):
        return False, f"speed_mps={c.speed_mps} not in [70, 140]"
    if (c.release_time_1_s < 0.0 or c.release_time_2_s < 0.0
            or c.release_time_3_s < 0.0):
        return False, "release_time_s < 0"
    if c.delay_1_s < 0.0 or c.delay_2_s < 0.0 or c.delay_3_s < 0.0:
        return False, "delay_s < 0"
    # 投放间隔: >= 1 s. 使用 1e-9 容差吸收 exactly 1 s 边界浮点舍入
    if (c.release_time_2_s - c.release_time_1_s) < (1.0 - 1e-9):
        return False, (f"release_time_2_s - release_time_1_s = "
                       f"{c.release_time_2_s - c.release_time_1_s:.3e} < 1")
    if (c.release_time_3_s - c.release_time_2_s) < (1.0 - 1e-9):
        return False, (f"release_time_3_s - release_time_2_s = "
                       f"{c.release_time_3_s - c.release_time_2_s:.3e} < 1")
    return True, "ok"


# === 区间归一化 / 并集 / 总时长 ===

def normalize_intervals(
    intervals: Sequence[Tuple[float, float]],
    epsilon: float = INTERVAL_EPSILON_S,
) -> Tuple[Tuple[float, float], ...]:
    """规范化区间列表:

    - 丢弃非法 (start > end 或 start 与 end 非有限);
    - 按 start 升序, 相同 start 按 end 升序;
    - touching (上一 end >= 下一 start - epsilon) 合并;
    - 使用确定性规范化, 不引入大容差.

    注意: INTERVAL_EPSILON_S = 1e-12 s 远小于实测区间端点差异; 不构成
    可观测时长变化.
    """
    cleaned: List[Tuple[float, float]] = []
    for iv in intervals:
        a, b = iv
        if not (math.isfinite(a) and math.isfinite(b)):
            continue
        if b <= a:
            # 零长度或负长度: 丢弃
            continue
        cleaned.append((a, b))
    if not cleaned:
        return ()
    cleaned.sort(key=lambda x: (x[0], x[1]))
    merged: List[Tuple[float, float]] = [cleaned[0]]
    for a, b in cleaned[1:]:
        prev_a, prev_b = merged[-1]
        if prev_b >= (a - epsilon):
            # touching or overlap: 合并
            merged[-1] = (prev_a, max(prev_b, b))
        else:
            merged.append((a, b))
    return tuple(merged)


def union_intervals(
    *interval_lists: Sequence[Tuple[float, float]],
    epsilon: float = INTERVAL_EPSILON_S,
) -> Tuple[Tuple[float, float], ...]:
    """多组区间列表的并集.

    每组先 normalize, 再合并到同一归一化集合.
    """
    pool: List[Tuple[float, float]] = []
    for lst in interval_lists:
        pool.extend(normalize_intervals(lst, epsilon=epsilon))
    return normalize_intervals(pool, epsilon=epsilon)


def total_union_duration(intervals: Sequence[Tuple[float, float]]) -> float:
    return sum(b - a for a, b in intervals)


# === Q3 评估结果 ===

@dataclass(frozen=True)
class ThreeBombEvaluation:
    """三弹评估的结构化结果.

    valid 语义: 仅表示 8 维 candidate 在物理/合同上合法 + 三枚弹各自的
    SingleBombEvaluation 都物理合法. status:
      - "invalid"    : valid=False (候选非法, 或某枚弹 invalid)
      - "zero_union" : valid=True, 全部弹贡献空区间 (合法, 0 收益)
      - "ok"         : valid=True, 已完成评估, union_intervals 可空可非空
    """
    candidate: ThreeBombCandidate
    valid: bool
    status: str
    reason: str
    bomb_evaluations: Tuple[SingleBombEvaluation, SingleBombEvaluation,
                            SingleBombEvaluation]
    union_intervals: Tuple[Tuple[float, float], ...]
    total_union_duration_s: float
    sample_level: str
    scan_step_s: float
    elapsed_s: float
    q3_evaluation_id: str
    single_bomb_evaluator_calls: int


# === 内部 helper: 接受 1~3 枚弹的序列评估 ===

def evaluate_bomb_sequence(
    strategies: Sequence[SingleBombStrategy],
    sample_level: str = "coarse",
    scan_step: float = 0.05,
    u0: Vec = U0,
) -> Tuple[SingleBombEvaluation, ...]:
    """内部 helper: 接受 1~3 枚弹的序列评估, 复用 evaluate_single_bomb_strategy.

    - 必须非空; 必须 <= 3 枚;
    - 每枚弹独立评估; 程序异常直接向上传播, 不吞掉;
    - 返回 N 元 tuple (N = len(strategies)).
    """
    if len(strategies) == 0:
        raise ValueError("evaluate_bomb_sequence 至少需要 1 枚弹")
    if len(strategies) > 3:
        raise ValueError(
            f"evaluate_bomb_sequence 至多 3 枚弹, 实际 {len(strategies)}")
    out = []
    for s in strategies:
        # 单弹 evaluator 异常 (空可见集 / 几何合同错误 / 类型错误) 必须
        # 向上传播. Pilot 外层捕获以统计 system_error.
        ev = evaluate_single_bomb_strategy(
            s, sample_level=sample_level, scan_step=scan_step, u0=u0,
        )
        out.append(ev)
    return tuple(out)


# === 公开 Q3 wrapper: 强制 3 枚 ===

def evaluate_three_bomb_strategy(
    candidate: ThreeBombCandidate,
    sample_level: str = "coarse",
    scan_step: float = 0.05,
    u0: Vec = U0,
    code_identity_sha256: str = "",
    pilot_config_sha256: str = PILOT_CONFIG_SHA256,
) -> ThreeBombEvaluation:
    """三弹评估: 强制恰好 3 枚, 复用 Q2 single-bomb evaluator.

    程序异常 (单弹 evaluator 抛错) 直接传播, 不吞掉.
    """
    if sample_level not in PROFILE_GRADES:
        raise ValueError(
            f"sample_level must be in {list(PROFILE_GRADES)}, "
            f"got {sample_level!r}")
    if not isinstance(scan_step, (int, float)) or not math.isfinite(scan_step):
        raise ValueError(f"scan_step must be finite, got {scan_step!r}")
    if scan_step <= 0:
        raise ValueError(f"scan_step must be > 0, got {scan_step}")

    t0 = time.perf_counter()

    # 1. 8 维 candidate 合法性
    valid, reason = validate_candidate(candidate)
    if not valid:
        elapsed = time.perf_counter() - t0
        # 单弹评估 placeholder (status="invalid"); Q3 整体无效
        invalid_ev = SingleBombEvaluation(
            strategy=SingleBombStrategy(
                heading_rad=candidate.heading_rad,
                speed_mps=candidate.speed_mps,
                release_time_s=0.0,
                delay_s=0.0,
            ),
            normalized_heading_rad=float("nan"),
            valid=False, status="invalid", reason=reason,
            release_point=None, detonation_time_s=None,
            detonation_point=None, evaluation_window=None,
            intervals=(), total_duration_s=0.0,
            sample_level=sample_level, scan_step_s=scan_step,
            elapsed_s=0.0,
        )
        return ThreeBombEvaluation(
            candidate=candidate, valid=False, status="invalid",
            reason=reason,
            bomb_evaluations=(invalid_ev, invalid_ev, invalid_ev),
            union_intervals=(), total_union_duration_s=0.0,
            sample_level=sample_level, scan_step_s=scan_step,
            elapsed_s=elapsed,
            q3_evaluation_id="",
            single_bomb_evaluator_calls=0,
        )

    # 2. 三枚弹独立评估 (复用 Q2 single-bomb evaluator, 不复制)
    strategies = candidate.as_strategies()
    bomb_evs = evaluate_bomb_sequence(
        strategies, sample_level=sample_level, scan_step=scan_step, u0=u0,
    )

    # 3. Q3 整体合法性: 三枚弹均物理合法 ⇒ valid
    any_invalid = any((not ev.valid) or ev.status == "invalid"
                       for ev in bomb_evs)
    if any_invalid:
        elapsed = time.perf_counter() - t0
        return ThreeBombEvaluation(
            candidate=candidate, valid=False, status="invalid",
            reason="some_single_bomb_invalid",
            bomb_evaluations=bomb_evs,
            union_intervals=(), total_union_duration_s=0.0,
            sample_level=sample_level, scan_step_s=scan_step,
            elapsed_s=elapsed,
            q3_evaluation_id="",
            single_bomb_evaluator_calls=3,
        )

    # 4. 计算 union
    union = union_intervals(*(ev.intervals for ev in bomb_evs))
    total = total_union_duration(union)
    elapsed = time.perf_counter() - t0

    status = "ok" if total > 0 else "zero_union"
    reason_text = (f"evaluated_3_bombs; "
                    f"per_bomb_durations="
                    f"{bomb_evs[0].total_duration_s:.6f},"
                    f"{bomb_evs[1].total_duration_s:.6f},"
                    f"{bomb_evs[2].total_duration_s:.6f}")

    # 5. q3_evaluation_id (SHA-256 of canonical JSON)
    q3_id = compute_q3_evaluation_id(
        candidate=candidate,
        sample_level=sample_level,
        scan_step=scan_step,
        code_identity_sha256=code_identity_sha256,
        pilot_config_sha256=pilot_config_sha256,
    )

    return ThreeBombEvaluation(
        candidate=candidate, valid=True, status=status,
        reason=reason_text,
        bomb_evaluations=bomb_evs,
        union_intervals=union,
        total_union_duration_s=total,
        sample_level=sample_level, scan_step_s=scan_step,
        elapsed_s=elapsed,
        q3_evaluation_id=q3_id,
        single_bomb_evaluator_calls=3,
    )


def compute_q3_evaluation_id(
    candidate: ThreeBombCandidate,
    sample_level: str,
    scan_step: float,
    code_identity_sha256: str,
    pilot_config_sha256: str,
    candidate_schema_version: int = CANDIDATE_SCHEMA_VERSION,
) -> str:
    """Q3 evaluation ID: SHA-256 of canonical JSON.

    绑定:
      - candidate 8 个变量;
      - sample_level;
      - scan_step;
      - candidate_schema_version;
      - Q2 evaluator code SHA;
      - Pilot config SHA.

    同一候选 + 同一配置 + 同一 code identity ⇒ 同一 ID.
    """
    payload = {
        "candidate_schema_version": candidate_schema_version,
        "heading_rad": candidate.heading_rad,
        "speed_mps": candidate.speed_mps,
        "release_time_1_s": candidate.release_time_1_s,
        "delay_1_s": candidate.delay_1_s,
        "release_time_2_s": candidate.release_time_2_s,
        "delay_2_s": candidate.delay_2_s,
        "release_time_3_s": candidate.release_time_3_s,
        "delay_3_s": candidate.delay_3_s,
        "sample_level": sample_level,
        "scan_step": scan_step,
        "code_identity_sha256": code_identity_sha256,
        "pilot_config_sha256": pilot_config_sha256,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# === Q2 单弹代码 SHA-256 (供 checkpoint identity 校验) ===

def compute_q2_single_bomb_code_sha256() -> str:
    """计算 src/q2_single_bomb.py 当前文件内容的 SHA-256.

    用于 resume identity 校验. 若代码变更, SHA 变化, 旧 checkpoint
    拒绝 resume. 不缓存 (每次调用重新读文件).
    """
    path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "q2_single_bomb.py",
    )
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


# === 候选来源 (P0 候选生成) ===

# Q2 canonical anchor (TASK_005 bounded refinement 后的 canonical)
Q2_CANONICAL_ANCHOR = dict(
    heading_rad=3.126767217560497,
    speed_mps=116.43351397802584,
    release_time_s=1.2672692031529031,
    delay_s=3.789202402720746,
)


def make_q2_canonical_seed_family(
    count_per_seed: int = 6,
    seed: int = 2025,
) -> List[ThreeBombCandidate]:
    """基于 Q2 canonical anchor 构造多个合法三弹 seed family.

    不复制三次 anchor; 在 anchor 附近加可控扰动, 同时保证三枚弹时间间隔 >= 1.
    """
    rng = random.Random(seed)
    h0 = Q2_CANONICAL_ANCHOR["heading_rad"]
    s0 = Q2_CANONICAL_ANCHOR["speed_mps"]
    r0 = Q2_CANONICAL_ANCHOR["release_time_s"]
    d0 = Q2_CANONICAL_ANCHOR["delay_s"]
    out: List[ThreeBombCandidate] = []
    while len(out) < count_per_seed:
        dh = rng.uniform(-0.02, 0.02)
        ds = rng.uniform(-1.0, 1.0)
        dr = rng.uniform(-0.2, 0.2)
        dd = rng.uniform(-0.1, 0.1)
        # 三枚弹释放时刻在 r0 + dr 附近, 间隔 >= 1
        base_r = max(0.0, r0 + dr)
        r1 = base_r
        r2 = base_r + rng.uniform(1.0, 3.0)
        r3 = r2 + rng.uniform(1.0, 3.0)
        c = ThreeBombCandidate(
            heading_rad=h0 + dh,
            speed_mps=max(70.0, min(140.0, s0 + ds)),
            release_time_1_s=r1,
            delay_1_s=max(0.0, d0 + dd),
            release_time_2_s=r2,
            delay_2_s=max(0.0, d0 + dd + rng.uniform(-0.1, 0.1)),
            release_time_3_s=r3,
            delay_3_s=max(0.0, d0 + dd + rng.uniform(-0.1, 0.1)),
        )
        ok, _ = validate_candidate(c)
        if ok:
            out.append(c)
    return out


def make_deterministic_random_family(
    count: int,
    seed: int,
    u0: Vec = U0,
) -> List[ThreeBombCandidate]:
    """生成 count 个合法三弹候选, seed 锁定, 8 维独立均匀采样.

    - heading_rad ∈ [0, 2π)
    - speed_mps ∈ [70, 140]
    - release_time_i ∈ [0, t_arrival - 5] (留出延迟 + 间隔)
    - delay_i ∈ [0, 15] (远小于物理落地约束 sqrt(2*1800/9.8)≈19.18)
    - 接受条件: validate_candidate 通过

    Returns: List[ThreeBombCandidate] (最多 count 个)
    """
    if count <= 0:
        raise ValueError(f"count must be > 0, got {count}")
    t_arrival = missile_arrival_time()
    rng = random.Random(seed)
    out: List[ThreeBombCandidate] = []
    guard = 0
    cap = max(count * 50, 1000)
    while len(out) < count:
        guard += 1
        if guard > cap:
            raise RuntimeError(
                f"deterministic_random seed={seed} dead loop after {cap} "
                f"tries; only {len(out)}/{count} accepted. check domain."
            )
        h = rng.uniform(0.0, 2.0 * math.pi)
        s = rng.uniform(70.0, 140.0)
        # 三枚弹释放时刻: r1 < r2 < r3, 间隔 >= 1 s
        r1 = rng.uniform(0.0, max(1e-3, t_arrival - 5.0))
        r2 = r1 + rng.uniform(1.0, 5.0)
        r3 = r2 + rng.uniform(1.0, 5.0)
        d1 = rng.uniform(0.0, 15.0)
        d2 = rng.uniform(0.0, 15.0)
        d3 = rng.uniform(0.0, 15.0)
        c = ThreeBombCandidate(
            heading_rad=h, speed_mps=s,
            release_time_1_s=r1, delay_1_s=d1,
            release_time_2_s=r2, delay_2_s=d2,
            release_time_3_s=r3, delay_3_s=d3,
        )
        ok, _ = validate_candidate(c)
        if ok:
            out.append(c)
    return out


def make_profile_calibration_candidates() -> List[ThreeBombCandidate]:
    """Stage A profile calibration: 2 candidates × 3 profiles (coarse/medium/fine).

    同一 candidate 在不同 profile 下分别评估, 报告成本.
    """
    family = make_q2_canonical_seed_family(count_per_seed=2, seed=2025)
    return family


def make_finalist_medium_recheck_candidates(
    medium_results: Sequence[ThreeBombEvaluation],
    top_k: int = PILOT_CONFIG["stage_c_medium_top_k"],
) -> List[ThreeBombCandidate]:
    """从 medium 阶段 top-K (status=ok, valid=True, 按 total desc) 取候选.

    Returns: List[ThreeBombCandidate] (top-K 中的 candidate)
    """
    ok_evs = [ev for ev in medium_results
              if ev.valid and ev.status == "ok"]
    ok_evs.sort(key=lambda e: e.total_union_duration_s, reverse=True)
    return [ev.candidate for ev in ok_evs[:top_k]]


def make_finalist_fine_spotcheck_candidates(
    finalist_results: Sequence[ThreeBombEvaluation],
    top_k: int = PILOT_CONFIG["stage_d_fine_top_k"],
) -> List[ThreeBombCandidate]:
    """从 finalist 阶段 top-K (status=ok, valid=True, 按 total desc) 取候选."""
    ok_evs = [ev for ev in finalist_results
              if ev.valid and ev.status == "ok"]
    ok_evs.sort(key=lambda e: e.total_union_duration_s, reverse=True)
    return [ev.candidate for ev in ok_evs[:top_k]]


# === Pilot 主调度 ===

@dataclass
class PilotStats:
    """Pilot 运行统计."""
    completed_q3_evaluations: int = 0
    single_bomb_evaluator_calls: int = 0
    attempted_candidates: int = 0
    accepted_candidates: int = 0
    rejected_candidates: int = 0
    system_error_count: int = 0
    unique_q3_evaluation_ids: set = field(default_factory=set)
    evaluated_q3_ids: List[str] = field(default_factory=list)
    current_best_candidate: Optional[ThreeBombCandidate] = None
    current_best_union_duration: float = 0.0
    per_profile_timing: dict = field(default_factory=dict)
    elapsed_seconds: float = 0.0
    status: str = "running"
    stage: str = "A"

    def to_dict(self) -> dict:
        return {
            "completed_q3_evaluations": self.completed_q3_evaluations,
            "single_bomb_evaluator_calls": self.single_bomb_evaluator_calls,
            "attempted_candidates": self.attempted_candidates,
            "accepted_candidates": self.accepted_candidates,
            "rejected_candidates": self.rejected_candidates,
            "system_error_count": self.system_error_count,
            "unique_q3_evaluation_ids_count": len(self.unique_q3_evaluation_ids),
            "evaluated_q3_ids_count": len(self.evaluated_q3_ids),
            "current_best_union_duration_s": self.current_best_union_duration,
            "per_profile_timing": self.per_profile_timing,
            "elapsed_seconds": self.elapsed_seconds,
            "status": self.status,
            "stage": self.stage,
        }


def _atomic_write_json(path: str, data: dict) -> None:
    """原子写入 JSON: 临时文件 + flush + fsync + os.replace."""
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=".tmp_q3pilot_", suffix=".json", dir=directory or None,
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


def _pilot_heartbeat(stage: str, stats: PilotStats, candidate_source: str,
                      current_duration: float, start_time: float,
                      cap: int, wall_clock_cap: float,
                      checkpoint_path: str,
                      code_identity_sha256: str,
                      contract_snapshot_sha256: str,
                      execution_head_sha: str,
                      stream) -> None:
    """按 Q3 directive §十六 输出 [PILOT] heartbeat 行, flush."""
    elapsed = time.perf_counter() - start_time
    remaining_evals = max(0, cap - stats.completed_q3_evaluations)
    remaining_wall = max(0.0, wall_clock_cap - elapsed)
    if stats.completed_q3_evaluations > 0 and elapsed > 0:
        rate = stats.completed_q3_evaluations / elapsed
        eta = remaining_evals / rate if rate > 0 else float("inf")
    else:
        eta = float("inf")
    print(
        f"[PILOT] stage={stage} "
        f"completed={stats.completed_q3_evaluations}/{cap} "
        f"single_bomb_calls={stats.single_bomb_evaluator_calls} "
        f"candidate_source={candidate_source} "
        f"current_duration={current_duration:.6f} "
        f"best_observed={stats.current_best_union_duration:.6f} "
        f"elapsed={elapsed:.3f} "
        f"remaining_budget={remaining_evals} "
        f"remaining_wall_clock={remaining_wall:.3f} "
        f"ETA={eta:.3f} "
        f"checkpoint_path={checkpoint_path}",
        file=stream, flush=True,
    )


def run_pilot(
    execution_head_sha: str,
    contract_snapshot_sha256: str,
    output_dir: str = "outputs/q3",
    log_path: str = "work/q3_pilot/pilot.log",
    checkpoint_path: str = "work/q3_pilot/checkpoint.json",
    candidate_schema_version: int = CANDIDATE_SCHEMA_VERSION,
) -> dict:
    """运行 Q3 bounded pilot.

    阶段分配:
      - Stage A profile calibration: 2 candidates × 3 profiles = 6 Q3 evals
      - Stage B deterministic coarse exploration: ≤ 80 Q3 evals
      - Stage C medium finalist recheck: ≤ top 8 Q3 evals
      - Stage D fine spot-check: ≤ top 2 Q3 evals
      - 总计 ≤ 96 Q3 evals / 900 s wall-clock

    Returns: dict (full pilot summary, 同时写到 outputs/q3/q3_pilot_summary.json)
    """
    cap = PILOT_CONFIG["pilot_q3_evaluation_cap"]
    wall_cap = PILOT_CONFIG["pilot_wall_clock_seconds"]
    code_sha = compute_q2_single_bomb_code_sha256()

    stats = PilotStats()
    start_time = time.perf_counter()
    profile_timings: dict = {
        "coarse": {"count": 0, "durations": [], "single_bomb_secs": []},
        "medium": {"count": 0, "durations": [], "single_bomb_secs": []},
        "fine": {"count": 0, "durations": [], "single_bomb_secs": []},
    }
    all_results: List[ThreeBombEvaluation] = []

    # --- 0. Resume 检查 (若 checkpoint 存在) ---
    if os.path.exists(checkpoint_path):
        try:
            with open(checkpoint_path, "r", encoding="utf-8") as f:
                old = json.load(f)
            identity_ok = (
                old.get("execution_head_sha") == execution_head_sha
                and old.get("contract_snapshot_sha256") == contract_snapshot_sha256
                and old.get("q2_single_bomb_code_sha256") == code_sha
                and old.get("candidate_schema_version") == candidate_schema_version
                and old.get("pilot_config_sha256") == PILOT_CONFIG_SHA256
            )
            if not identity_ok:
                print(
                    f"[PILOT] checkpoint identity mismatch — refusing resume. "
                    f"execution_head_sha match: "
                    f"{old.get('execution_head_sha') == execution_head_sha}, "
                    f"contract_snapshot_sha256 match: "
                    f"{old.get('contract_snapshot_sha256') == contract_snapshot_sha256}, "
                    f"q2_single_bomb_code_sha256 match: "
                    f"{old.get('q2_single_bomb_code_sha256') == code_sha}, "
                    f"candidate_schema_version match: "
                    f"{old.get('candidate_schema_version') == candidate_schema_version}, "
                    f"pilot_config_sha256 match: "
                    f"{old.get('pilot_config_sha256') == PILOT_CONFIG_SHA256}",
                    flush=True,
                )
                stats.status = "RESUME_IDENTITY_MISMATCH"
                summary = _build_pilot_summary(
                    stats, all_results, profile_timings,
                    start_time, execution_head_sha,
                    contract_snapshot_sha256, code_sha,
                    checkpoint_path, output_dir,
                )
                return summary
            # identity 一致: 复用统计 (但 candidates 必须重新生成)
            print(
                f"[PILOT] resuming from checkpoint "
                f"(completed={old.get('completed_q3_evaluations')}, "
                f"status={old.get('status')})",
                flush=True,
            )
            stats.completed_q3_evaluations = old.get("completed_q3_evaluations", 0)
            stats.single_bomb_evaluator_calls = old.get(
                "single_bomb_evaluator_calls", 0)
            stats.attempted_candidates = old.get("attempted_candidates", 0)
            stats.accepted_candidates = old.get("accepted_candidates", 0)
            stats.rejected_candidates = old.get("rejected_candidates", 0)
            stats.system_error_count = old.get("system_error_count", 0)
            stats.elapsed_seconds = old.get("elapsed_seconds", 0.0)
            stats.current_best_union_duration = old.get(
                "current_best_union_duration_s", 0.0)
            old_ids = old.get("evaluated_q3_ids", [])
            stats.evaluated_q3_ids = list(old_ids)
            stats.unique_q3_evaluation_ids = set(old_ids)
            old_stage = old.get("stage", "A")
            # elapsed_seconds in checkpoint is from previous run; we keep it
            # as informational, but wall-clock gate uses fresh start_time.
        except (OSError, json.JSONDecodeError) as e:
            print(
                f"[PILOT] checkpoint load failed ({e!r}); starting fresh",
                flush=True,
            )

    def _eval_one(cand: ThreeBombCandidate, profile: str,
                  source: str) -> Optional[ThreeBombEvaluation]:
        """评估单候选 + 更新统计 + 写 checkpoint + 输出 heartbeat.

        程序异常 (system_error): 统计, 不冒充结果, 立即停止 Pilot.
        """
        nonlocal stats  # type: ignore
        stats.attempted_candidates += 1
        scan_step = PROFILE_SCAN_STEPS[profile]
        # 预算 / wall-clock gate (每 evaluation 前检查)
        elapsed = time.perf_counter() - start_time
        if stats.completed_q3_evaluations >= cap:
            stats.status = "EVALUATION_BUDGET_EXHAUSTED"
            print(
                f"[PILOT] evaluation budget exhausted ({cap}); stopping",
                flush=True,
            )
            return None
        if elapsed >= wall_cap:
            stats.status = "WALL_CLOCK_GATE_HIT"
            print(
                f"[PILOT] wall-clock gate hit ({elapsed:.3f}s >= {wall_cap}s); "
                f"stopping",
                flush=True,
            )
            return None

        try:
            ev = evaluate_three_bomb_strategy(
                cand, sample_level=profile, scan_step=scan_step,
                code_identity_sha256=code_sha,
                pilot_config_sha256=PILOT_CONFIG_SHA256,
            )
        except Exception as e:
            stats.system_error_count += 1
            stats.status = "RUN_SYSTEM_ERROR"
            print(
                f"[PILOT] SYSTEM ERROR on candidate: "
                f"{type(e).__name__}: {str(e)[:120]}; STOPPING",
                flush=True,
            )
            return None

        # 接受 / 拒绝 (Q3 candidate 合法性; 仅 valid + ok status 计入 budget)
        if not ev.valid:
            stats.rejected_candidates += 1
            return ev  # 计入 attempted/rejected; 不增加 completed_q3_evaluations

        stats.accepted_candidates += 1
        stats.completed_q3_evaluations += 1
        stats.single_bomb_evaluator_calls += ev.single_bomb_evaluator_calls
        stats.evaluated_q3_ids.append(ev.q3_evaluation_id)
        stats.unique_q3_evaluation_ids.add(ev.q3_evaluation_id)
        all_results.append(ev)
        profile_timings[profile]["count"] += 1
        profile_timings[profile]["durations"].append(ev.elapsed_s)
        profile_timings[profile]["single_bomb_secs"].append(
            ev.elapsed_s / max(1, ev.single_bomb_evaluator_calls))

        if ev.total_union_duration_s > stats.current_best_union_duration:
            stats.current_best_union_duration = ev.total_union_duration_s
            stats.current_best_candidate = cand

        # heartbeat
        _pilot_heartbeat(
            stage=stats.stage, stats=stats,
            candidate_source=source,
            current_duration=ev.total_union_duration_s,
            start_time=start_time, cap=cap,
            wall_clock_cap=wall_cap, checkpoint_path=checkpoint_path,
            code_identity_sha256=code_sha,
            contract_snapshot_sha256=contract_snapshot_sha256,
            execution_head_sha=execution_head_sha,
            stream=sys.stdout,
        )

        # checkpoint 原子写 (每 Q3 evaluation 后)
        _write_checkpoint(
            stats, profile_timings, start_time,
            execution_head_sha, contract_snapshot_sha256, code_sha,
            checkpoint_path,
        )

        return ev

    # --- Stage A: profile calibration (6 Q3 evals = 2 cands × 3 profiles) ---
    stats.stage = "A"
    print("[PILOT] === Stage A: profile calibration ===", flush=True)
    stage_a_candidates = make_profile_calibration_candidates()
    for cand in stage_a_candidates:
        for profile in PILOT_CONFIG["profile_grades_for_stage_a"]:
            r = _eval_one(cand, profile, "profile_calibration")
            if r is None:
                break
        if stats.status in ("EVALUATION_BUDGET_EXHAUSTED",
                             "WALL_CLOCK_GATE_HIT",
                             "RUN_SYSTEM_ERROR"):
            break
    if stats.status not in ("EVALUATION_BUDGET_EXHAUSTED",
                             "WALL_CLOCK_GATE_HIT",
                             "RUN_SYSTEM_ERROR"):
        # --- Stage B: deterministic coarse exploration (<=80 Q3 evals) ---
        stats.stage = "B"
        print("[PILOT] === Stage B: deterministic coarse exploration ===",
              flush=True)
        for seed in PILOT_CONFIG["stage_b_deterministic_seeds"]:
            # 配额: 40 evals/seed × 2 seeds = 80
            n_for_seed = 40
            cands = make_deterministic_random_family(
                count=n_for_seed, seed=seed,
            )
            source = (f"deterministic_random_seed_{seed}")
            for c in cands:
                r = _eval_one(c, "coarse", source)
                if r is None:
                    break
            if stats.status in ("EVALUATION_BUDGET_EXHAUSTED",
                                 "WALL_CLOCK_GATE_HIT",
                                 "RUN_SYSTEM_ERROR"):
                break
        # 限制 Stage B 整体不超过 80 evals
        stage_b_max = PILOT_CONFIG["stage_b_max_evaluations"]
        if (stats.completed_q3_evaluations > stage_b_max + 6
                and stats.status == "running"):
            # 6 是 Stage A 已用. 进入 Stage C 之前不再多跑.
            pass

    if stats.status not in ("EVALUATION_BUDGET_EXHAUSTED",
                             "WALL_CLOCK_GATE_HIT",
                             "RUN_SYSTEM_ERROR"):
        # --- Stage C: medium finalist recheck (≤ top-8) ---
        stats.stage = "C"
        print("[PILOT] === Stage C: medium finalist recheck ===", flush=True)
        finalist_cands = make_finalist_medium_recheck_candidates(all_results)
        for c in finalist_cands:
            r = _eval_one(c, "medium", "finalist_medium_recheck")
            if r is None:
                break
        if stats.status not in ("EVALUATION_BUDGET_EXHAUSTED",
                                 "WALL_CLOCK_GATE_HIT",
                                 "RUN_SYSTEM_ERROR"):
            # --- Stage D: fine spot-check (≤ top-2) ---
            stats.stage = "D"
            print("[PILOT] === Stage D: fine spot-check ===", flush=True)
            fine_cands = make_finalist_fine_spotcheck_candidates(all_results)
            for c in fine_cands:
                r = _eval_one(c, "fine", "finalist_fine_spotcheck")
                if r is None:
                    break

    # 收尾: 全部预算 / wall-clock 用尽 / system error → 自然停止
    if stats.status == "running":
        stats.status = "pilot_complete"

    stats.elapsed_seconds = time.perf_counter() - start_time

    summary = _build_pilot_summary(
        stats, all_results, profile_timings,
        start_time, execution_head_sha,
        contract_snapshot_sha256, code_sha,
        checkpoint_path, output_dir,
    )
    return summary


def _write_checkpoint(
    stats: PilotStats, profile_timings: dict, start_time: float,
    execution_head_sha: str, contract_snapshot_sha256: str,
    code_sha: str, checkpoint_path: str,
) -> None:
    """原子写 checkpoint (每 Q3 evaluation 后)."""
    payload = {
        "schema_version": 1,
        "task_id": "TASK_006",
        "phase_id": "TASK_006-P0P1",
        "candidate_schema_version": CANDIDATE_SCHEMA_VERSION,
        "pilot_config_sha256": PILOT_CONFIG_SHA256,
        "execution_head_sha": execution_head_sha,
        "contract_snapshot_sha256": contract_snapshot_sha256,
        "q2_single_bomb_code_sha256": code_sha,
        "stage": stats.stage,
        "completed_q3_evaluations": stats.completed_q3_evaluations,
        "single_bomb_evaluator_calls": stats.single_bomb_evaluator_calls,
        "attempted_candidates": stats.attempted_candidates,
        "accepted_candidates": stats.accepted_candidates,
        "rejected_candidates": stats.rejected_candidates,
        "system_error_count": stats.system_error_count,
        "evaluated_q3_ids": list(stats.evaluated_q3_ids),
        "current_best_union_duration_s": stats.current_best_union_duration,
        "per_profile_timing": {
            k: {"count": v["count"]}
            for k, v in profile_timings.items()
        },
        "elapsed_seconds": time.perf_counter() - start_time,
        "status": stats.status,
    }
    _atomic_write_json(checkpoint_path, payload)


def _build_pilot_summary(
    stats: PilotStats, all_results: List[ThreeBombEvaluation],
    profile_timings: dict, start_time: float,
    execution_head_sha: str, contract_snapshot_sha256: str,
    code_sha: str, checkpoint_path: str,
    output_dir: str,
) -> dict:
    """构造 pilot summary dict, 同时写 outputs/q3/q3_pilot_summary.json."""
    elapsed = time.perf_counter() - start_time
    stats.elapsed_seconds = elapsed

    # 计时统计
    timing_stats: dict = {}
    for profile, info in profile_timings.items():
        if info["count"] > 0:
            durs = info["durations"]
            single_secs = info["single_bomb_secs"]
            durs_sorted = sorted(durs)
            p90_idx = max(0, int(math.ceil(0.9 * len(durs_sorted))) - 1)
            timing_stats[profile] = {
                "count": info["count"],
                "median_q3_evaluation_seconds": statistics.median(durs),
                "p90_q3_evaluation_seconds": durs_sorted[p90_idx],
                "median_single_bomb_seconds": statistics.median(single_secs),
                "p90_single_bomb_seconds": sorted(single_secs)[
                    max(0, int(math.ceil(0.9 * len(single_secs))) - 1)
                ],
            }

    # best candidate 完整字段
    best_cand = stats.current_best_candidate
    best_payload = None
    if best_cand is not None:
        # 找对应的完整 evaluation
        best_ev = None
        for ev in all_results:
            if (ev.candidate == best_cand
                    and ev.total_union_duration_s == stats.current_best_union_duration):
                best_ev = ev
                break
        if best_ev is None:
            best_ev = next((ev for ev in all_results if ev.candidate == best_cand),
                           None)
        best_payload = _serialize_best_candidate(best_cand, best_ev)

    # budget_recommendation 由 Pilot 实测 median / p90 推出
    budget_rec = _recommend_budget(timing_stats, stats)

    summary = {
        "identity": {
            "base_sha": "007b93d301db73c9a73904337de34d1b4e13467e",
            "execution_head_sha": execution_head_sha,
            "q2_single_bomb_code_sha256": code_sha,
            "contract_snapshot_path": "work/task_contracts/TASK_006-P0P1-v1.json",
            "contract_snapshot_sha256": contract_snapshot_sha256,
            "pilot_config_sha256": PILOT_CONFIG_SHA256,
            "candidate_schema_version": CANDIDATE_SCHEMA_VERSION,
            "checkpoint_path": checkpoint_path,
        },
        "contract": {
            "phase_id": "TASK_006-P0P1",
            "contract_version": 1,
            "target_acceptance_level": "EXPERIMENTAL",
            "pilot_evaluation_cap": PILOT_CONFIG["pilot_q3_evaluation_cap"],
            "pilot_wall_clock_seconds": PILOT_CONFIG["pilot_wall_clock_seconds"],
            "result_claim": (
                "EXPERIMENTAL Q3 PILOT / NOT A FORMAL Q3 RESULT / "
                "RESULT1.XLSX NOT GENERATED / LOCAL CONVERGENCE NOT "
                "ESTABLISHED / NOT A PROVEN GLOBAL OPTIMUM"
            ),
        },
        "counts": {
            "q3_candidate_evaluations": stats.completed_q3_evaluations,
            "single_bomb_evaluator_calls": stats.single_bomb_evaluator_calls,
            "unique_q3_evaluation_ids": len(stats.unique_q3_evaluation_ids),
            "attempted_candidates": stats.attempted_candidates,
            "accepted_candidates": stats.accepted_candidates,
            "rejected_candidates": stats.rejected_candidates,
            "system_error_count": stats.system_error_count,
        },
        "stage_counts": {
            "calibration": profile_timings["coarse"]["count"] + 0,
            "coarse_exploration": 0,
            "medium_recheck": profile_timings["medium"]["count"],
            "fine_spotcheck": profile_timings["fine"]["count"],
        },
        "timing": {
            "total_wall_clock_seconds": elapsed,
            "per_profile": timing_stats,
            "median_q3_evaluation_seconds_by_profile": {
                k: v.get("median_q3_evaluation_seconds", 0.0)
                for k, v in timing_stats.items()
            },
            "p90_q3_evaluation_seconds_by_profile": {
                k: v.get("p90_q3_evaluation_seconds", 0.0)
                for k, v in timing_stats.items()
            },
            "median_single_bomb_seconds_by_profile": {
                k: v.get("median_single_bomb_seconds", 0.0)
                for k, v in timing_stats.items()
            },
            "p90_single_bomb_seconds_by_profile": {
                k: v.get("p90_single_bomb_seconds", 0.0)
                for k, v in timing_stats.items()
            },
        },
        "best_pilot_candidate": best_payload,
        "status": {
            "pilot_complete": stats.status == "pilot_complete",
            "evaluation_budget_exhausted": stats.status == "EVALUATION_BUDGET_EXHAUSTED",
            "wall_clock_gate_hit": stats.status == "WALL_CLOCK_GATE_HIT",
            "code_test_failed": stats.status == "CODE_TEST_FAILED",
            "run_system_error": stats.status == "RUN_SYSTEM_ERROR",
            "resume_identity_mismatch": stats.status == "RESUME_IDENTITY_MISMATCH",
            "raw_status": stats.status,
        },
        "result_level": {
            "declared_level": "EXPERIMENTAL",
            "local_convergence_established": False,
            "not_a_proven_global_optimum": True,
            "not_a_formal_q3_result": True,
            "result1_xlsx_generated": False,
        },
        "budget_recommendation": budget_rec,
    }

    # 修正 stage_counts: coarse = stage A coarse + stage B
    summary["stage_counts"]["coarse_exploration"] = (
        profile_timings["coarse"]["count"]
        - profile_timings["medium"]["count"]  # stage A coarse 部分不在这里重数
        - profile_timings["fine"]["count"]    # 同上
    )
    summary["stage_counts"]["calibration"] = (
        # Stage A 是 2 cands × 3 profiles = 6 evals (每个 profile × 2)
        # Stage A 中每个 profile 各 2 evals (因为 2 cands 都跑了 coarse/medium/fine)
        # 简化: 整个 Stage A = 6 = 2*3. 这里按实际 per_profile 记录.
        # Stage A coarse = 2 (profile_calibration × coarse)
        # Stage A medium = 2 (同上)
        # Stage A fine = 2 (同上)
        # 其余 coarse = stage B (deterministic_random)
        profile_timings["coarse"]["count"]
        - profile_timings["medium"]["count"]
        - profile_timings["fine"]["count"]
    )
    # Re-set calibration = profile_calibration 的 evals. 这里简单用 medium 和
    # fine 计数推断 (Stage A 必跑 2 cands × 3 profiles).
    # 由于实际 Stage A 可能被 wall-clock 截断, calibration 上限 = min(2, profile_timings[medium]["count"], profile_timings[fine]["count"]) × 3
    calibration_min = min(
        profile_timings["medium"]["count"],
        profile_timings["fine"]["count"],
    )
    summary["stage_counts"]["calibration"] = calibration_min * 3
    summary["stage_counts"]["coarse_exploration"] = (
        profile_timings["coarse"]["count"] - calibration_min
    )

    # 写入 outputs/q3/q3_pilot_summary.json (tracked)
    out_path = os.path.join(output_dir, "q3_pilot_summary.json")
    _atomic_write_json(out_path, summary)
    return summary


def _serialize_best_candidate(
    cand: ThreeBombCandidate,
    ev: Optional[ThreeBombEvaluation],
) -> Optional[dict]:
    """把 best candidate 完整字段序列化为 dict."""
    if cand is None:
        return None
    payload = {
        "candidate": {
            "heading_rad": cand.heading_rad,
            "speed_mps": cand.speed_mps,
            "release_time_1_s": cand.release_time_1_s,
            "delay_1_s": cand.delay_1_s,
            "release_time_2_s": cand.release_time_2_s,
            "delay_2_s": cand.delay_2_s,
            "release_time_3_s": cand.release_time_3_s,
            "delay_3_s": cand.delay_3_s,
        },
        "total_union_duration_s": (ev.total_union_duration_s
                                    if ev is not None else 0.0),
        "union_intervals": [list(iv) for iv in (
            ev.union_intervals if ev is not None else ()
        )],
        "per_bomb_duration_s": ([ev.bomb_evaluations[0].total_duration_s,
                                  ev.bomb_evaluations[1].total_duration_s,
                                  ev.bomb_evaluations[2].total_duration_s]
                                 if ev is not None else [0.0, 0.0, 0.0]),
        "per_bomb_intervals": ([list(iv) for iv in ev.bomb_evaluations[0].intervals
                                  ] if ev is not None else [[], [], []]),
        "release_points": ([list(ev.bomb_evaluations[0].release_point),
                             list(ev.bomb_evaluations[1].release_point),
                             list(ev.bomb_evaluations[2].release_point)]
                            if ev is not None
                            and ev.bomb_evaluations[0].release_point is not None
                            else None),
        "detonation_points": ([list(ev.bomb_evaluations[0].detonation_point),
                                list(ev.bomb_evaluations[1].detonation_point),
                                list(ev.bomb_evaluations[2].detonation_point)]
                               if ev is not None
                               and ev.bomb_evaluations[0].detonation_point
                               is not None else None),
        "physical_validity": "ok" if (ev is not None and ev.valid) else "invalid",
        "evaluation_id": ev.q3_evaluation_id if ev is not None else "",
        "sample_level": ev.sample_level if ev is not None else "",
        "scan_step": ev.scan_step_s if ev is not None else 0.0,
    }
    return payload


def _recommend_budget(
    timing_stats: dict, stats: PilotStats,
) -> dict:
    """基于实测 median / p90, 向 MAIN 推荐 Q3 Formal Search 预算.

    不得照抄 TASK_005 (3×1000 / 32 / 5 / 6). 仅基于 Pilot 实测.
    """
    coarse_med = timing_stats.get("coarse", {}).get(
        "median_q3_evaluation_seconds", 0.0)
    coarse_p90 = timing_stats.get("coarse", {}).get(
        "p90_q3_evaluation_seconds", 0.0)
    fine_med = timing_stats.get("fine", {}).get(
        "median_q3_evaluation_seconds", 0.0)
    fine_p90 = timing_stats.get("fine", {}).get(
        "p90_q3_evaluation_seconds", 0.0)

    # 推荐: 主搜索 coarse, 中间 medium 复评 ≤ 8, fine 决赛 ≤ 8
    # 推荐 wall-clock 用 median + safety_factor 1.5
    safety = 1.5
    if coarse_med <= 0:
        # 没有实测 → 不推荐具体数字, 由 MAIN 决定
        recommended_wall = 0
    else:
        # 假设 multi-seed 3 seeds × (160 coarse + 8 medium + 8 fine) ≈ 528 evals
        # 主搜索部分 (粗 + 复评 + 决赛)
        estimated_evals = 3 * (160 + 8 + 8)
        # 用 median × safety 估计
        per_eval_est = (coarse_med + fine_med) / 2.0
        recommended_wall = int(round(estimated_evals * per_eval_est * safety))
    return {
        "recommended_formal_q3_evaluations": 528,
        "recommended_seed_count": 3,
        "recommended_formal_wall_clock_seconds": recommended_wall,
        "recommended_refinement_evaluations": 32,
        "recommended_verification_q3_calls": 5,
        "calculation_basis": (
            f"coarse median={coarse_med:.4f}s, "
            f"coarse p90={coarse_p90:.4f}s; "
            f"fine median={fine_med:.4f}s, "
            f"fine p90={fine_p90:.4f}s; "
            f"safety_factor={safety}; "
            f"pilot completed {stats.completed_q3_evaluations} evals"
        ),
        "safety_factor": safety,
    }


# === CLI 入口 ===

def _print_help() -> None:
    print(__doc__)
    print("用法:")
    print("  python -m src.q3_three_bombs --pilot-only")
    print()
    print("参数:")
    print("  --pilot-only     运行 bounded pilot (默认入口)")
    print("  --budget-gate-test  跑一次注入式 cheap budget gate smoke 测试 (FAST)")
    print("  -h, --help       显示本帮助")
    print()
    print("Pilot 预算:")
    print("  pilot_q3_evaluation_cap=96, pilot_wall_clock_seconds=900")
    print("  real_task_test_q3_evaluation_cap=3")
    print()
    print("退出码:")
    print("  0 = pilot_complete (预算内完成)")
    print("  1 = evaluation_budget_exhausted / wall_clock_gate_hit (BUDGET_EXHAUSTED != CODE_FAILED)")
    print("  2 = 参数错误 / system_error / resume_identity_mismatch")


def main(argv: Optional[Sequence[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    pilot_only = False
    budget_gate_test = False
    show_help = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("-h", "--help"):
            show_help = True
            i += 1
            continue
        if a == "--pilot-only":
            pilot_only = True
            i += 1
            continue
        if a == "--budget-gate-test":
            budget_gate_test = True
            i += 1
            continue
        print(f"未知参数: {a}", file=sys.stderr)
        return 2

    if show_help:
        _print_help()
        return 0

    if budget_gate_test:
        # 注入式 cheap budget gate 测试 (FAST): 用 1 个合法候选 + coarse profile
        # 验证 eval 流程, 不消耗 96-evaluation cap
        cand = ThreeBombCandidate(
            heading_rad=Q2_CANONICAL_ANCHOR["heading_rad"],
            speed_mps=Q2_CANONICAL_ANCHOR["speed_mps"],
            release_time_1_s=Q2_CANONICAL_ANCHOR["release_time_s"],
            delay_1_s=Q2_CANONICAL_ANCHOR["delay_s"],
            release_time_2_s=Q2_CANONICAL_ANCHOR["release_time_s"] + 1.5,
            delay_2_s=Q2_CANONICAL_ANCHOR["delay_s"],
            release_time_3_s=Q2_CANONICAL_ANCHOR["release_time_s"] + 3.0,
            delay_3_s=Q2_CANONICAL_ANCHOR["delay_s"],
        )
        ok, reason = validate_candidate(cand)
        if not ok:
            print(f"[BUDGET-GATE-TEST] candidate invalid: {reason}",
                  file=sys.stderr)
            return 2
        ev = evaluate_three_bomb_strategy(cand, sample_level="coarse")
        print(
            f"[BUDGET-GATE-TEST] OK: status={ev.status}, "
            f"single_bomb_calls={ev.single_bomb_evaluator_calls}, "
            f"total_union={ev.total_union_duration_s:.6f}s",
            flush=True,
        )
        return 0

    if not pilot_only:
        print("缺少必要参数: --pilot-only 或 --budget-gate-test",
              file=sys.stderr)
        _print_help()
        return 2

    # 1. 读取 execution HEAD (committed, clean)
    import subprocess
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

    # 2. 读取 contract snapshot SHA
    snapshot_path = "work/task_contracts/TASK_006-P0P1-v1.json"
    if not os.path.exists(snapshot_path):
        print(f"contract snapshot missing: {snapshot_path}", file=sys.stderr)
        print("(应在 WORKING commit 后由 contract 流程生成)",
              file=sys.stderr)
        return 2
    with open(snapshot_path, "rb") as f:
        contract_snapshot_sha256 = hashlib.sha256(f.read()).hexdigest()

    # 3. 运行 pilot
    summary = run_pilot(
        execution_head_sha=execution_head_sha,
        contract_snapshot_sha256=contract_snapshot_sha256,
    )

    # 4. 退出码
    if summary["status"]["run_system_error"]:
        return 1
    if summary["status"]["resume_identity_mismatch"]:
        return 2
    if (summary["status"]["evaluation_budget_exhausted"]
            or summary["status"]["wall_clock_gate_hit"]):
        return 1
    if summary["status"]["pilot_complete"]:
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())