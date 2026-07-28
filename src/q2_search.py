"""Q2 Search Implementation (TASK_004 Q2 REAL SEARCH CORE V1).

本轮任务范围 (TASK_004 Q2 REAL SEARCH CORE V1):

- 串行 real-search pipeline (workers=1, evaluator=real);
- deterministic candidate generation (anchor + global + local);
- manifest identity (seed / domain / algorithm version / candidate vectors);
- checkpoint v2 (resume identity 校验);
- coarse → medium → local refinement → fine 顺序;
- 小规模 pilot (固定 seed / 固定预算, 总运行时间 < 5 分钟);
- 本地测试 + commit + push + Draft PR.

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
import statistics
import sys
import tempfile
import time
import traceback
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple


# =============================================================================
#  第一节: 搜索域 (在 Foundation 合同上推导, 不得重复定义物理常量)
# =============================================================================
# 物理合法范围 (复用 Foundation 评价搜索域):
#   - heading_rad: 周期变量 [0, 2π)
#   - speed_mps:   [70, 140] (FACTS §9, 含端点)
#   - release_time_s: ≥ 0 (项目约束); 上界为 t_arrival - 1 (搜索域剪枝,
#     避免 t_detonate > t_arrival; 这是搜索域约定, 不是物理禁令)
#   - delay_s: ≥ 0 (项目约束); 上界由炸弹触地推导 (EPS_GROUND 吸收下边界),
#     delay_max = sqrt(2 * U0_z / G), 物理上确保 z ≥ 0 (Foundation 合同)
# 搜索域 = 物理合法 ∩ 搜索域无损剪枝范围. evaluator 仍必须做最终合法性判断.

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
    # release_time 上界推迟到调用方注入 t_arrival, 不在此硬编码 66.
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

    约束:
      - heading 周期 wrap 到 [0, 2π)
      - speed / release_time / delay 清零负值; 上界 clamp 到 *None 表示无上界*
        (调用方负责传入已经含上界的 domain)
    """
    return (
        _wrap_heading(heading_rad),
        float(speed_mps),
        max(0.0, float(release_time_s)),
        max(0.0, float(delay_s)),
    )


def parse_candidate(c: Any) -> Tuple[float, float, float, float]:
    """从可迭代对象构造规范化候选. 长度必须 == 4."""
    if not isinstance(c, (tuple, list)) or len(c) != 4:
        raise ValueError(f"候选必须是 4 元, 实际 {type(c).__name__} len={len(c) if hasattr(c, '__len__') else '?'}")
    return make_strategy(
        heading_rad=c[0], speed_mps=c[1],
        release_time_s=c[2], delay_s=c[3],
    )


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
#  第四节: 候选生成 (deterministic)
# =============================================================================
def generate_deterministic_candidates(seed: int, count: int,
                                       domain: Mapping[str, Mapping[str, Any]],
                                       release_time_max: float,
                                       include_anchor: bool = True
                                       ) -> List[Tuple[float, float, float, float]]:
    """生成 deterministic 候选池.

    Args:
        seed: random.Random 种子.
        count: 候选数量 (不含 anchor).
        domain: 搜索域描述符 (含 heading / speed / delay 上下界).
        release_time_max: release_time 上界 (由调用方注入 t_arrival 决定).
        include_anchor: 是否在第 0 位插入 Q1 锚点.

    Returns:
        候选 list, 每项为 4 元归一化元组.
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


def wrap_local_candidate(base: Tuple[float, float, float, float],
                          rng: random.Random,
                          domain: Mapping[str, Mapping[str, Any]],
                          release_time_max: float,
                          delta_rel: Sequence[float]
                          ) -> Tuple[float, float, float, float]:
    """围绕 base 生成局部扰动候选.

    Args:
        base: 父候选 (4 元).
        rng: 共享随机源.
        domain: 搜索域描述符.
        release_time_max: release_time 上界.
        delta_rel: 4 个相对扰动幅度 (heading / speed / release / delay).

    Returns:
        4 元归一化候选.
    """
    h, s, r, d = base
    dh, ds, dr, dd = delta_rel
    new_h = h + rng.uniform(-dh, dh)
    new_s = s + rng.uniform(-ds, ds)
    new_r = r + rng.uniform(-dr, dr)
    new_d = d + rng.uniform(-dd, dd)
    return make_strategy(
        heading_rad=new_h, speed_mps=new_s,
        release_time_s=new_r, delay_s=new_d,
    )


# =============================================================================
#  第五节: Manifest 文本与 SHA-256
# =============================================================================
def build_manifest_text(seed: int,
                         vectors: Sequence[Tuple[float, float, float, float]],
                         algorithm_version: str = "v1",
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
                     algorithm_version: str = "v1",
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
    }


# =============================================================================
#  第六节: SearchEvaluationRow (统一结果结构)
# =============================================================================
@dataclass
class SearchEvaluationRow:
    """单候选评估结果 (统一结构, JSON 可序列化).

    字段:
      - candidate_index: 候选在全局池中的 index
      - stage: 评估阶段 ('coarse' / 'medium' / 'fine')
      - seed: 随机种子
      - heading_rad, speed_mps, release_time_s, delay_s: 4 元变量
      - valid: bool, 物理/合同合法
      - status: str, Foundation 状态 ('invalid' / 'pruned_zero' / 'zero_window' / 'ok' / 'system_error')
      - total_duration_s: float, 严格遮蔽总时长 (zero=0.0)
      - intervals: list[(a, b)] (ok 状态才有)
      - release_point, detonation_point: (x, y, z) 或 None
      - detonation_time_s: float 或 None
      - sample_level, scan_step_s: 评估参数
      - evaluator_kind: 'real' | 'fake'
      - wall_clock_s: 评估耗时
      - error_type, error_message: 程序异常时填充
    """
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
        return cls(
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


# =============================================================================
#  第七节: Real evaluator adapter (调用 evaluate_single_bomb_strategy)
# =============================================================================
def evaluate_with_real_evaluator(
    candidate: Tuple[float, float, float, float],
    *,
    sample_level: str,
    scan_step: float,
    seed: int,
) -> SearchEvaluationRow:
    """Real evaluator: 真实调用 src.q2_single_bomb.evaluate_single_bomb_strategy.

    Args:
        candidate: (heading_rad, speed_mps, release_time_s, delay_s).
        sample_level: 'coarse' | 'medium' | 'fine'.
        scan_step: 时间扫描步长 (s).
        seed: 记录用 (与 evaluator 实际行为无关, 真实 evaluation 内部不依赖
              random; 真实 motion 完全由候选决定).

    Returns:
        SearchEvaluationRow. 任何程序异常 (geometry / type / ValueError 等)
        都被捕获, 转换为 status='system_error', valid=False.
    """
    from src.q2_single_bomb import (
        SingleBombStrategy,
        evaluate_single_bomb_strategy,
    )

    h, s, r, d = candidate
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
) -> SearchEvaluationRow:
    """Fake evaluator: 仅用于测试 / dry-run / 调度开销 benchmark.

    合成目标值 (Phase 0 / Locked):
      total = (sin(h) + 1) * 0.5 + (s - 70) / 70 + r / 60 + d / 30
    不得用于正式 Q2 决策; 真实 search 必须 evaluator='real'.
    """
    if sleep_s > 0.0:
        time.sleep(sleep_s)
    h, s, r, d = candidate
    total = (math.sin(h) + 1.0) * 0.5 + (s - 70.0) / 70.0 \
             + (r / 60.0) + (d / 30.0)
    t0 = time.perf_counter()
    elapsed = time.perf_counter() - t0
    return SearchEvaluationRow(
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
#  第八节: 串行 pipeline (workers=1)
# =============================================================================
def run_serial_real(candidates: Sequence[Tuple[float, float, float, float]],
                     *,
                     sample_level: str = "coarse",
                     scan_step: float = 0.05,
                     seed: int = 2025,
                     start_index: int = 0,
                     resume_rows: Optional[Sequence[SearchEvaluationRow]] = None,
                     ) -> List[SearchEvaluationRow]:
    """workers=1 serial real evaluator.

    Args:
        candidates: 待评估候选序列.
        sample_level: 'coarse' | 'medium' | 'fine'.
        scan_step: 扫描步长 (s).
        seed: random seed (用于 SearchEvaluationRow.seed 字段).
        start_index: 起始 index (用于 resume).
        resume_rows: 已完成的 row 列表 (用于 resume 等价).

    Returns:
        List[SearchEvaluationRow], 顺序与 (start_index + offset) 对齐.
    """
    if start_index < 0:
        raise ValueError(f"start_index 必须 ≥ 0, 实际 {start_index}")
    if resume_rows is None:
        resume_rows = []
    done: Dict[int, SearchEvaluationRow] = {
        r.candidate_index: r for r in resume_rows
    }
    out: List[SearchEvaluationRow] = list(resume_rows)
    for offset, cand in enumerate(candidates):
        idx = start_index + offset
        if idx in done:
            continue
        row = evaluate_with_real_evaluator(
            cand, sample_level=sample_level,
            scan_step=scan_step, seed=seed,
        )
        row.candidate_index = idx
        out.append(row)
    return out


# =============================================================================
#  第九节: 串行 pipeline: coarse → medium → local → fine
# =============================================================================
@dataclass
class StagePlan:
    """单阶段评估的执行计划."""
    stage: str                  # 'coarse' / 'medium' / 'fine'
    sample_level: str           # 同 stage
    scan_step: float
    source: str                 # 'global' / 'top_k' / 'local' / 'final'
    top_k: int = 0              # 0 = 全部保留
    n_local: int = 0            # 围绕每个 top_k 候选的 local 数量
    local_delta: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)  # 局部扰动幅度


# 默认 pilot 预算 (TASK_004 Q2 REAL SEARCH CORE V1)
DEFAULT_PILOT_BUDGET = {
    "global_coarse_count": 96,
    "coarse_top_k": 8,
    "medium_re_evaluate_count": 8,
    "local_per_top": 6,
    "local_max_count": 48,
    "fine_final_count": 2,
}


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
    """围绕 top rows 生成局部扰动候选."""
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
    """保持顺序去重."""
    seen = set()
    out = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def run_search_pipeline(seed: int,
                          u0: Tuple[float, float, float],
                          g: float,
                          t_arrival: float,
                          budget: Optional[Dict[str, int]] = None,
                          scan_step_coarse: float = 0.05,
                          scan_step_medium: float = 0.02,
                          scan_step_fine: float = 0.01,
                          output_dir: str = "work/q2_search",
                          ) -> Dict[str, Any]:
    """完整 pilot pipeline: coarse → medium → local → fine.

    Args:
        seed: 随机种子.
        u0: FY1 初始位置.
        g: 重力加速度.
        t_arrival: 导弹到达假目标时刻.
        budget: pilot 预算 dict (默认 DEFAULT_PILOT_BUDGET).
        scan_step_*: 三档扫描步长.
        output_dir: 写入 work/ 的根目录.

    Returns:
        dict 含 status counts, best-known candidate, rows, manifest.
    """
    if budget is None:
        budget = dict(DEFAULT_PILOT_BUDGET)
    if t_arrival <= 0:
        raise ValueError(f"t_arrival 必须 > 0, 实际 {t_arrival}")
    domain = build_search_domain(u0, g)
    domain["release_time_s"]["max"] = max(1e-3, t_arrival - 1.0)

    # ── Stage 1: coarse global exploration ──
    candidates = generate_deterministic_candidates(
        seed=seed, count=budget["global_coarse_count"],
        domain=domain, release_time_max=domain["release_time_s"]["max"],
        include_anchor=True,
    )
    # manifest identity
    manifest = manifest_record(seed, candidates,
                                algorithm_version="v1",
                                domain=q_space_descriptor(domain))
    coarse_rows = run_serial_real(
        candidates, sample_level="coarse",
        scan_step=scan_step_coarse, seed=seed,
    )
    # ── Stage 2: medium re-evaluation Top-K ──
    top_k = rank_top_k(coarse_rows, budget["coarse_top_k"])
    top_k_vec = [(r.heading_rad, r.speed_mps,
                  r.release_time_s, r.delay_s) for r in top_k]
    medium_rows: List[SearchEvaluationRow] = []
    if top_k_vec:
        medium_rows = run_serial_real(
            top_k_vec, sample_level="medium",
            scan_step=scan_step_medium, seed=seed,
        )
    # ── Stage 3: local candidates ──
    # 围绕 medium 重新排序后的 top_k (从 medium 评估中再选 top)
    medium_top = rank_top_k(medium_rows, budget["medium_re_evaluate_count"])
    local_delta = (
        0.10,                        # heading: ~5.7 deg
        5.0,                         # speed mps
        0.5,                         # release s
        0.3,                         # delay s
    )
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
    )
    # ── Stage 4: fine final candidates ──
    combined = coarse_rows + medium_rows + local_rows
    final_top = rank_top_k(combined, budget["fine_final_count"])
    final_vec = [(r.heading_rad, r.speed_mps,
                  r.release_time_s, r.delay_s) for r in final_top]
    fine_rows = run_serial_real(
        final_vec, sample_level="fine",
        scan_step=scan_step_fine, seed=seed,
    )

    # 汇总
    all_rows = coarse_rows + medium_rows + local_rows + fine_rows
    status_counts: Dict[str, int] = {
        "ok": 0, "invalid": 0, "pruned_zero": 0,
        "zero_window": 0, "system_error": 0,
    }
    for r in all_rows:
        if r.status in status_counts:
            status_counts[r.status] += 1
    best = rank_top_k(all_rows, 1)
    best_row = best[0] if best else None

    # 写入 work/q2_search/
    os.makedirs(output_dir, exist_ok=True)
    output = {
        "task": "TASK_004 Q2 REAL SEARCH CORE V1",
        "declaration": "PILOT / NOT A FORMAL Q2 RESULT",
        "best_known_disclaimer": "BEST-KNOWN CANDIDATE / NOT A PROVEN GLOBAL OPTIMUM",
        "seed": seed,
        "domain": q_space_descriptor(domain),
        "manifest_sha256": manifest["sha256"],
        "budget": budget,
        "status_counts": status_counts,
        "n_total_rows": len(all_rows),
        "best_known_candidate": best_row.to_dict() if best_row else None,
        "manifest": manifest,
        "coarse_top_k": [r.to_dict() for r in top_k],
        "medium_top": [r.to_dict() for r in medium_top],
        "all_rows": [r.to_dict() for r in all_rows],
    }
    out_path = os.path.join(output_dir, "pilot_result.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # 简易 CLI 报告
    print(f"[PILOT] seed={seed} status_counts={status_counts}")
    print(f"[PILOT] manifest_sha256={manifest['sha256']}")
    if best_row is not None:
        print(f"[PILOT] best_known total_duration_s={best_row.total_duration_s:.6f}")
        print(f"[PILOT] best_known candidate={best_row.to_dict()}")
    print(f"[PILOT] output={out_path}")
    print(f"[PILOT] declaration={output['declaration']}")
    print(f"[PILOT] best_known_disclaimer={output['best_known_disclaimer']}")

    return output


# =============================================================================
#  第十节: Checkpoint v2 (resume identity 校验)
# =============================================================================
CHECKPOINT_SCHEMA_V2: int = 2


@dataclass
class CheckpointV2:
    """Search checkpoint v2."""
    schema: int
    algorithm_version: str
    seed: int
    domain_hash: str
    manifest_sha256: str
    evaluator_kind: str
    code_revision: str
    stage: str
    sample_level: str
    scan_step_s: float
    completed_indexes: List[int] = field(default_factory=list)
    rows: List[SearchEvaluationRow] = field(default_factory=list)
    best_index: int = -1
    best_total: float = 0.0
    status_counts: Dict[str, int] = field(default_factory=dict)
    system_errors: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema": int(self.schema),
            "algorithm_version": str(self.algorithm_version),
            "seed": int(self.seed),
            "domain_hash": str(self.domain_hash),
            "manifest_sha256": str(self.manifest_sha256),
            "evaluator_kind": str(self.evaluator_kind),
            "code_revision": str(self.code_revision),
            "stage": str(self.stage),
            "sample_level": str(self.sample_level),
            "scan_step_s": float(self.scan_step_s),
            "completed_indexes": [int(i) for i in self.completed_indexes],
            "rows": [r.to_dict() for r in self.rows],
            "best_index": int(self.best_index),
            "best_total": float(self.best_total),
            "status_counts": dict(self.status_counts),
            "system_errors": list(self.system_errors),
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "CheckpointV2":
        if not isinstance(d, Mapping):
            raise ValueError(f"checkpoint 必须是 mapping, 实际 {type(d).__name__}")
        required = {"schema", "algorithm_version", "seed", "domain_hash",
                    "manifest_sha256", "evaluator_kind", "code_revision",
                    "stage", "sample_level", "scan_step_s"}
        missing = required - set(d.keys())
        if missing:
            raise ValueError(f"checkpoint 缺少字段: {sorted(missing)}")
        schema = int(d["schema"])
        if schema != CHECKPOINT_SCHEMA_V2:
            raise ValueError(f"checkpoint schema mismatch: 当前 {CHECKPOINT_SCHEMA_V2}, 文件 {schema}")
        return cls(
            schema=schema,
            algorithm_version=str(d["algorithm_version"]),
            seed=int(d["seed"]),
            domain_hash=str(d["domain_hash"]),
            manifest_sha256=str(d["manifest_sha256"]),
            evaluator_kind=str(d["evaluator_kind"]),
            code_revision=str(d["code_revision"]),
            stage=str(d["stage"]),
            sample_level=str(d["sample_level"]),
            scan_step_s=float(d["scan_step_s"]),
            completed_indexes=[int(i) for i in d.get("completed_indexes", [])],
            rows=[SearchEvaluationRow.from_dict(r) for r in d.get("rows", [])],
            best_index=int(d.get("best_index", -1)),
            best_total=float(d.get("best_total", 0.0)),
            status_counts=dict(d.get("status_counts", {})),
            system_errors=list(d.get("system_errors", [])),
        )


def _hash_domain(domain: Mapping[str, Any]) -> str:
    text = json.dumps(domain, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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
                            expected_stage: str,
                            expected_sample_level: str,
                            expected_scan_step: float,
                            expected_code_revision: str,
                            ) -> None:
    """校验 resume identity. 任一 mismatch 抛出 ValueError."""
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
    if ck.stage != expected_stage:
        raise ValueError(f"checkpoint stage mismatch: {ck.stage} vs {expected_stage}")
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
#  第十一节: parallel (FakeEvaluator only, EXPERIMENTAL)
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
#  第十二节: CLI
# =============================================================================
def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m src.q2_search",
        description="Q2 Real Search Core v1 (TASK_004)",
    )
    p.add_argument("--run-search", action="store_true",
                    help="执行真实 Search (默认仅打印 banner)")
    p.add_argument("--evaluator", choices=["real", "fake"], default="real",
                    help="evaluator 类型; real 必须 --run-search")
    p.add_argument("--mode", choices=["pilot", "formal"], default="pilot",
                    help="执行模式; pilot 默认上限预算")
    p.add_argument("--seed", type=int, default=2025)
    p.add_argument("--checkpoint-dir", default="work/q2_search",
                    help="checkpoint / 输出目录")
    p.add_argument("--workers", type=int, default=1,
                    help="workers 数; real 模式下 workers > 1 拒绝")
    p.add_argument("--global-coarse-count", type=int, default=None)
    p.add_argument("--coarse-top-k", type=int, default=None)
    p.add_argument("--medium-re-evaluate-count", type=int, default=None)
    p.add_argument("--local-per-top", type=int, default=None)
    p.add_argument("--local-max-count", type=int, default=None)
    p.add_argument("--fine-final-count", type=int, default=None)
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI 入口."""
    parser = _build_argparser()
    args = parser.parse_args(argv)

    if not args.run_search:
        print("Q2 SEARCH IMPLEMENTATION (TASK_004 Q2 REAL SEARCH CORE V1)")
        print("=" * 70)
        print("NOT AN OPTIMIZATION RESULT")
        print("默认仅打印 banner; 真实 Search 必须显式 --run-search.")
        print("推荐：")
        print("  python -m src.q2_search --run-search --evaluator real "
              "--mode pilot --seed 2025 --checkpoint-dir work/q2_search")
        return 0

    # --run-search --evaluator fake 拒绝
    if args.evaluator == "fake":
        print("ERROR: --run-search --evaluator fake 拒绝. "
              "正式 Search 必须 evaluator=real.",
              file=sys.stderr)
        return 2

    # real 模式 workers > 1 拒绝 (EXPERIMENTAL / DISABLED FOR FORMAL SEARCH)
    if args.workers > 1:
        print(f"ERROR: real 模式 workers > 1 当前禁用 (EXPERIMENTAL). "
              f"workers={args.workers}",
              file=sys.stderr)
        return 2

    # 注入最新 main 的物理常量
    from src.q1_baseline import U0, G, missile_arrival_time
    t_arrival = missile_arrival_time()
    u0_vec = tuple(U0)

    budget = dict(DEFAULT_PILOT_BUDGET)
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
    if args.fine_final_count is not None:
        budget["fine_final_count"] = args.fine_final_count

    if args.mode == "formal":
        # formal 模式本轮允许入口存在, 但默认沿用 pilot 预算
        # (避免无上限运行)
        pass

    out = run_search_pipeline(
        seed=args.seed, u0=u0_vec, g=G,
        t_arrival=t_arrival, budget=budget,
        output_dir=args.checkpoint_dir,
    )

    # 退出码: 0 表示无 system_error; 1 表示有 system_error
    if out["status_counts"].get("system_error", 0) > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
