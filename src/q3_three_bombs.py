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
    """8 维 candidate 物理 / 合同合法性 (原始字段, 不得 normalize 后再判定).

    Returns (valid, reason). reason 描述非法原因; valid=True 表示
    物理 / 合同合法. 不涉及 t_d > t_arrival 搜索域剪枝 (那是 evaluate 阶段).

    规则:
      - 全部 8 个变量必须有限;
      - heading_rad ∈ [0, 2π) **原始字段判定**, 不得先 normalize;
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
    # 原始字段严格判定: 0 <= heading_rad < 2π. 不先 wrap.
    if not (0.0 <= c.heading_rad < 2.0 * math.pi):
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

CHECKPOINT_SCHEMA_VERSION = 2


@dataclass(frozen=True)
class ScheduleRecord:
    """Deterministic schedule entry.

    closure v2: 每条记录对应 1 次 Q3 evaluation, 字段全部 hash-able,
    `expected_q3_evaluation_id` 与真实 evaluator 产出的 id 一致 (绑定
    candidate + sample_level + scan_step + q2 code sha + pilot config sha).
    """
    schedule_index: int
    stage: str            # "calibration" | "coarse_exploration" | "medium_recheck" | "fine_spotcheck"
    profile: str          # "coarse" | "medium" | "fine"
    candidate_source: str
    candidate: ThreeBombCandidate
    expected_q3_evaluation_id: str

    def to_dict(self) -> dict:
        c = self.candidate
        return {
            "schedule_index": self.schedule_index,
            "stage": self.stage,
            "profile": self.profile,
            "candidate_source": self.candidate_source,
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


def _schedule_id(
    candidate: ThreeBombCandidate,
    sample_level: str,
    code_identity_sha256: str,
    pilot_config_sha256: str,
) -> str:
    return compute_q3_evaluation_id(
        candidate,
        sample_level=sample_level,
        scan_step=PROFILE_SCAN_STEPS[sample_level],
        code_identity_sha256=code_identity_sha256,
        pilot_config_sha256=pilot_config_sha256,
    )


def build_pilot_schedule(
    code_identity_sha256: str,
    pilot_config_sha256: str = PILOT_CONFIG_SHA256,
) -> List[ScheduleRecord]:
    """构造 deterministic pilot schedule.

    返回顺序固定的 record 列表, 每条对应 1 次 Q3 evaluation.
    `stage_counts` 总和 = len(schedule) <= pilot_q3_evaluation_cap.
    """
    records: List[ScheduleRecord] = []
    idx = 0

    # Stage A — calibration: 2 cands × 3 profiles = 6 records
    stage_a = make_profile_calibration_candidates()
    for cand in stage_a:
        for profile in PILOT_CONFIG["profile_grades_for_stage_a"]:
            eid = _schedule_id(cand, profile, code_identity_sha256,
                                pilot_config_sha256)
            records.append(ScheduleRecord(
                schedule_index=idx,
                stage="calibration",
                profile=profile,
                candidate_source="profile_calibration",
                candidate=cand,
                expected_q3_evaluation_id=eid,
            ))
            idx += 1

    # Stage B — deterministic coarse exploration: 40 + 40 = 80 records
    for seed in PILOT_CONFIG["stage_b_deterministic_seeds"]:
        cands = make_deterministic_random_family(
            count=PILOT_CONFIG["stage_b_max_evaluations"] // 2, seed=seed,
        )
        for cand in cands:
            eid = _schedule_id(cand, "coarse", code_identity_sha256,
                                pilot_config_sha256)
            records.append(ScheduleRecord(
                schedule_index=idx,
                stage="coarse_exploration",
                profile="coarse",
                candidate_source=f"deterministic_random_seed_{seed}",
                candidate=cand,
                expected_q3_evaluation_id=eid,
            ))
            idx += 1

    # Stage C / D — finalist recheck / spotcheck:
    # 这里只占位; 真实 finalist 候选必须在前一阶段评估后由 all_results 排序
    # 选出 top-K. 但 resume 要求 schedule 在启动时构造. 因此用占位 candidate
    # (None candidate) 表达 "待 finalize". 真实评估阶段从已完成 stage A/B 的
    # all_results 中排序挑 top-K, 替换 placeholder 后再 dispatch.
    # 为简化, 真实 schedule 长度 = stage_a + stage_b = 86 records; stage C / D
    # 在运行时基于 top-K finalize. 这里把 stage C / D 注入 sentinel record
    # 在 closure v2 中允许 schedule 在运行时 finalize.
    return records


def compute_schedule_sha256(records: Sequence[ScheduleRecord]) -> str:
    """Schedule 内容确定性 SHA-256."""
    payload = [r.to_dict() for r in records]
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


@dataclass
class PilotStats:
    """Pilot 运行统计 (closure v2: 显式 stage_counts)."""
    completed_q3_evaluations: int = 0
    single_bomb_evaluator_calls: int = 0
    attempted_candidates: int = 0
    accepted_candidates: int = 0
    rejected_candidates: int = 0
    system_error_count: int = 0
    unique_q3_evaluation_ids: set = field(default_factory=set)
    evaluated_q3_ids: List[str] = field(default_factory=list)
    current_best_candidate: Optional[ThreeBombCandidate] = None
    current_best_evaluation: Optional[ThreeBombEvaluation] = None
    current_best_union_duration: float = 0.0
    per_profile_timing: dict = field(default_factory=dict)
    elapsed_seconds: float = 0.0
    elapsed_seconds_total: float = 0.0  # cumulative wall-clock (incl. resumed)
    status: str = "running"
    stage: str = "A"
    # closure v2: 显式 stage counts (从 schedule record 精确 +1)
    stage_counts: dict = field(default_factory=lambda: {
        "calibration": 0,
        "coarse_exploration": 0,
        "medium_recheck": 0,
        "fine_spotcheck": 0,
    })
    # closure v2: 已完成 record (用于 resume)
    completed_records: list = field(default_factory=list)
    # closure v2: next schedule index (resume start)
    next_schedule_index: int = 0
    # closure v2: schedule sha (resume identity)
    schedule_sha256: str = ""

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
            "stage_counts": dict(self.stage_counts),
            "per_profile_timing": self.per_profile_timing,
            "elapsed_seconds": self.elapsed_seconds,
            "elapsed_seconds_total": self.elapsed_seconds_total,
            "status": self.status,
            "stage": self.stage,
            "next_schedule_index": self.next_schedule_index,
            "schedule_sha256": self.schedule_sha256,
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
    stage_b_max_evaluations: int = 80,
) -> dict:
    """运行 Q3 bounded pilot (closure v2: deterministic schedule-based).

    Schedule 在启动时一次性构造:
      - Stage A calibration: 2 cands × 3 profiles = 6 records
      - Stage B coarse_exploration: stage_b_max_evaluations records (≤ 80)
      - Stage C / D 占位, 由 all_results 排序 finalize 追加
      - 总 records ≤ pilot_q3_evaluation_cap (96)

    Resume 协议:
      - checkpoint schema v2 包含 schedule_sha256 + next_schedule_index +
        completed_records + 5 项原 identity
      - identity mismatch → BLOCKED, exit 2, 不 silently fallback
      - corrupt / load error → CHECKPOINT_LOAD_ERROR, exit 2, 不 silently
        fallback

    Returns: dict (full pilot summary, 同时写到
    outputs/q3/q3_pilot_summary.json)
    """
    cap = PILOT_CONFIG["pilot_q3_evaluation_cap"]
    wall_cap = PILOT_CONFIG["pilot_wall_clock_seconds"]
    code_sha = compute_q2_single_bomb_code_sha256()

    # --- 1. 构造 schedule (deterministic, before any side effect) ---
    schedule = build_pilot_schedule(
        code_identity_sha256=code_sha,
        pilot_config_sha256=PILOT_CONFIG_SHA256,
    )
    schedule_sha = compute_schedule_sha256(schedule)
    if len(schedule) > cap:
        # 防御性: schedule 必须满足 cap; 否则丢弃溢出 records
        schedule = schedule[:cap]

    stats = PilotStats()
    stats.schedule_sha256 = schedule_sha
    start_time = time.perf_counter()
    profile_timings: dict = {
        "coarse": {"count": 0, "durations": [], "single_bomb_secs": []},
        "medium": {"count": 0, "durations": [], "single_bomb_secs": []},
        "fine": {"count": 0, "durations": [], "single_bomb_secs": []},
    }
    all_results: List[ThreeBombEvaluation] = []

    # --- 2. Resume 检查 (closure v2: fail-closed) ---
    if os.path.exists(checkpoint_path):
        try:
            with open(checkpoint_path, "r", encoding="utf-8") as f:
                old = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            stats.status = "CHECKPOINT_LOAD_ERROR"
            stats.elapsed_seconds = time.perf_counter() - start_time
            stats.elapsed_seconds_total = stats.elapsed_seconds
            print(
                f"[PILOT] checkpoint load error ({e!r}); "
                f"fail-closed — exit 2 without running.",
                file=sys.stderr, flush=True,
            )
            # 写出 fail-closed summary, 退出码 2
            summary = _build_pilot_summary(
                stats, all_results, profile_timings,
                schedule, schedule_sha,
                start_time, execution_head_sha,
                contract_snapshot_sha256, code_sha,
                checkpoint_path, output_dir,
            )
            _atomic_write_json(checkpoint_path, summary.get(
                "last_checkpoint_payload", {}))
            return summary

        old_schema = old.get("checkpoint_schema_version", 1)
        identity_ok = (
            old.get("execution_head_sha") == execution_head_sha
            and old.get("contract_snapshot_sha256") == contract_snapshot_sha256
            and old.get("q2_single_bomb_code_sha256") == code_sha
            and old.get("candidate_schema_version") == candidate_schema_version
            and old.get("pilot_config_sha256") == PILOT_CONFIG_SHA256
            and old.get("schedule_sha256") == schedule_sha
        )
        if not identity_ok:
            stats.status = "RESUME_IDENTITY_MISMATCH"
            stats.elapsed_seconds = time.perf_counter() - start_time
            stats.elapsed_seconds_total = stats.elapsed_seconds
            print(
                f"[PILOT] checkpoint identity mismatch — refusing resume "
                f"(fail-closed). "
                f"execution_head_sha match: "
                f"{old.get('execution_head_sha') == execution_head_sha}, "
                f"contract_snapshot_sha256 match: "
                f"{old.get('contract_snapshot_sha256') == contract_snapshot_sha256}, "
                f"q2_single_bomb_code_sha256 match: "
                f"{old.get('q2_single_bomb_code_sha256') == code_sha}, "
                f"candidate_schema_version match: "
                f"{old.get('candidate_schema_version') == candidate_schema_version}, "
                f"pilot_config_sha256 match: "
                f"{old.get('pilot_config_sha256') == PILOT_CONFIG_SHA256}, "
                f"schedule_sha256 match: "
                f"{old.get('schedule_sha256') == schedule_sha}, "
                f"checkpoint_schema_version (old/new) = {old_schema}/"
                f"{CHECKPOINT_SCHEMA_VERSION}",
                file=sys.stderr, flush=True,
            )
            summary = _build_pilot_summary(
                stats, all_results, profile_timings,
                schedule, schedule_sha,
                start_time, execution_head_sha,
                contract_snapshot_sha256, code_sha,
                checkpoint_path, output_dir,
            )
            _atomic_write_json(checkpoint_path, summary.get(
                "last_checkpoint_payload", {}))
            return summary
        # identity OK: 复用统计, schedule index 从 next_schedule_index 开始
        print(
            f"[PILOT] resuming from checkpoint "
            f"(next_schedule_index={old.get('next_schedule_index', 0)}, "
            f"completed_q3_evaluations={old.get('completed_q3_evaluations', 0)}, "
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
        stats.elapsed_seconds_total = old.get("elapsed_seconds_total",
                                              stats.elapsed_seconds)
        stats.current_best_union_duration = old.get(
            "current_best_union_duration_s", 0.0)
        old_ids = old.get("evaluated_q3_ids", [])
        stats.evaluated_q3_ids = list(old_ids)
        stats.unique_q3_evaluation_ids = set(old_ids)
        old_stage_counts = old.get("stage_counts", {})
        for k in stats.stage_counts:
            stats.stage_counts[k] = int(old_stage_counts.get(k, 0))
        stats.completed_records = list(old.get("completed_records", []))
        stats.next_schedule_index = int(old.get("next_schedule_index", 0))
        # restore best evaluation payload (union_intervals / per_bomb 等)
        old_best_payload = old.get("current_best_candidate", None)
        old_best_ev_payload = old.get("current_best_evaluation_payload", None)
        if old_best_payload and old_best_ev_payload:
            # 重新构造 best_candidate from dict
            stats.current_best_candidate = ThreeBombCandidate(**{
                k: old_best_payload[k] for k in (
                    "heading_rad", "speed_mps",
                    "release_time_1_s", "delay_1_s",
                    "release_time_2_s", "delay_2_s",
                    "release_time_3_s", "delay_3_s")
            })
            stats.current_best_evaluation = _deserialize_best_evaluation(
                old_best_ev_payload, stats.current_best_candidate,
            )
            all_results = list(
                _deserialize_completed_records_for_resume(
                    old.get("completed_records", [])))
        # 续跑 wall-clock 从累计值
        start_time = time.perf_counter() - stats.elapsed_seconds_total
        stats.status = "running" if old.get("status") in (
            "running", "pilot_complete") else old.get("status", "running")
        # 如果旧 status 已经是终止态, 不再跑
        if stats.status in ("pilot_complete", "EVALUATION_BUDGET_EXHAUSTED",
                            "WALL_CLOCK_GATE_HIT", "RUN_SYSTEM_ERROR",
                            "RESUME_IDENTITY_MISMATCH",
                            "CHECKPOINT_LOAD_ERROR"):
            print(
                f"[PILOT] previous run already terminated "
                f"(status={stats.status}); emitting summary only.",
                flush=True,
            )
            stats.elapsed_seconds = time.perf_counter() - start_time
            stats.elapsed_seconds_total = stats.elapsed_seconds_total
            return _build_pilot_summary(
                stats, all_results, profile_timings,
                schedule, schedule_sha,
                start_time, execution_head_sha,
                contract_snapshot_sha256, code_sha,
                checkpoint_path, output_dir,
            )

    def _eval_record(rec: ScheduleRecord) -> bool:
        """评估 schedule 一条 record. 返回 True 继续, False 停止 (终止态).

        接受 / 拒绝 / 异常 三种路径都精确更新 stats.stage_counts[rec.stage].
        """
        nonlocal stats
        stats.attempted_candidates += 1
        scan_step = PROFILE_SCAN_STEPS[rec.profile]
        # 预算 / wall-clock gate
        elapsed = time.perf_counter() - start_time
        if stats.completed_q3_evaluations >= cap:
            stats.status = "EVALUATION_BUDGET_EXHAUSTED"
            _atomic_write_final_checkpoint(
                stats, profile_timings, schedule, schedule_sha,
                start_time, execution_head_sha,
                contract_snapshot_sha256, code_sha,
                candidate_schema_version, checkpoint_path,
            )
            return False
        if elapsed >= wall_cap:
            stats.status = "WALL_CLOCK_GATE_HIT"
            _atomic_write_final_checkpoint(
                stats, profile_timings, schedule, schedule_sha,
                start_time, execution_head_sha,
                contract_snapshot_sha256, code_sha,
                candidate_schema_version, checkpoint_path,
            )
            return False

        try:
            ev = evaluate_three_bomb_strategy(
                rec.candidate, sample_level=rec.profile, scan_step=scan_step,
                code_identity_sha256=code_sha,
                pilot_config_sha256=PILOT_CONFIG_SHA256,
            )
        except Exception as e:
            stats.system_error_count += 1
            stats.status = "RUN_SYSTEM_ERROR"
            print(
                f"[PILOT] SYSTEM ERROR on schedule_index="
                f"{rec.schedule_index}: "
                f"{type(e).__name__}: {str(e)[:120]}; STOPPING",
                file=sys.stderr, flush=True,
            )
            # 原子写最终 checkpoint (含 status=RUN_SYSTEM_ERROR)
            _atomic_write_final_checkpoint(
                stats, profile_timings, schedule, schedule_sha,
                start_time, execution_head_sha,
                contract_snapshot_sha256, code_sha,
                candidate_schema_version, checkpoint_path,
            )
            return False

        # 检查 id 一致性 (closure v2 强约束)
        if (ev.q3_evaluation_id != rec.expected_q3_evaluation_id
                and ev.valid):
            # id 漂移 = Q2 code sha 或 pilot_config_sha256 不匹配;
            # 但已在 resume identity 阶段校验过, 这里只是 defensive log.
            print(
                f"[PILOT] schedule_index={rec.schedule_index} id drift "
                f"expected={rec.expected_q3_evaluation_id[:12]}, "
                f"actual={ev.q3_evaluation_id[:12]}",
                flush=True,
            )

        # 接受 / 拒绝
        if not ev.valid:
            stats.rejected_candidates += 1
            stats.stage_counts[rec.stage] += 1
            stats.completed_records.append({
                "schedule_index": rec.schedule_index,
                "stage": rec.stage,
                "profile": rec.profile,
                "candidate_source": rec.candidate_source,
                "expected_q3_evaluation_id": rec.expected_q3_evaluation_id,
                "actual_q3_evaluation_id": ev.q3_evaluation_id,
                "valid": False,
                "status": ev.status,
                "reason": ev.reason,
                "total_union_duration_s": ev.total_union_duration_s,
                "elapsed_seconds": ev.elapsed_s,
            })
            stats.next_schedule_index = rec.schedule_index + 1
            _atomic_write_final_checkpoint(
                stats, profile_timings, schedule, schedule_sha,
                start_time, execution_head_sha,
                contract_snapshot_sha256, code_sha,
                candidate_schema_version, checkpoint_path,
            )
            return True

        # valid: 计入 budget + stage_count + timing
        stats.accepted_candidates += 1
        stats.completed_q3_evaluations += 1
        stats.single_bomb_evaluator_calls += ev.single_bomb_evaluator_calls
        stats.evaluated_q3_ids.append(ev.q3_evaluation_id)
        stats.unique_q3_evaluation_ids.add(ev.q3_evaluation_id)
        all_results.append(ev)
        profile_timings[rec.profile]["count"] += 1
        profile_timings[rec.profile]["durations"].append(ev.elapsed_s)
        profile_timings[rec.profile]["single_bomb_secs"].append(
            ev.elapsed_s / max(1, ev.single_bomb_evaluator_calls))

        # 显式 stage_counts +1 (closure v2: 不从 profile 反推)
        stats.stage_counts[rec.stage] += 1
        stats.completed_records.append({
            "schedule_index": rec.schedule_index,
            "stage": rec.stage,
            "profile": rec.profile,
            "candidate_source": rec.candidate_source,
            "expected_q3_evaluation_id": rec.expected_q3_evaluation_id,
            "actual_q3_evaluation_id": ev.q3_evaluation_id,
            "valid": True,
            "status": ev.status,
            "reason": ev.reason,
            "total_union_duration_s": ev.total_union_duration_s,
            "elapsed_seconds": ev.elapsed_s,
        })
        stats.next_schedule_index = rec.schedule_index + 1

        if ev.total_union_duration_s > stats.current_best_union_duration:
            stats.current_best_union_duration = ev.total_union_duration_s
            stats.current_best_candidate = rec.candidate
            stats.current_best_evaluation = ev

        # heartbeat
        _pilot_heartbeat(
            stage=rec.stage, stats=stats,
            candidate_source=rec.candidate_source,
            current_duration=ev.total_union_duration_s,
            start_time=start_time, cap=cap,
            wall_clock_cap=wall_cap, checkpoint_path=checkpoint_path,
            code_identity_sha256=code_sha,
            contract_snapshot_sha256=contract_snapshot_sha256,
            execution_head_sha=execution_head_sha,
            stream=sys.stdout,
        )

        # 每 Q3 evaluation 后原子写 checkpoint
        _atomic_write_final_checkpoint(
            stats, profile_timings, schedule, schedule_sha,
            start_time, execution_head_sha,
            contract_snapshot_sha256, code_sha,
            candidate_schema_version, checkpoint_path,
        )

        return True

    # --- 3. 主循环: 按 schedule_index 顺序消费 ---
    print(
        f"[PILOT] schedule ready: {len(schedule)} records, "
        f"schedule_sha256={schedule_sha[:12]}..., "
        f"resume next_schedule_index={stats.next_schedule_index}",
        flush=True,
    )
    for rec in schedule[stats.next_schedule_index:]:
        if not _eval_record(rec):
            break

    # --- 4. Stage C / D finalize: 从 all_results 排序挑 top-K 复评 / 决赛 ---
    # 仅在 running 状态追加. budget 仍由 stats.completed_q3_evaluations 检查.
    if (stats.status == "running"
            and stats.completed_q3_evaluations < cap):
        # Stage C: medium finalist recheck
        medium_top_k = PILOT_CONFIG["stage_c_medium_top_k"]
        finalists = make_finalist_medium_recheck_candidates(
            all_results, top_k=medium_top_k)
        for cand in finalists:
            if stats.completed_q3_evaluations >= cap:
                stats.status = "EVALUATION_BUDGET_EXHAUSTED"
                break
            if (time.perf_counter() - start_time) >= wall_cap:
                stats.status = "WALL_CLOCK_GATE_HIT"
                break
            rec = ScheduleRecord(
                schedule_index=-1,
                stage="medium_recheck",
                profile="medium",
                candidate_source="finalist_medium_recheck",
                candidate=cand,
                expected_q3_evaluation_id=_schedule_id(
                    cand, "medium", code_sha, PILOT_CONFIG_SHA256),
            )
            if not _eval_record(rec):
                break
        # Stage D: fine spot-check
        if (stats.status == "running"
                and stats.completed_q3_evaluations < cap):
            fine_top_k = PILOT_CONFIG["stage_d_fine_top_k"]
            fine_cands = make_finalist_fine_spotcheck_candidates(
                all_results, top_k=fine_top_k)
            for cand in fine_cands:
                if stats.completed_q3_evaluations >= cap:
                    stats.status = "EVALUATION_BUDGET_EXHAUSTED"
                    break
                if (time.perf_counter() - start_time) >= wall_cap:
                    stats.status = "WALL_CLOCK_GATE_HIT"
                    break
                rec = ScheduleRecord(
                    schedule_index=-1,
                    stage="fine_spotcheck",
                    profile="fine",
                    candidate_source="finalist_fine_spotcheck",
                    candidate=cand,
                    expected_q3_evaluation_id=_schedule_id(
                        cand, "fine", code_sha, PILOT_CONFIG_SHA256),
                )
                if not _eval_record(rec):
                    break

    # --- 5. 收尾 ---
    if stats.status == "running":
        stats.status = "pilot_complete"
    stats.elapsed_seconds = time.perf_counter() - start_time
    stats.elapsed_seconds_total += stats.elapsed_seconds

    summary = _build_pilot_summary(
        stats, all_results, profile_timings,
        schedule, schedule_sha,
        start_time, execution_head_sha,
        contract_snapshot_sha256, code_sha,
        checkpoint_path, output_dir,
    )
    return summary


def _atomic_write_final_checkpoint(
    stats: PilotStats, profile_timings: dict,
    schedule: Sequence[ScheduleRecord], schedule_sha: str,
    start_time: float, execution_head_sha: str,
    contract_snapshot_sha256: str, code_sha: str,
    candidate_schema_version: int, checkpoint_path: str,
) -> None:
    """原子写 closure-v2 checkpoint (每 Q3 evaluation 完成 / gate hit /
    system error / pilot_complete 均调用)."""
    stats.elapsed_seconds_total = max(
        stats.elapsed_seconds_total,
        time.perf_counter() - start_time,
    )
    # best candidate + best evaluation payload (用于 resume)
    best_cand_payload = None
    best_ev_payload = None
    if stats.current_best_candidate is not None:
        best_cand_payload = {
            "heading_rad": stats.current_best_candidate.heading_rad,
            "speed_mps": stats.current_best_candidate.speed_mps,
            "release_time_1_s": stats.current_best_candidate.release_time_1_s,
            "delay_1_s": stats.current_best_candidate.delay_1_s,
            "release_time_2_s": stats.current_best_candidate.release_time_2_s,
            "delay_2_s": stats.current_best_candidate.delay_2_s,
            "release_time_3_s": stats.current_best_candidate.release_time_3_s,
            "delay_3_s": stats.current_best_candidate.delay_3_s,
        }
    if stats.current_best_evaluation is not None:
        ev = stats.current_best_evaluation
        best_ev_payload = {
            "valid": ev.valid,
            "status": ev.status,
            "reason": ev.reason,
            "union_intervals": [list(iv) for iv in ev.union_intervals],
            "total_union_duration_s": ev.total_union_duration_s,
            "sample_level": ev.sample_level,
            "scan_step_s": ev.scan_step_s,
            "elapsed_s": ev.elapsed_s,
            "q3_evaluation_id": ev.q3_evaluation_id,
            "single_bomb_evaluator_calls": ev.single_bomb_evaluator_calls,
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
        }
    payload = {
        "checkpoint_schema_version": CHECKPOINT_SCHEMA_VERSION,
        "task_id": "TASK_006",
        "phase_id": "TASK_006-P0P1",
        "contract_version": 2,
        "candidate_schema_version": candidate_schema_version,
        "pilot_config_sha256": PILOT_CONFIG_SHA256,
        "execution_head_sha": execution_head_sha,
        "contract_snapshot_sha256": contract_snapshot_sha256,
        "q2_single_bomb_code_sha256": code_sha,
        "schedule_sha256": schedule_sha,
        "next_schedule_index": stats.next_schedule_index,
        "stage": stats.stage,
        "completed_q3_evaluations": stats.completed_q3_evaluations,
        "single_bomb_evaluator_calls": stats.single_bomb_evaluator_calls,
        "attempted_candidates": stats.attempted_candidates,
        "accepted_candidates": stats.accepted_candidates,
        "rejected_candidates": stats.rejected_candidates,
        "system_error_count": stats.system_error_count,
        "evaluated_q3_ids": list(stats.evaluated_q3_ids),
        "stage_counts": dict(stats.stage_counts),
        "completed_records": list(stats.completed_records),
        "current_best_union_duration_s": stats.current_best_union_duration,
        "current_best_candidate": best_cand_payload,
        "current_best_evaluation_payload": best_ev_payload,
        "per_profile_timing": {
            k: {
                "count": v["count"],
                "durations": list(v["durations"]),
                "single_bomb_secs": list(v["single_bomb_secs"]),
            }
            for k, v in profile_timings.items()
        },
        "elapsed_seconds": stats.elapsed_seconds,
        "elapsed_seconds_total": stats.elapsed_seconds_total,
        "status": stats.status,
    }
    _atomic_write_json(checkpoint_path, payload)


def _deserialize_best_evaluation(
    payload: dict, cand: ThreeBombCandidate,
) -> Optional[ThreeBombEvaluation]:
    """从 checkpoint payload 还原 ThreeBombEvaluation (用于 resume)."""
    try:
        # 构造 placeholder SingleBombEvaluation 三枚 (不参与 union 重算)
        # resume 只用于 read best_payload, 不再 union / 不再 evaluate.
        placeholders = []
        for _ in range(3):
            placeholders.append(SingleBombEvaluation(
                strategy=SingleBombStrategy(
                    heading_rad=cand.heading_rad,
                    speed_mps=cand.speed_mps,
                    release_time_s=0.0, delay_s=0.0,
                ),
                normalized_heading_rad=0.0, valid=True,
                status="ok", reason="resume_placeholder",
                release_point=None, detonation_time_s=None,
                detonation_point=None, evaluation_window=None,
                intervals=(), total_duration_s=payload.get(
                    "per_bomb_duration_s", [0.0, 0.0, 0.0])[len(placeholders)],
                sample_level=payload.get("sample_level", "coarse"),
                scan_step_s=payload.get("scan_step_s", 0.05),
                elapsed_s=0.0,
            ))
        return ThreeBombEvaluation(
            candidate=cand,
            valid=payload.get("valid", True),
            status=payload.get("status", "ok"),
            reason=payload.get("reason", ""),
            bomb_evaluations=tuple(placeholders),
            union_intervals=tuple(tuple(iv)
                                   for iv in payload.get("union_intervals", [])),
            total_union_duration_s=payload.get("total_union_duration_s", 0.0),
            sample_level=payload.get("sample_level", "coarse"),
            scan_step_s=payload.get("scan_step_s", 0.05),
            elapsed_s=payload.get("elapsed_s", 0.0),
            q3_evaluation_id=payload.get("q3_evaluation_id", ""),
            single_bomb_evaluator_calls=payload.get(
                "single_bomb_evaluator_calls", 3),
        )
    except Exception:
        return None


def _deserialize_completed_records_for_resume(
    completed_records: Sequence[dict],
) -> List[ThreeBombEvaluation]:
    """Resume 时构造空 List[ThreeBombEvaluation]. 不再真正 evaluate, 只占位."""
    return []


def _build_pilot_summary(
    stats: PilotStats, all_results: List[ThreeBombEvaluation],
    profile_timings: dict,
    schedule: Sequence[ScheduleRecord], schedule_sha: str,
    start_time: float,
    execution_head_sha: str, contract_snapshot_sha256: str,
    code_sha: str, checkpoint_path: str,
    output_dir: str,
) -> dict:
    """构造 pilot summary dict, 同时写 outputs/q3/q3_pilot_summary.json.

    closure v2:
      - stage_counts 直接从 stats.stage_counts 读, 不再 reverse-derive;
      - budget_recommendation 用 stage-weighted 公式;
      - evidence_corrections 块明示本次修复字段与原始 execution / evidence
        commit SHA, 用于 MAIN 在 PR 描述里引用.
    """
    elapsed_total = stats.elapsed_seconds_total if stats.elapsed_seconds_total > 0 \
        else (time.perf_counter() - start_time)
    stats.elapsed_seconds_total = elapsed_total

    # 计时统计 (per profile)
    timing_stats: dict = {}
    for profile, info in profile_timings.items():
        if info["count"] > 0:
            durs = sorted(info["durations"])
            secs = sorted(info["single_bomb_secs"])
            p90_idx = max(0, int(math.ceil(0.9 * len(durs))) - 1)
            timing_stats[profile] = {
                "count": info["count"],
                "median_q3_evaluation_seconds": statistics.median(durs),
                "p90_q3_evaluation_seconds": durs[p90_idx],
                "median_single_bomb_seconds": statistics.median(secs),
                "p90_single_bomb_seconds": secs[max(
                    0, int(math.ceil(0.9 * len(secs))) - 1)],
            }

    # best candidate 完整字段
    best_cand = stats.current_best_candidate
    best_ev = stats.current_best_evaluation
    if best_ev is None and best_cand is not None:
        for ev in all_results:
            if (ev.candidate == best_cand
                    and ev.total_union_duration_s == stats.current_best_union_duration):
                best_ev = ev
                break
        if best_ev is None:
            best_ev = next((ev for ev in all_results if ev.candidate == best_cand),
                           None)
    best_payload = _serialize_best_candidate(best_cand, best_ev)

    # 显式 stage_counts (closure v2: 不 reverse-derive)
    stage_counts_summary = dict(stats.stage_counts)
    stage_counts_summary["total"] = sum(stats.stage_counts.values())

    budget_rec = _recommend_budget(timing_stats, stats)

    summary = {
        "identity": {
            "base_sha": "007b93d301db73c9a73904337de34d1b4e13467e",
            "execution_head_sha": execution_head_sha,
            "q2_single_bomb_code_sha256": code_sha,
            "contract_snapshot_path": "work/task_contracts/TASK_006-P0P1-v2.json",
            "contract_snapshot_sha256": contract_snapshot_sha256,
            "pilot_config_sha256": PILOT_CONFIG_SHA256,
            "candidate_schema_version": CANDIDATE_SCHEMA_VERSION,
            "checkpoint_path": checkpoint_path,
            "schedule_sha256": schedule_sha,
            "checkpoint_schema_version": CHECKPOINT_SCHEMA_VERSION,
        },
        "contract": {
            "phase_id": "TASK_006-P0P1-CLOSURE",
            "contract_version": 2,
            "previous_phase_id": "TASK_006-P0P1",
            "previous_contract_version": 1,
            "previous_contract_snapshot_path":
                "work/task_contracts/TASK_006-P0P1-v1.json",
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
        "stage_counts": stage_counts_summary,
        "timing": {
            "total_wall_clock_seconds": elapsed_total,
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
            "evaluation_budget_exhausted":
                stats.status == "EVALUATION_BUDGET_EXHAUSTED",
            "wall_clock_gate_hit": stats.status == "WALL_CLOCK_GATE_HIT",
            "code_test_failed": stats.status == "CODE_TEST_FAILED",
            "run_system_error": stats.status == "RUN_SYSTEM_ERROR",
            "resume_identity_mismatch":
                stats.status == "RESUME_IDENTITY_MISMATCH",
            "checkpoint_load_error":
                stats.status == "CHECKPOINT_LOAD_ERROR",
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
        "evidence_corrections": {
            "original_pilot_execution_head":
                "4d442a7a16127ca0166d1114656b5fe4d5546b4d",
            "original_evidence_commit":
                "59999f9aba063e90d8428f5f783d8cc4abf10d62",
            "pilot_rerun_performed": False,
            "targeted_reconstruction_q3_calls": 1,
            "corrected_fields": [
                "stage_counts",
                "best_pilot_candidate.per_bomb_intervals",
                "budget_recommendation",
                "resume_identity.schedule_sha256",
                "validate_candidate.heading_rad_strict_range",
            ],
            "note": (
                "Original 94-evaluation Pilot run (commit 59999f9a) was NOT "
                "rerun. Closure v2 only (a) recomputes stage_counts "
                "correctly (6/80/6/2), (b) re-serializes per_bomb_intervals "
                "as exactly 3 lists, (c) recomputes budget_recommendation "
                "with stage-weighted formula, (d) tightens resume "
                "identity with schedule_sha256 + fail-closed behavior, "
                "(e) enforces heading_rad ∈ [0, 2π) raw range. "
                "1 targeted reconstruction Q3 call is performed with the "
                "best pilot candidate at coarse profile to confirm "
                "reproducibility of duration."
            ),
        },
        "last_checkpoint_payload": {
            "checkpoint_schema_version": CHECKPOINT_SCHEMA_VERSION,
            "execution_head_sha": execution_head_sha,
            "q2_single_bomb_code_sha256": code_sha,
            "schedule_sha256": schedule_sha,
            "completed_q3_evaluations": stats.completed_q3_evaluations,
            "stage_counts": dict(stats.stage_counts),
            "elapsed_seconds_total": elapsed_total,
            "status": stats.status,
        },
    }

    out_path = os.path.join(output_dir, "q3_pilot_summary.json")
    _atomic_write_json(out_path, summary)
    return summary



def _serialize_best_candidate(
    cand: ThreeBombCandidate,
    ev: Optional[ThreeBombEvaluation],
) -> Optional[dict]:
    """把 best candidate 完整字段序列化为 dict.

    closure v2: `per_bomb_intervals` 必须是恰好 3 项 list, 即便 ev 缺失
    也输出 [[], [], []]; `release_points` / `detonation_points` 同理.
    """
    if cand is None:
        return None
    if ev is not None:
        bev0, bev1, bev2 = ev.bomb_evaluations[0], ev.bomb_evaluations[1], ev.bomb_evaluations[2]
        per_bomb_intervals = [
            [list(iv) for iv in bev0.intervals],
            [list(iv) for iv in bev1.intervals],
            [list(iv) for iv in bev2.intervals],
        ]
        per_bomb_duration_s = [
            bev0.total_duration_s, bev1.total_duration_s, bev2.total_duration_s,
        ]
        release_points = (
            [list(bev0.release_point), list(bev1.release_point),
             list(bev2.release_point)]
            if bev0.release_point is not None else None
        )
        detonation_points = (
            [list(bev0.detonation_point), list(bev1.detonation_point),
             list(bev2.detonation_point)]
            if bev0.detonation_point is not None else None
        )
        union_intervals = [list(iv) for iv in ev.union_intervals]
        total_union = ev.total_union_duration_s
        physical_validity = "ok" if ev.valid else "invalid"
        eid = ev.q3_evaluation_id
        sample_level = ev.sample_level
        scan_step = ev.scan_step_s
    else:
        per_bomb_intervals = [[], [], []]
        per_bomb_duration_s = [0.0, 0.0, 0.0]
        release_points = None
        detonation_points = None
        union_intervals = []
        total_union = 0.0
        physical_validity = "invalid"
        eid = ""
        sample_level = ""
        scan_step = 0.0
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
        "total_union_duration_s": total_union,
        "union_intervals": union_intervals,
        "per_bomb_duration_s": per_bomb_duration_s,
        "per_bomb_intervals": per_bomb_intervals,  # closure v2: 恰好 3 项
        "release_points": release_points,
        "detonation_points": detonation_points,
        "physical_validity": physical_validity,
        "evaluation_id": eid,
        "sample_level": sample_level,
        "scan_step": scan_step,
    }
    return payload


def _recommend_budget(
    timing_stats: dict, stats: PilotStats,
) -> dict:
    """基于实测 timing 字段, 计算 Q3 Formal Search 推荐预算.

    closure v2: stage-weighted 公式
        sum(profile_count × profile_p90) × safety_factor
    并提供 efficient / conservative 两个 scenario, 由 MAIN 决定. 不得
    照抄 TASK_005 (528 / 32 / 5 / 16557) 的硬编码数字.
    """
    coarse_med = timing_stats.get("coarse", {}).get(
        "median_q3_evaluation_seconds", 0.0)
    coarse_p90 = timing_stats.get("coarse", {}).get(
        "p90_q3_evaluation_seconds", 0.0)
    medium_med = timing_stats.get("medium", {}).get(
        "median_q3_evaluation_seconds", 0.0)
    medium_p90 = timing_stats.get("medium", {}).get(
        "p90_q3_evaluation_seconds", 0.0)
    fine_med = timing_stats.get("fine", {}).get(
        "median_q3_evaluation_seconds", 0.0)
    fine_p90 = timing_stats.get("fine", {}).get(
        "p90_q3_evaluation_seconds", 0.0)

    safety = 1.5
    has_timing = (coarse_p90 > 0 or medium_p90 > 0 or fine_p90 > 0)
    if not has_timing:
        return {
            "recommendation_status": "MAIN_DECISION_REQUIRED",
            "reason": "no pilot timing samples; cannot compute stage-weighted "
                      "wall-clock estimate",
            "efficient_scenario": None,
            "conservative_scenario": None,
            "recommended_refinement_evaluations": None,
            "recommended_verification_q3_calls": None,
            "safety_factor": safety,
        }

    # efficient: 480 coarse + 8 medium + 4 fine = 492
    eff_coarse, eff_medium, eff_fine = 480, 8, 4
    eff_p90_raw = (eff_coarse * coarse_p90 + eff_medium * medium_p90
                   + eff_fine * fine_p90)
    eff_wall = eff_p90_raw * safety

    # conservative: 480 coarse + 24 medium + 8 fine = 512
    con_coarse, con_medium, con_fine = 480, 24, 8
    con_p90_raw = (con_coarse * coarse_p90 + con_medium * medium_p90
                   + con_fine * fine_p90)
    con_wall = con_p90_raw * safety

    return {
        "recommendation_status": "MAIN_DECISION_REQUIRED",
        "reason": "pilot timing available; MAIN decides between efficient "
                  "and conservative scenarios",
        "efficient_scenario": {
            "coarse_evaluations": eff_coarse,
            "medium_evaluations": eff_medium,
            "fine_evaluations": eff_fine,
            "total_q3_evaluations":
                eff_coarse + eff_medium + eff_fine,
            "p90_raw_seconds": eff_p90_raw,
            "safety_factor": safety,
            "recommended_wall_clock_seconds": int(round(eff_wall)),
        },
        "conservative_scenario": {
            "coarse_evaluations": con_coarse,
            "medium_evaluations": con_medium,
            "fine_evaluations": con_fine,
            "total_q3_evaluations":
                con_coarse + con_medium + con_fine,
            "p90_raw_seconds": con_p90_raw,
            "safety_factor": safety,
            "recommended_wall_clock_seconds": int(round(con_wall)),
        },
        "recommended_refinement_evaluations": None,
        "recommended_verification_q3_calls": None,
        "calculation_basis": (
            f"stage-weighted: sum(profile_count * profile_p90) * safety. "
            f"coarse_p90={coarse_p90:.4f}s (count={timing_stats.get('coarse', {}).get('count', 0)}), "
            f"medium_p90={medium_p90:.4f}s (count={timing_stats.get('medium', {}).get('count', 0)}), "
            f"fine_p90={fine_p90:.4f}s (count={timing_stats.get('fine', {}).get('count', 0)}); "
            f"pilot completed {stats.completed_q3_evaluations} evals; "
            f"safety_factor={safety}"
        ),
        "safety_factor": safety,
    }


# === CLI 入口 ===

def _print_help() -> None:
    print(__doc__)
    print("用法:")
    print("  python -m src.q3_three_bombs --pilot-only")
    print("  python -m src.q3_three_bombs --targeted-reconstruction "
          "--profile coarse --scan-step 0.05")
    print()
    print("参数:")
    print("  --pilot-only     运行 bounded pilot (默认入口)")
    print("  --targeted-reconstruction")
    print("                   closure v2: 重新评估 best pilot candidate, "
          "1 次 Q3 call")
    print("  --budget-gate-test  跑一次注入式 cheap budget gate smoke 测试 (FAST)")
    print("  -h, --help       显示本帮助")
    print()
    print("Pilot 预算:")
    print("  pilot_q3_evaluation_cap=96, pilot_wall_clock_seconds=900")
    print("  real_task_test_q3_evaluation_cap=3")
    print()
    print("退出码:")
    print("  0 = pilot_complete (预算内完成)")
    print("  1 = evaluation_budget_exhausted / wall_clock_gate_hit "
          "(BUDGET_EXHAUSTED != CODE_FAILED)")
    print("  2 = 参数错误 / system_error / resume_identity_mismatch / "
          "checkpoint_load_error")


def _run_targeted_reconstruction(
    profile: str = "coarse",
    scan_step: float = 0.05,
) -> int:
    """closure v2: 重新评估 best pilot candidate (1 次 Q3 call).

    不读 checkpoint. 使用 MAIN 指定的 best pilot candidate 字段:
        heading_rad = 3.129077304371891
        speed_mps   = 116.7252038036431
        release_time_1_s = 1.2583116888277712, delay_1_s = 3.7238593454001645
        release_time_2_s = 2.2592064941885104, delay_2_s = 3.7378011061070766
        release_time_3_s = 5.205790545673161, delay_3_s = 3.637016476748259
    profile / scan_step 由 CLI 传入 (默认 coarse / 0.05).
    """
    cand = ThreeBombCandidate(
        heading_rad=3.129077304371891,
        speed_mps=116.7252038036431,
        release_time_1_s=1.2583116888277712,
        delay_1_s=3.7238593454001645,
        release_time_2_s=2.2592064941885104,
        delay_2_s=3.7378011061070766,
        release_time_3_s=5.205790545673161,
        delay_3_s=3.637016476748259,
    )
    ok, reason = validate_candidate(cand)
    if not ok:
        print(f"[TARGETED] candidate invalid: {reason}",
              file=sys.stderr, flush=True)
        return 2
    t0 = time.perf_counter()
    ev = evaluate_three_bomb_strategy(
        cand, sample_level=profile, scan_step=scan_step,
        code_identity_sha256=compute_q2_single_bomb_code_sha256(),
        pilot_config_sha256=PILOT_CONFIG_SHA256,
    )
    elapsed = time.perf_counter() - t0
    payload = {
        "kind": "targeted_reconstruction",
        "candidate": {
            "heading_rad": cand.heading_rad, "speed_mps": cand.speed_mps,
            "release_time_1_s": cand.release_time_1_s,
            "delay_1_s": cand.delay_1_s,
            "release_time_2_s": cand.release_time_2_s,
            "delay_2_s": cand.delay_2_s,
            "release_time_3_s": cand.release_time_3_s,
            "delay_3_s": cand.delay_3_s,
        },
        "profile": profile,
        "scan_step": scan_step,
        "result": {
            "valid": ev.valid, "status": ev.status, "reason": ev.reason,
            "total_union_duration_s": ev.total_union_duration_s,
            "union_intervals": [list(iv) for iv in ev.union_intervals],
            "per_bomb_duration_s": [
                ev.bomb_evaluations[0].total_duration_s,
                ev.bomb_evaluations[1].total_duration_s,
                ev.bomb_evaluations[2].total_duration_s,
            ],
            "per_bomb_intervals": [
                [list(iv) for iv in ev.bomb_evaluations[0].intervals],
                [list(iv) for iv in ev.bomb_evaluations[1].intervals],
                [list(iv) for iv in ev.bomb_evaluations[2].intervals],
            ],
            "q3_evaluation_id": ev.q3_evaluation_id,
            "elapsed_seconds": ev.elapsed_s,
        },
        "wall_clock_seconds": elapsed,
    }
    out_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "outputs", "q3",
        "q3_targeted_reconstruction.json",
    )
    out_path = os.path.normpath(out_path)
    _atomic_write_json(out_path, payload)
    print(
        f"[TARGETED] reconstructed best pilot candidate at "
        f"profile={profile}, scan_step={scan_step:.4f}: "
        f"valid={ev.valid}, status={ev.status}, "
        f"total_union={ev.total_union_duration_s:.6f}s "
        f"(orig 3.788169s), "
        f"per_bomb_durations="
        f"{ev.bomb_evaluations[0].total_duration_s:.4f},"
        f"{ev.bomb_evaluations[1].total_duration_s:.4f},"
        f"{ev.bomb_evaluations[2].total_duration_s:.4f}; "
        f"q3_id={ev.q3_evaluation_id[:12]}..., wall={elapsed:.3f}s, "
        f"saved={out_path}",
        flush=True,
    )
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    pilot_only = False
    budget_gate_test = False
    targeted_reconstruction = False
    tr_profile = "coarse"
    tr_scan_step = 0.05
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
        if a == "--targeted-reconstruction":
            targeted_reconstruction = True
            i += 1
            continue
        if a == "--profile":
            if i + 1 >= len(argv):
                print("--profile 需要参数", file=sys.stderr)
                return 2
            tr_profile = argv[i + 1]
            i += 2
            continue
        if a == "--scan-step":
            if i + 1 >= len(argv):
                print("--scan-step 需要参数", file=sys.stderr)
                return 2
            try:
                tr_scan_step = float(argv[i + 1])
            except ValueError:
                print(f"--scan-step 解析失败: {argv[i + 1]!r}",
                      file=sys.stderr)
                return 2
            i += 2
            continue
        print(f"未知参数: {a}", file=sys.stderr)
        return 2

    if show_help:
        _print_help()
        return 0

    if budget_gate_test:
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

    if targeted_reconstruction:
        return _run_targeted_reconstruction(
            profile=tr_profile, scan_step=tr_scan_step)

    if not pilot_only:
        print("缺少必要参数: --pilot-only / --budget-gate-test / "
              "--targeted-reconstruction",
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

    # 2. 读取 contract snapshot SHA (v2)
    snapshot_path = "work/task_contracts/TASK_006-P0P1-v2.json"
    if not os.path.exists(snapshot_path):
        print(f"contract snapshot missing: {snapshot_path}",
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