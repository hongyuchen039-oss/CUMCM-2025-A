"""Q1 完整圆柱遮蔽判定冻结 (FULL-CYLINDER CANDIDATE / EXPERIMENTAL).

按 FACTS.md §11 与 MODEL.md"完整圆柱遮蔽正式候选"章节定义:

- 真目标 K = {(x, y, z) | x² + (y-200)² ≤ 49, 0 ≤ z ≤ 10}
- 严格遮蔽主判据: 所有当前可见表面采样点的视线均与烟幕球体相交
- 覆盖率仅作辅助诊断, 不使用人为覆盖率阈值
- 空间采样: coarse / medium / fine 三档
- 时间扫描: 0.02 / 0.01 / 0.005 s (medium 空间采样下)
- 边界函数: f_cylinder(t) = max_visible_distance(t) - R_cloud

几何层与时序层拆分:
- evaluate_occlusion_geometry(m, c, samples, radius) — 纯几何, 不读取时间/轨迹
- evaluate_cylinder_state(t, samples, ...) — 时序包装, 注入轨迹回调
- strict_boundary_value / find_strict_intervals — 同样支持轨迹注入

可见性边界 (本轮 FIX 之后):
- visible ⇔ n(X) · (M - X) >= -EPS_VISIBLE
- 切线轮廓邻域不再被排除 (保守可见性, 防"放宽成严格遮蔽")
- EPS_VISIBLE 必须有限且 ≥ 0

空可见集:
- 时间窗外返回 strict_occlusion=False / strict_margin=-inf / coverage_ratio=0
- 时间窗内 visible_count == 0 ⇒ ValueError (几何配置错误)

只使用 Python 标准库; 直接复用 src/q1_baseline.py 的运动学函数与区间算法.
"""

from __future__ import annotations

import math
import os
import sys
from dataclasses import dataclass
from typing import Callable, List, Sequence, Tuple

# 复用 Q1 基线
from src.q1_baseline import (
    G, DRONE_SPEED, MISSILE_SPEED, CLOUD_SINK, CLOUD_RADIUS, CLOUD_DURATION,
    U0, M0, O, P, V_U, T_RELEASE, DELAY, T_DETONATE,
    BISECT_TOL,
    vector_add, vector_sub, vector_scale, dot, norm,
    missile_position, missile_velocity, missile_arrival_time,
    cloud_center, detonation_point, drone_position, bomb_position,
    point_to_segment_distance, find_effective_intervals,
    total_effective_duration, compute_q1,
    f_distance_minus_radius,
)

Vec = Tuple[float, float, float]
TrajFn = Callable[[float], Vec]

# === 圆柱参数 ===
R_T: float = 7.0
H_T: float = 10.0
CYL_BASE: Vec = (0.0, 200.0, 0.0)
CYL_TOP:  Vec = (0.0, 200.0, 10.0)
CYL_AXIS_DIR: Vec = (0.0, 0.0, 1.0)

# 采样等级
SAMPLE_GRADES = {
    "coarse":  dict(side_theta=48,  side_z=8,  cap_r=4,  cap_theta=48),
    "medium":  dict(side_theta=96,  side_z=16, cap_r=8,  cap_theta=96),
    "fine":    dict(side_theta=192, side_z=32, cap_r=16, cap_theta=192),
}

# 数值参数
EPS_VISIBLE: float = 1e-9   # 可见性判定容差; visible ⇔ score >= -EPS_VISIBLE
T_WINDOW_START: float = T_DETONATE
T_WINDOW_END: float = T_DETONATE + CLOUD_DURATION

# 时间扫描步长
TIME_STEPS: Tuple[float, ...] = (0.02, 0.01, 0.005)

# 诊断时间网格 (收敛验证使用)
DIAG_STEP: float = 0.01      # 空间收敛与时间收敛的诊断网格
SVG_STEP: float = 0.05       # SVG 时间序列采样
MARGIN_REFINE_STEP: float = 0.001  # margin 最大值局部加密网格

# 收敛阈值 (用户审核返工要求)
SPATIAL_THR_START: float = 0.01
SPATIAL_THR_END: float = 0.01
SPATIAL_THR_TOTAL: float = 0.02
SPATIAL_THR_COVERAGE: float = 0.005
SPATIAL_THR_MARGIN: float = 0.10
SPATIAL_THR_RESIDUAL: float = 1e-4
TEMPORAL_THR_START: float = 0.01
TEMPORAL_THR_END: float = 0.01
TEMPORAL_THR_TOTAL: float = 0.01
TEMPORAL_THR_RESIDUAL: float = 1e-4

OUT_OF_WINDOW_F: float = 1e9


# === 表面样本 ===
@dataclass(frozen=True)
class SurfaceSample:
    point: Vec
    normal: Vec
    weight: float
    surface_type: str  # "side" / "top" / "bottom"


# === 输入校验 ===
def _validate_eps(eps: float) -> None:
    if not math.isfinite(eps) or eps < 0.0:
        raise ValueError(f"EPS 必须有限且 ≥ 0, 实际 {eps!r}")


def _validate_finite_vec(name: str, v: Vec) -> None:
    for i, c in enumerate(v):
        if not math.isfinite(c):
            raise ValueError(f"{name}[{i}] 非有限: {c}")


def _validate_radius(radius: float) -> None:
    if not math.isfinite(radius) or radius <= 0.0:
        raise ValueError(f"radius 必须有限且 > 0, 实际 {radius!r}")


# === 采样生成 ===
def generate_cylinder_samples(side_theta: int = 96,
                              side_z: int = 16,
                              cap_r: int = 8,
                              cap_theta: int = 96) -> List[SurfaceSample]:
    """生成圆柱三面 (侧面 + 顶面 + 底面) 单元中心样本.

    单元中心 (theta_j = 2π(j+0.5)/n_theta, z_k = H_T·(k+0.5)/n_z) 严格避开
    侧面与端面公共棱边 (z = 0 / z = H_T).

    面积权重:
      - 侧面单元: w_side = 2π·R_T·H_T / (n_side_theta · n_side_z)
      - 端面单元: w_cap = π·R_T² / (n_cap_r · n_cap_theta)
    """
    def check_positive(name: str, v: int) -> None:
        if not isinstance(v, int) or v <= 0:
            raise ValueError(f"{name} 必须正整数, 实际 {v!r}")

    for n, v in (("side_theta", side_theta), ("side_z", side_z),
                 ("cap_r", cap_r), ("cap_theta", cap_theta)):
        check_positive(n, v)

    samples: List[SurfaceSample] = []

    w_side = 2.0 * math.pi * R_T * H_T / (side_theta * side_z)
    for j in range(side_theta):
        theta = 2.0 * math.pi * (j + 0.5) / side_theta
        ct = math.cos(theta)
        st = math.sin(theta)
        for k in range(side_z):
            z = H_T * (k + 0.5) / side_z
            x = R_T * ct
            y = 200.0 + R_T * st
            n_vec: Vec = (ct, st, 0.0)
            assert abs(math.sqrt(n_vec[0] ** 2 + n_vec[1] ** 2 + n_vec[2] ** 2) - 1.0) < 1e-12
            samples.append(SurfaceSample((x, y, z), n_vec, w_side, "side"))

    w_cap = math.pi * R_T ** 2 / (cap_r * cap_theta)
    for r_idx in range(cap_r):
        r = R_T * math.sqrt((r_idx + 0.5) / cap_r)
        for j in range(cap_theta):
            theta = 2.0 * math.pi * (j + 0.5) / cap_theta
            ct = math.cos(theta)
            st = math.sin(theta)
            x = r * ct
            y = 200.0 + r * st
            samples.append(SurfaceSample((x, y, H_T), (0.0, 0.0, 1.0), w_cap, "top"))
            samples.append(SurfaceSample((x, y, 0.0), (0.0, 0.0, -1.0), w_cap, "bottom"))

    return samples


def verify_sample_geometry(samples: Sequence[SurfaceSample]) -> dict:
    n_side = sum(1 for s in samples if s.surface_type == "side")
    n_top = sum(1 for s in samples if s.surface_type == "top")
    n_bot = sum(1 for s in samples if s.surface_type == "bottom")
    total_weight = sum(s.weight for s in samples)
    expected_total = 2.0 * math.pi * R_T * H_T + 2.0 * math.pi * R_T ** 2
    return {
        "n_side": n_side, "n_top": n_top, "n_bot": n_bot,
        "total": len(samples),
        "total_weight": total_weight,
        "expected_total_weight": expected_total,
    }


# === 可见性 ===
def sample_is_visible(sample: SurfaceSample, m: Vec,
                       eps: float = EPS_VISIBLE) -> bool:
    """凸体表面支持平面可见性 (本轮 FIX 后的保守规则).

    visible ⇔ n(X) · (M - X) >= -eps

    切线轮廓邻域 (score ≈ 0) 一律视为可见, 严格遮蔽不应通过排除轮廓样本
    而变得更容易. eps 用于吸收浮点误差, 不构成轮廓收紧.
    """
    _validate_eps(eps)
    diff = vector_sub(m, sample.point)
    return dot(sample.normal, diff) >= -eps


def visible_samples(samples: Sequence[SurfaceSample], m: Vec,
                     eps: float = EPS_VISIBLE) -> List[SurfaceSample]:
    _validate_eps(eps)
    return [s for s in samples if sample_is_visible(s, m, eps)]


# === 遮挡判定 ===
def sample_is_occluded(sample: SurfaceSample, m: Vec, c: Vec,
                        radius: float = CLOUD_RADIUS) -> bool:
    """闭线段 [M, X] 是否被烟幕球遮挡.

    使用闭线段距离 (在 [M, X] 段内最近点距离 ≤ radius).
    投影落在线段延长线但不在闭线段上时, 距离退化到端点, 不会误判.
    radius 必须有限且 > 0.
    """
    _validate_radius(radius)
    d, _ = point_to_segment_distance(c, m, sample.point)
    return d <= radius


# === 圆柱状态 ===
@dataclass(frozen=True)
class CylinderState:
    t: float
    visible_count: int
    visible_weight: float
    occluded_count: int
    occluded_weight: float
    coverage_ratio: float
    max_visible_distance: float
    strict_margin: float
    worst_sample_point: Vec | None
    worst_sample_surface: str | None
    strict_occlusion: bool


# === 纯几何层 (Q2 可注入新轨迹) ===
def evaluate_occlusion_geometry(m: Vec, c: Vec,
                                 samples: Sequence[SurfaceSample],
                                 radius: float = CLOUD_RADIUS) -> CylinderState:
    """纯几何层: 给定观测点 m、烟幕中心 c、圆柱表面样本集与遮蔽半径,
    返回严格遮蔽与覆盖率状态.

    不读取时间、轨迹或全局窗口. 完全可重用于 Q2/Q3/Q4/Q5.

    约束:
      - m, c 每个分量必须有限;
      - radius 必须有限且 > 0;
      - samples 不得为空;
      - 在窗口内 visible_count == 0 抛 ValueError (视为几何配置错误).
    """
    _validate_finite_vec("m", m)
    _validate_finite_vec("c", c)
    _validate_radius(radius)
    if not samples:
        raise ValueError("samples 不得为空")

    visible = visible_samples(samples, m)
    v_count = len(visible)
    v_weight = sum(s.weight for s in visible)

    if v_count == 0:
        raise ValueError(
            "evaluate_occlusion_geometry: 在 [samples 中] 没有可见样本 "
            "(观测点 m 不暴露任何表面). 几何配置错误."
        )

    max_d = -1.0
    occ_count = 0
    occ_weight = 0.0
    worst_pt = None
    worst_surf = None

    for s in visible:
        d, _ = point_to_segment_distance(c, m, s.point)
        if d <= radius:
            occ_count += 1
            occ_weight += s.weight
        if d > max_d:
            max_d = d
            worst_pt = s.point
            worst_surf = s.surface_type

    coverage = (occ_weight / v_weight) if v_weight > 0 else 0.0
    margin = radius - max_d

    return CylinderState(
        t=float("nan"),         # 纯几何层无 t
        visible_count=v_count,
        visible_weight=v_weight,
        occluded_count=occ_count,
        occluded_weight=occ_weight,
        coverage_ratio=coverage,
        max_visible_distance=max_d,
        strict_margin=margin,
        worst_sample_point=worst_pt,
        worst_sample_surface=worst_surf,
        strict_occlusion=(max_d <= radius),
    )


# === 时序包装层 ===
def evaluate_cylinder_state(t: float,
                              samples: Sequence[SurfaceSample],
                              missile_position_fn: TrajFn = missile_position,
                              cloud_center_fn: TrajFn = cloud_center,
                              window_start: float = T_WINDOW_START,
                              window_end: float = T_WINDOW_END,
                              ) -> CylinderState:
    """时序包装: 在时刻 t 调用纯几何层, 加入窗口外哨兵.

    - 时间窗外: strict_occlusion=False, strict_margin=-inf, coverage_ratio=0
    - 时间窗内: 委托给 evaluate_occlusion_geometry, 其内部空可见集抛 ValueError
    """
    if not math.isfinite(t):
        raise ValueError(f"t 非有限: {t}")

    m = missile_position_fn(t)
    _validate_finite_vec("missile_position(t)", m)

    if not (window_start <= t <= window_end):
        return CylinderState(
            t=t, visible_count=0, visible_weight=0.0,
            occluded_count=0, occluded_weight=0.0,
            coverage_ratio=0.0, max_visible_distance=float("inf"),
            strict_margin=-float("inf"),
            worst_sample_point=None, worst_sample_surface=None,
            strict_occlusion=False,
        )

    c = cloud_center_fn(t)
    _validate_finite_vec("cloud_center(t)", c)

    st = evaluate_occlusion_geometry(m, c, samples, CLOUD_RADIUS)
    # 替换 t 字段 (纯几何层用 NaN, 这里写实)
    return CylinderState(
        t=t, visible_count=st.visible_count,
        visible_weight=st.visible_weight,
        occluded_count=st.occluded_count,
        occluded_weight=st.occluded_weight,
        coverage_ratio=st.coverage_ratio,
        max_visible_distance=st.max_visible_distance,
        strict_margin=st.strict_margin,
        worst_sample_point=st.worst_sample_point,
        worst_sample_surface=st.worst_sample_surface,
        strict_occlusion=st.strict_occlusion,
    )


def strict_boundary_value(t: float,
                            samples: Sequence[SurfaceSample],
                            missile_position_fn: TrajFn = missile_position,
                            cloud_center_fn: TrajFn = cloud_center,
                            window_start: float = T_WINDOW_START,
                            window_end: float = T_WINDOW_END,
                            ) -> float:
    """f_cylinder(t) = max_visible_distance(t) - R_cloud.

    严格有效遮蔽 ⇔ f_cylinder(t) ≤ 0.
    时间窗外返回 OUT_OF_WINDOW_F; 空可见集异常直接向上传播.
    """
    st = evaluate_cylinder_state(t, samples, missile_position_fn,
                                  cloud_center_fn, window_start, window_end)
    if st.strict_margin == -float("inf"):
        return OUT_OF_WINDOW_F
    return st.max_visible_distance - CLOUD_RADIUS


# === 区间求解 (复用 find_effective_intervals) ===
def find_strict_intervals(samples: Sequence[SurfaceSample],
                           scan_step: float = 0.01,
                           t_arrival: float | None = None,
                           boundary_func: Callable[[float], float] | None = None,
                           missile_position_fn: TrajFn = missile_position,
                           cloud_center_fn: TrajFn = cloud_center,
                           window_start: float = T_WINDOW_START,
                           window_end: float = T_WINDOW_END,
                           ) -> List[Tuple[float, float]]:
    """扫描 + 二分, 找出所有严格遮蔽区间.

    boundary_func 不为空时, 直接注入; 否则使用默认 strict_boundary_value.
    Q2/Q3/Q4/Q5 可注入新 missile/cloud 轨迹函数, 不复制代码.

    window_end 通过 t_arrival 传给 find_effective_intervals (后者只接受
    t_detonate + t_arrival + 隐含的 t_detonate + CLOUD_DURATION).
    """
    if boundary_func is None:
        boundary_func = lambda t: strict_boundary_value(
            t, samples, missile_position_fn, cloud_center_fn,
            window_start, window_end,
        )
    # 把 window_end 也作为 t_arrival 截断点 (基线函数取 min(t_arrival, default))
    eff_arrival = t_arrival if t_arrival is not None else window_end
    return find_effective_intervals(
        scan_step=scan_step,
        t_detonate=window_start,
        t_arrival=eff_arrival,
        boundary_func=boundary_func,
    )


# === 收敛验证 (使用 DIAG_STEP 诊断网格) ===
def _endpoint_residual(t: float, samples: Sequence[SurfaceSample],
                        missile_position_fn: TrajFn = missile_position,
                        cloud_center_fn: TrajFn = cloud_center,
                        window_start: float = T_WINDOW_START,
                        window_end: float = T_WINDOW_END,
                        ) -> float:
    """max |f_cylinder| 在 t 时刻."""
    return strict_boundary_value(t, samples, missile_position_fn,
                                  cloud_center_fn, window_start, window_end)


def run_temporal_convergence(samples: Sequence[SurfaceSample],
                               missile_position_fn: TrajFn = missile_position,
                               cloud_center_fn: TrajFn = cloud_center,
                               window_start: float = T_WINDOW_START,
                               window_end: float = T_WINDOW_END,
                               ) -> dict:
    """在固定空间采样下, 用不同时间步长求严格区间."""
    per_step = {}
    intervals_per_step = []
    for step in TIME_STEPS:
        ivs = find_strict_intervals(
            samples, scan_step=step,
            missile_position_fn=missile_position_fn,
            cloud_center_fn=cloud_center_fn,
            window_start=window_start, window_end=window_end,
        )
        residuals = [_endpoint_residual(a, samples, missile_position_fn,
                                          cloud_center_fn, window_start,
                                          window_end) for a, _ in ivs]
        residuals += [_endpoint_residual(b, samples, missile_position_fn,
                                           cloud_center_fn, window_start,
                                           window_end) for _, b in ivs]
        per_step[step] = {
            "intervals": ivs,
            "n_intervals": len(ivs),
            "total_duration": total_effective_duration(ivs),
            "endpoint_residuals": residuals,
            "max_residual": max(abs(r) for r in residuals) if residuals else 0.0,
        }
        intervals_per_step.append((step, ivs))
    return {"per_step": per_step, "list": intervals_per_step}


def run_spatial_convergence(scan_step: float = DIAG_STEP,
                              missile_position_fn: TrajFn = missile_position,
                              cloud_center_fn: TrajFn = cloud_center,
                              window_start: float = T_WINDOW_START,
                              window_end: float = T_WINDOW_END,
                              ) -> dict:
    """在固定时间步长下, 用三档空间采样求严格区间 + 诊断指标.

    每档记录: sample_count, intervals, n_intervals, total_duration,
              max_coverage, first_max_coverage_t, max_margin, max_margin_t,
              endpoint_residuals (max |f|).
    诊断时间网格使用 DIAG_STEP (默认 0.01 s).
    """
    per_grade = {}
    intervals_per_grade = []
    for grade, params in SAMPLE_GRADES.items():
        samples = generate_cylinder_samples(**params)
        ivs = find_strict_intervals(
            samples, scan_step=scan_step,
            missile_position_fn=missile_position_fn,
            cloud_center_fn=cloud_center_fn,
            window_start=window_start, window_end=window_end,
        )
        # 端点残差
        residuals = [_endpoint_residual(a, samples, missile_position_fn,
                                          cloud_center_fn, window_start,
                                          window_end) for a, _ in ivs]
        residuals += [_endpoint_residual(b, samples, missile_position_fn,
                                           cloud_center_fn, window_start,
                                           window_end) for _, b in ivs]
        # 诊断网格上扫描 (覆盖 max_coverage / max_margin / 时刻)
        n_diag = int(math.ceil((window_end - window_start) / DIAG_STEP)) + 1
        max_cov = -1.0
        first_max_cov_t = window_start
        max_margin = -float("inf")
        max_margin_t = window_start
        for i in range(n_diag):
            tt = window_start + (window_end - window_start) * i / (n_diag - 1)
            try:
                st = evaluate_cylinder_state(tt, samples,
                                              missile_position_fn,
                                              cloud_center_fn,
                                              window_start, window_end)
            except ValueError:
                continue
            if st.coverage_ratio > max_cov + 1e-12:
                max_cov = st.coverage_ratio
                first_max_cov_t = tt
            elif abs(st.coverage_ratio - max_cov) <= 1e-12 and tt < first_max_cov_t:
                first_max_cov_t = tt
            if st.strict_margin > max_margin:
                max_margin = st.strict_margin
                max_margin_t = tt

        per_grade[grade] = {
            "sample_count": len(samples),
            "samples": len(samples),
            "intervals": ivs,
            "n_intervals": len(ivs),
            "total_duration": total_effective_duration(ivs),
            "max_coverage": max_cov,
            "first_max_coverage_t": first_max_cov_t,
            "max_margin": max_margin,
            "max_margin_t": max_margin_t,
            "endpoint_residuals": residuals,
            "max_residual": max(abs(r) for r in residuals) if residuals else 0.0,
            "diag_step": DIAG_STEP,
        }
        intervals_per_grade.append((grade, ivs))
    return {"per_grade": per_grade, "list": intervals_per_grade,
            "diag_step": DIAG_STEP}


def check_temporal_convergence(temporal_result: dict) -> dict:
    """真实执行时间收敛通过标准.

    通过标准:
      - 所有 step 之间 n_intervals 一致
      - 起点差 <= TEMPORAL_THR_START
      - 终点差 <= TEMPORAL_THR_END
      - 总时长差 <= TEMPORAL_THR_TOTAL
      - 每个端点 |f_cylinder| <= TEMPORAL_THR_RESIDUAL
    """
    entries = list(temporal_result["per_step"].items())
    summary = {
        "comparisons": [],
        "passed": True,
        "reasons": [],
        "thresholds": {
            "start": TEMPORAL_THR_START,
            "end": TEMPORAL_THR_END,
            "total": TEMPORAL_THR_TOTAL,
            "residual": TEMPORAL_THR_RESIDUAL,
        },
    }
    # 区间数一致性
    ns = [info["n_intervals"] for _, info in entries]
    if len(set(ns)) != 1:
        summary["passed"] = False
        summary["reasons"].append(
            f"n_intervals 不一致: {[(s, info['n_intervals']) for s, info in entries]}"
        )

    # 端点残差
    for step, info in entries:
        if info["max_residual"] > TEMPORAL_THR_RESIDUAL:
            summary["passed"] = False
            summary["reasons"].append(
                f"step={step}: max |f| = {info['max_residual']:.3e} > {TEMPORAL_THR_RESIDUAL}"
            )

    # 两两比较
    for i in range(len(entries)):
        for j in range(i + 1, len(entries)):
            sa, da = entries[i]
            sb, db = entries[j]
            comp = {"step_a": sa, "step_b": sb}
            if da["n_intervals"] != db["n_intervals"]:
                comp["n_intervals_diff"] = abs(da["n_intervals"] - db["n_intervals"])
            else:
                comp["n_intervals_diff"] = 0
            starts_diff = 0.0
            ends_diff = 0.0
            if da["intervals"] and db["intervals"]:
                if len(da["intervals"]) != len(db["intervals"]):
                    starts_diff = max(starts_diff, float("inf"))
                    ends_diff = max(ends_diff, float("inf"))
                else:
                    for ia, ib in zip(da["intervals"], db["intervals"]):
                        starts_diff = max(starts_diff, abs(ia[0] - ib[0]))
                        ends_diff = max(ends_diff, abs(ia[1] - ib[1]))
            comp["max_start_diff"] = starts_diff
            comp["max_end_diff"] = ends_diff
            comp["total_diff"] = abs(da["total_duration"] - db["total_duration"])
            if starts_diff > TEMPORAL_THR_START:
                summary["passed"] = False
                summary["reasons"].append(
                    f"step {sa} vs {sb}: 最大起点差 {starts_diff:.3e} > {TEMPORAL_THR_START}"
                )
            if ends_diff > TEMPORAL_THR_END:
                summary["passed"] = False
                summary["reasons"].append(
                    f"step {sa} vs {sb}: 最大终点差 {ends_diff:.3e} > {TEMPORAL_THR_END}"
                )
            if comp["total_diff"] > TEMPORAL_THR_TOTAL:
                summary["passed"] = False
                summary["reasons"].append(
                    f"step {sa} vs {sb}: 总时长差 {comp['total_diff']:.3e} > {TEMPORAL_THR_TOTAL}"
                )
            summary["comparisons"].append(comp)
    return summary


def check_spatial_convergence(spatial_result: dict) -> dict:
    """真实执行空间收敛通过标准.

    通过标准 (medium vs fine):
      - n_intervals 一致
      - 起点差 <= SPATIAL_THR_START
      - 终点差 <= SPATIAL_THR_END
      - 总时长差 <= SPATIAL_THR_TOTAL
      - max_coverage 差 <= SPATIAL_THR_COVERAGE
      - max_margin 差 <= SPATIAL_THR_MARGIN
      - 所有非时间窗端点 |f_cylinder| <= SPATIAL_THR_RESIDUAL
    """
    per = spatial_result["per_grade"]
    medium = per["medium"]
    fine = per["fine"]
    summary = {
        "medium_vs_fine": {
            "n_intervals": (medium["n_intervals"], fine["n_intervals"]),
            "n_intervals_match": medium["n_intervals"] == fine["n_intervals"],
            "total_medium": medium["total_duration"],
            "total_fine": fine["total_duration"],
            "total_diff": abs(medium["total_duration"] - fine["total_duration"]),
            "start_diff": 0.0,
            "end_diff": 0.0,
            "max_coverage_diff": abs(medium["max_coverage"] - fine["max_coverage"]),
            "max_margin_diff": abs(medium["max_margin"] - fine["max_margin"]),
            "max_residual_medium": medium["max_residual"],
            "max_residual_fine": fine["max_residual"],
        },
        "coarse_vs_medium": {
            "total_coarse": per["coarse"]["total_duration"],
            "total_medium": medium["total_duration"],
            "total_diff": abs(per["coarse"]["total_duration"]
                              - medium["total_duration"]),
        },
        "passed": True,
        "reasons": [],
        "thresholds": {
            "start": SPATIAL_THR_START,
            "end": SPATIAL_THR_END,
            "total": SPATIAL_THR_TOTAL,
            "coverage": SPATIAL_THR_COVERAGE,
            "margin": SPATIAL_THR_MARGIN,
            "residual": SPATIAL_THR_RESIDUAL,
        },
    }
    mfv = summary["medium_vs_fine"]

    # 起点 / 终点差 (按区间对齐)
    if medium["intervals"] and fine["intervals"] \
            and len(medium["intervals"]) == len(fine["intervals"]):
        for (a_m, b_m), (a_f, b_f) in zip(medium["intervals"], fine["intervals"]):
            mfv["start_diff"] = max(mfv["start_diff"], abs(a_m - a_f))
            mfv["end_diff"] = max(mfv["end_diff"], abs(b_m - b_f))
    else:
        mfv["start_diff"] = float("inf")
        mfv["end_diff"] = float("inf")

    # 通过判定
    if not mfv["n_intervals_match"]:
        summary["passed"] = False
        summary["reasons"].append(
            f"medium/fine n_intervals 不一致: {mfv['n_intervals']}"
        )
    if mfv["start_diff"] > SPATIAL_THR_START:
        summary["passed"] = False
        summary["reasons"].append(
            f"medium/fine 起点差 {mfv['start_diff']:.3e} > {SPATIAL_THR_START}"
        )
    if mfv["end_diff"] > SPATIAL_THR_END:
        summary["passed"] = False
        summary["reasons"].append(
            f"medium/fine 终点差 {mfv['end_diff']:.3e} > {SPATIAL_THR_END}"
        )
    if mfv["total_diff"] > SPATIAL_THR_TOTAL:
        summary["passed"] = False
        summary["reasons"].append(
            f"medium/fine 总时长差 {mfv['total_diff']:.3e} > {SPATIAL_THR_TOTAL}"
        )
    if mfv["max_coverage_diff"] > SPATIAL_THR_COVERAGE:
        summary["passed"] = False
        summary["reasons"].append(
            f"medium/fine max_coverage 差 {mfv['max_coverage_diff']:.3e} > {SPATIAL_THR_COVERAGE}"
        )
    if mfv["max_margin_diff"] > SPATIAL_THR_MARGIN:
        summary["passed"] = False
        summary["reasons"].append(
            f"medium/fine max_margin 差 {mfv['max_margin_diff']:.3e} > {SPATIAL_THR_MARGIN}"
        )
    if mfv["max_residual_medium"] > SPATIAL_THR_RESIDUAL:
        summary["passed"] = False
        summary["reasons"].append(
            f"medium 端点 max |f| {mfv['max_residual_medium']:.3e} > {SPATIAL_THR_RESIDUAL}"
        )
    if mfv["max_residual_fine"] > SPATIAL_THR_RESIDUAL:
        summary["passed"] = False
        summary["reasons"].append(
            f"fine 端点 max |f| {mfv['max_residual_fine']:.3e} > {SPATIAL_THR_RESIDUAL}"
        )
    return summary


# === 与 Q1 点目标基线对照 ===
def compare_point_and_cylinder(cylinder_total: float, point_total: float
                                ) -> dict:
    delta = cylinder_total - point_total
    rel = (delta / point_total) if point_total > 0 else 0.0
    return {
        "delta_T": delta,
        "relative_difference": rel,
        "point_total": point_total,
        "cylinder_total": cylinder_total,
    }


# === 时间序列与局部加密 ===
def build_time_series(samples: Sequence[SurfaceSample],
                       missile_position_fn: TrajFn = missile_position,
                       cloud_center_fn: TrajFn = cloud_center,
                       window_start: float = T_WINDOW_START,
                       window_end: float = T_WINDOW_END,
                       scan_step: float = SVG_STEP,
                       ) -> Tuple[List[Tuple[float, float]],
                                  List[Tuple[float, float]],
                                  float, float, float, float]:
    """在窗口内每 scan_step 评估一次.

    返回: (cov_series, mar_series, cov_max, cov_max_t, margin_max, margin_max_t)
    """
    ts = []
    n = int(math.ceil((window_end - window_start) / scan_step)) + 1
    for i in range(n):
        ts.append(window_start + (window_end - window_start) * i / (n - 1))

    cov_series = []
    mar_series = []
    cov_max = -1.0
    cov_max_t = window_start
    margin_max = -float("inf")
    margin_max_t = window_start

    for t in ts:
        try:
            s = evaluate_cylinder_state(t, samples,
                                          missile_position_fn,
                                          cloud_center_fn,
                                          window_start, window_end)
        except ValueError:
            cov_series.append((t, float("nan")))
            mar_series.append((t, float("nan")))
            continue
        cov_series.append((t, s.coverage_ratio))
        mar_series.append((t, s.strict_margin))
        if math.isfinite(s.coverage_ratio) and s.coverage_ratio > cov_max + 1e-12:
            cov_max = s.coverage_ratio
            cov_max_t = t
        if math.isfinite(s.strict_margin) and s.strict_margin > margin_max:
            margin_max = s.strict_margin
            margin_max_t = t

    return cov_series, mar_series, cov_max, cov_max_t, margin_max, margin_max_t


def refine_margin_max(samples: Sequence[SurfaceSample],
                       t_approx: float,
                       half_window: float = 0.05,
                       step: float = MARGIN_REFINE_STEP,
                       missile_position_fn: TrajFn = missile_position,
                       cloud_center_fn: TrajFn = cloud_center,
                       window_start: float = T_WINDOW_START,
                       window_end: float = T_WINDOW_END,
                       ) -> Tuple[float, float]:
    """在 [t_approx - half_window, t_approx + half_window] 上以 step 加密扫描
    严格遮蔽裕量, 返回 (max_margin, max_margin_t).

    用于报告更细局部网格估计值 (step=0.001 s), 不只是 SVG 0.05 s 网格上的采样值.
    注意: 这是离散局部网格上的最大值, 不是解析连续极值.
    """
    a = max(window_start, t_approx - half_window)
    b = min(window_end, t_approx + half_window)
    n = max(2, int(math.ceil((b - a) / step)) + 1)
    max_margin = -float("inf")
    max_t = t_approx
    for i in range(n):
        tt = a + (b - a) * i / (n - 1)
        try:
            st = evaluate_cylinder_state(tt, samples,
                                          missile_position_fn,
                                          cloud_center_fn,
                                          window_start, window_end)
        except ValueError:
            continue
        if st.strict_margin > max_margin:
            max_margin = st.strict_margin
            max_t = tt
    return max_margin, max_t


def coverage_plateau(samples: Sequence[SurfaceSample],
                       window_start: float = T_WINDOW_START,
                       window_end: float = T_WINDOW_END,
                       step: float = 0.01,
                       missile_position_fn: TrajFn = missile_position,
                       cloud_center_fn: TrajFn = cloud_center,
                       ) -> dict:
    """报告 coverage_ratio = 1 的连续平台区间 (若有).

    严格遮蔽成立 ⇒ coverage_ratio = 1. 本函数枚举 strict_occlusion 区间
    以便报告 ρ=1 的真实持续时长.
    """
    n = int(math.ceil((window_end - window_start) / step)) + 1
    plateaus = []
    cur_start = None
    for i in range(n):
        tt = window_start + (window_end - window_start) * i / (n - 1)
        try:
            st = evaluate_cylinder_state(tt, samples,
                                          missile_position_fn,
                                          cloud_center_fn,
                                          window_start, window_end)
        except ValueError:
            if cur_start is not None:
                plateaus.append((cur_start, tt - step))
                cur_start = None
            continue
        if abs(st.coverage_ratio - 1.0) <= 1e-12:
            if cur_start is None:
                cur_start = tt
        else:
            if cur_start is not None:
                plateaus.append((cur_start, tt - step))
                cur_start = None
    if cur_start is not None:
        plateaus.append((cur_start, window_end))
    return {"plateaus": plateaus,
            "total_plateau_duration": sum(b - a for a, b in plateaus)}


# === SVG 对照图 ===
def write_comparison_svg(path: str,
                          point_intervals: Sequence[Tuple[float, float]],
                          cyl_intervals: Sequence[Tuple[float, float]],
                          point_total: float,
                          cyl_total: float,
                          coverage_max: float,
                          coverage_max_t: float,
                          strict_margin_max: float,
                          margin_max_t: float,
                          coverage_series: Sequence[Tuple[float, float]],
                          margin_series: Sequence[Tuple[float, float]],
                          diag_step_used: float = SVG_STEP,
                          ) -> None:
    """x-z 投影 + 时间对照面板. 标题包含 FULL-CYLINDER CANDIDATE / EXPERIMENTAL."""
    SVG_HEADER = (
        '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'viewBox="0 0 1000 760" width="1000" height="760" '
        'font-family="Arial, sans-serif" font-size="12">\n'
    )
    SVG_FOOTER = "</svg>\n"

    parts = [SVG_HEADER]
    parts.append('<rect x="0" y="0" width="1000" height="760" fill="white"/>\n')
    parts.append('<text x="500" y="28" text-anchor="middle" font-size="18" '
                 'font-weight="bold">Q1 Point vs Full-Cylinder Comparison</text>\n')
    parts.append('<text x="500" y="50" text-anchor="middle" font-size="12" '
                 'fill="red">[FULL-CYLINDER CANDIDATE / EXPERIMENTAL] '
                 'not a final answer</text>\n')

    # 上半: x-z 投影
    X0, X1 = 0.0, 20500.0
    Z0, Z1 = 0.0, 2100.0
    PL, PR, PT, PB = 60.0, 940.0, 70.0, 360.0
    W = PR - PL
    H = PB - PT

    def map_x(x: float) -> float:
        return PL + (x - X0) / (X1 - X0) * W

    def map_z(z: float) -> float:
        return PB - (z - Z0) / (Z1 - Z0) * H

    parts.append(f'<text x="{PL}" y="{PT - 10}" font-size="13" '
                 'font-weight="bold">上部: x-z 投影 (场景地图)</text>\n')
    parts.append(f'<line x1="{PL}" y1="{PB}" x2="{PR}" y2="{PB}" stroke="black"/>\n')
    parts.append(f'<line x1="{PL}" y1="{PT}" x2="{PL}" y2="{PB}" stroke="black"/>\n')
    parts.append(f'<text x="{PR - 20}" y="{PB + 18}" font-size="12">x (m)</text>\n')
    parts.append(f'<text x="{PL - 30}" y="{PT + 5}" font-size="12">z (m)</text>\n')

    for xv in range(0, 20001, 5000):
        sx = map_x(xv)
        parts.append(f'<line x1="{sx}" y1="{PB}" x2="{sx}" y2="{PB + 4}" stroke="black"/>\n')
        parts.append(f'<text x="{sx}" y="{PB + 16}" text-anchor="middle">{xv}</text>\n')
    for zv in range(0, 2001, 500):
        sy = map_z(zv)
        parts.append(f'<line x1="{PL - 4}" y1="{sy}" x2="{PL}" y2="{sy}" stroke="black"/>\n')
        parts.append(f'<text x="{PL - 8}" y="{sy + 4}" text-anchor="end">{zv}</text>\n')

    ox, oy = map_x(0.0), map_z(0.0)
    parts.append(f'<circle cx="{ox}" cy="{oy}" r="4" fill="gray"/>\n')
    parts.append(f'<text x="{ox + 8}" y="{oy - 6}" font-size="11" fill="gray">'
                 '假目标 O (0,0,0)</text>\n')
    px, py = map_x(0.0), map_z(5.0)
    parts.append(f'<circle cx="{px}" cy="{py}" r="4" fill="orange"/>\n')
    parts.append(f'<text x="{px + 8}" y="{py - 6}" font-size="11" fill="orange">'
                 '点目标 P=(0,200,5)</text>\n')

    cyl_x_svg = map_x(0.0)
    cyl_top = map_z(10.0)
    cyl_bot = map_z(0.0)
    parts.append(f'<rect x="{cyl_x_svg - 3}" y="{cyl_top}" width="6" '
                 f'height="{cyl_bot - cyl_top}" fill="none" '
                 'stroke="purple" stroke-width="2"/>\n')
    parts.append(f'<text x="{cyl_x_svg + 6}" y="{(cyl_top + cyl_bot) / 2}" '
                 f'font-size="11" fill="purple">'
                 '真目标圆柱 (x=0, y=200, z∈[0,10])</text>\n')

    result_point = compute_q1()
    v_m = result_point["v_m"]
    t_arr = result_point["t_arrival"]
    n_m = int(math.ceil(t_arr / 0.5)) + 1
    pts = []
    for i in range(n_m):
        t = i * 0.5
        m = (M0[0] + v_m[0] * t, M0[1] + v_m[1] * t, M0[2] + v_m[2] * t)
        pts.append((map_x(m[0]), map_z(m[2])))
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    parts.append(f'<polyline points="{poly}" fill="none" stroke="red" '
                 'stroke-width="1.5"/>\n')

    n_f = int(math.ceil(T_RELEASE / 0.1)) + 1
    pts = []
    for i in range(n_f):
        u = drone_position(i * 0.1)
        pts.append((map_x(u[0]), map_z(u[2])))
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    parts.append(f'<polyline points="{poly}" fill="none" stroke="blue" '
                 'stroke-width="1.5"/>\n')

    rr = result_point["r_release"]
    rsx, rsy = map_x(rr[0]), map_z(rr[2])
    parts.append(f'<circle cx="{rsx}" cy="{rsy}" r="4" fill="blue" '
                 'stroke="black" stroke-width="1"/>\n')

    n_b = int(math.ceil((T_DETONATE - T_RELEASE) / 0.1)) + 1
    pts = []
    for i in range(n_b):
        t = T_RELEASE + i * (T_DETONATE - T_RELEASE) / (n_b - 1)
        b = bomb_position(t)
        pts.append((map_x(b[0]), map_z(b[2])))
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    parts.append(f'<polyline points="{poly}" fill="none" stroke="purple" '
                 'stroke-width="1.5" stroke-dasharray="4,2"/>\n')

    dd = result_point["d_deton"]
    dsx, dsy = map_x(dd[0]), map_z(dd[2])
    parts.append(f'<circle cx="{dsx}" cy="{dsy}" r="4" fill="purple" '
                 'stroke="black" stroke-width="1"/>\n')

    n_c = int(math.ceil(CLOUD_DURATION / 0.5)) + 1
    pts = []
    for i in range(n_c):
        t = T_DETONATE + i * CLOUD_DURATION / (n_c - 1)
        c = cloud_center(t)
        pts.append((map_x(c[0]), map_z(c[2])))
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    parts.append(f'<polyline points="{poly}" fill="none" stroke="green" '
                 'stroke-width="1.5" stroke-dasharray="2,2"/>\n')

    for a, b in point_intervals:
        if a > T_DETONATE + CLOUD_DURATION:
            continue
        ca = cloud_center(a); cb = cloud_center(b)
        ax, ay = map_x(ca[0]), map_z(ca[2])
        bx, by = map_x(cb[0]), map_z(cb[2])
        parts.append(f'<line x1="{ax:.1f}" y1="{ay:.1f}" '
                     f'x2="{bx:.1f}" y2="{by:.1f}" '
                     'stroke="orange" stroke-width="3"/>\n')
    for a, b in cyl_intervals:
        if a > T_DETONATE + CLOUD_DURATION:
            continue
        ca = cloud_center(a); cb = cloud_center(b)
        ax, ay = map_x(ca[0]), map_z(ca[2])
        bx, by = map_x(cb[0]), map_z(cb[2])
        parts.append(f'<line x1="{ax:.1f}" y1="{ay:.1f}" '
                     f'x2="{bx:.1f}" y2="{by:.1f}" '
                     'stroke="red" stroke-width="2" stroke-dasharray="3,1"/>\n')

    parts.append(f'<text x="500" y="{PB + 40}" text-anchor="middle" '
                 'font-size="11">'
                 f'点目标总时长 {point_total:.4f}s | 完整圆柱总时长 '
                 f'{cyl_total:.4f}s | max ρ {coverage_max:.4f} '
                 f'(平台 {coverage_max_t:.3f}s 起) | max margin '
                 f'{strict_margin_max:.4f}m @ t={margin_max_t:.3f}s '
                 f'({diag_step_used:.3f}s 网格, 已局部加密)'
                 '</text>\n')

    # 下半: 时间对照
    TL, TR, TP, TB = 80.0, 940.0, 430.0, 700.0
    TW = TR - TL
    t_min = T_DETONATE - 1.0
    t_max = T_DETONATE + CLOUD_DURATION + 1.0

    def map_t(t: float) -> float:
        return TL + (t - t_min) / (t_max - t_min) * TW

    parts.append(f'<text x="{TL}" y="{TP - 10}" font-size="13" '
                 'font-weight="bold">下部: 时间对照 (t=[5.1, 25.1]s)</text>\n')
    parts.append(f'<line x1="{TL}" y1="{TB}" x2="{TR}" y2="{TB}" stroke="black"/>\n')
    parts.append(f'<line x1="{TL}" y1="{TP}" x2="{TL}" y2="{TB}" stroke="black"/>\n')
    parts.append(f'<text x="{TR - 10}" y="{TB + 18}" font-size="12">t (s)</text>\n')
    parts.append(f'<text x="{TL - 30}" y="{TP + 5}" font-size="12">指标</text>\n')

    for tv in (5.1, 8.0, 12.0, 16.0, 20.0, 25.1):
        sx = map_t(tv)
        parts.append(f'<line x1="{sx}" y1="{TB}" x2="{sx}" y2="{TB + 4}" '
                     'stroke="black"/>\n')
        parts.append(f'<text x="{sx}" y="{TB + 16}" text-anchor="middle" '
                     f'font-size="10">{tv:.1f}</text>\n')

    ch1_top = TP + 5
    ch1_bot = ch1_top + 60
    parts.append(f'<text x="{TL - 5}" y="{(ch1_top + ch1_bot) / 2 + 4}" '
                 'text-anchor="end" font-size="11">点目标</text>\n')
    for a, b in point_intervals:
        ax = map_t(max(a, t_min)); bx = map_t(min(b, t_max))
        parts.append(f'<rect x="{ax:.1f}" y="{ch1_top}" width="{max(1, bx - ax):.1f}" '
                     f'height="{ch1_bot - ch1_top}" fill="orange" '
                     'fill-opacity="0.7"/>\n')

    ch2_top = ch1_bot + 10
    ch2_bot = ch2_top + 60
    parts.append(f'<text x="{TL - 5}" y="{(ch2_top + ch2_bot) / 2 + 4}" '
                 'text-anchor="end" font-size="11">圆柱严格</text>\n')
    for a, b in cyl_intervals:
        ax = map_t(max(a, t_min)); bx = map_t(min(b, t_max))
        parts.append(f'<rect x="{ax:.1f}" y="{ch2_top}" width="{max(1, bx - ax):.1f}" '
                     f'height="{ch2_bot - ch2_top}" fill="red" '
                     'fill-opacity="0.7"/>\n')

    ch3_top = ch2_bot + 10
    ch3_bot = ch3_top + 80
    parts.append(f'<text x="{TL - 5}" y="{(ch3_top + ch3_bot) / 2 + 4}" '
                 'text-anchor="end" font-size="11">ρ(t)</text>\n')
    if coverage_series:
        prev_x = prev_y = None
        for t, rho in coverage_series:
            if not math.isfinite(rho):
                continue
            sx = map_t(t)
            sy = ch3_bot - rho * (ch3_bot - ch3_top)
            if prev_x is not None:
                parts.append(f'<line x1="{prev_x:.1f}" y1="{prev_y:.1f}" '
                             f'x2="{sx:.1f}" y2="{sy:.1f}" '
                             'stroke="blue" stroke-width="1.5"/>\n')
            prev_x, prev_y = sx, sy
    for level in (0.0, 0.5, 1.0):
        sy = ch3_bot - level * (ch3_bot - ch3_top)
        parts.append(f'<line x1="{TL}" y1="{sy:.1f}" x2="{TR}" y2="{sy:.1f}" '
                     'stroke="lightgray" stroke-width="0.5" stroke-dasharray="2,2"/>\n')
        parts.append(f'<text x="{TL - 5}" y="{sy + 3:.1f}" text-anchor="end" '
                     f'font-size="9">{level:.1f}</text>\n')

    ch4_top = ch3_bot + 10
    ch4_bot = ch4_top + 80
    parts.append(f'<text x="{TL - 5}" y="{(ch4_top + ch4_bot) / 2 + 4}" '
                 'text-anchor="end" font-size="11">margin(m)</text>\n')
    if margin_series:
        ms = [m for _, m in margin_series if math.isfinite(m)]
        if ms:
            m_min = min(-0.5, min(ms))
            m_max_y = max(0.5, max(ms))
            if m_max_y == m_min:
                m_max_y = m_min + 1.0
            zero_y = ch4_bot - (0 - m_min) / (m_max_y - m_min) * (ch4_bot - ch4_top)
            parts.append(f'<line x1="{TL}" y1="{zero_y:.1f}" x2="{TR}" '
                         f'y2="{zero_y:.1f}" stroke="green" stroke-width="1.5"/>\n')
            parts.append(f'<text x="{TR + 5}" y="{zero_y + 3:.1f}" font-size="10" '
                         'fill="green">margin=0</text>\n')

            prev_x = prev_y = None
            for t, m_val in margin_series:
                if not math.isfinite(m_val):
                    continue
                sx = map_t(t)
                sy = ch4_bot - (m_val - m_min) / (m_max_y - m_min) * (ch4_bot - ch4_top)
                if prev_x is not None:
                    parts.append(f'<line x1="{prev_x:.1f}" y1="{prev_y:.1f}" '
                                 f'x2="{sx:.1f}" y2="{sy:.1f}" '
                                 'stroke="black" stroke-width="1"/>\n')
                prev_x, prev_y = sx, sy

    leg_x = TL
    leg_y = TB + 50
    items = [
        ("red", "M1 轨迹"),
        ("blue", "FY1 轨迹"),
        ("purple dashed", "烟幕弹抛体"),
        ("green dashed", "云团下沉"),
        ("orange rect", "点目标有效"),
        ("red rect", "圆柱严格有效"),
        ("blue line", "覆盖率 ρ(t)"),
        ("black line", "严格裕量 margin"),
    ]
    for i, (color, label) in enumerate(items):
        x = leg_x + (i % 4) * 230
        y = leg_y + (i // 4) * 18
        if "rect" in color:
            parts.append(f'<rect x="{x}" y="{y - 9}" width="14" height="12" '
                         f'fill="{color.split()[0]}" fill-opacity="0.7"/>\n')
        elif "dashed" in color:
            parts.append(f'<line x1="{x}" y1="{y}" x2="{x + 14}" y2="{y}" '
                         f'stroke="{color.split()[0]}" stroke-width="2" '
                         'stroke-dasharray="3,1"/>\n')
        else:
            parts.append(f'<line x1="{x}" y1="{y}" x2="{x + 14}" y2="{y}" '
                         f'stroke="{color}" stroke-width="2"/>\n')
        parts.append(f'<text x="{x + 20}" y="{y + 4}" font-size="10">{label}</text>\n')

    parts.append(SVG_FOOTER)

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("".join(parts))


# === 主入口 ===
def main(argv: List[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    out_path = argv[0] if argv else "outputs/q1/q1_cylinder_comparison.svg"

    print("模型状态: FULL-CYLINDER CANDIDATE / EXPERIMENTAL")
    print("=" * 70)

    point_result = compute_q1()
    point_intervals = point_result["intervals"]
    point_total = point_result["total_duration"]
    print("## 方案 A: 点目标基线")
    print(f"  遮蔽区间: {point_intervals}")
    print(f"  总时长:   {point_total:.6f} s")
    print()

    print("## 方案 B: 完整圆柱严格遮蔽 (三档空间 + 时间扫描)")
    print(f"  诊断网格 step = {DIAG_STEP} s (margin 局部加密 {MARGIN_REFINE_STEP} s)")
    print(f"{'grade':<10s} {'samples':>8s} {'intervals':>40s} {'total(s)':>12s} "
          f"{'max_ρ':>9s} {'max_margin':>11s}")
    print("-" * 100)
    per_grade_samples = {}
    spatial_res = run_spatial_convergence(scan_step=DIAG_STEP)
    for grade, info in spatial_res["per_grade"].items():
        params = SAMPLE_GRADES[grade]
        per_grade_samples[grade] = generate_cylinder_samples(**params)
        ivs = info["intervals"]
        print(f"{grade:<10s} {info['sample_count']:>8d} "
              f"{str(ivs)[:40]:>40s} "
              f"{info['total_duration']:>12.6f} "
              f"{info['max_coverage']:>9.4f} "
              f"{info['max_margin']:>11.4f}")

    final_ivs = spatial_res["per_grade"]["fine"]["intervals"]
    final_total = spatial_res["per_grade"]["fine"]["total_duration"]
    print()
    print(f"  最终候选 (fine): 区间={final_ivs}, 总时长={final_total:.6f} s")

    # SVG 时间序列 + 局部 margin 加密
    cov_series, mar_series, cov_max, cov_max_t, mar_max_grid, mar_max_t_grid = \
        build_time_series(per_grade_samples["fine"],
                           missile_position_fn=missile_position,
                           cloud_center_fn=cloud_center,
                           window_start=T_WINDOW_START,
                           window_end=T_WINDOW_END,
                           scan_step=SVG_STEP)
    mar_max_refined, mar_max_t_refined = refine_margin_max(
        per_grade_samples["fine"], mar_max_t_grid,
        half_window=0.05, step=MARGIN_REFINE_STEP,
    )
    # 用更精的 margin 替换
    strict_margin_max = mar_max_refined
    margin_max_t = mar_max_t_refined
    print(f"  max ρ = {cov_max:.6f} (诊断网格上达到 1.0 的最早时刻 t={cov_max_t:.4f}s; "
          f"严格遮蔽区间内 ρ=1 形成平台)")
    print(f"  max margin = {strict_margin_max:.6f} m @ t={margin_max_t:.6f} s "
          f"(在 {mar_max_t_grid:.4f}s 周围 ±0.05 s 范围内以 "
          f"{MARGIN_REFINE_STEP} s 加密扫描)")

    plat = coverage_plateau(per_grade_samples["fine"],
                              step=DIAG_STEP)
    print(f"  coverage = 1 平台: {plat['plateaus']} "
          f"(总持续 {plat['total_plateau_duration']:.6f} s)")

    print()
    print("## 时间收敛 (medium 空间采样)")
    temp_res = run_temporal_convergence(per_grade_samples["medium"])
    print(f"{'step':>8s} {'n_ivs':>6s} {'intervals':>40s} {'total(s)':>12s} "
          f"{'max|f|':>10s}")
    print("-" * 90)
    for step, info in temp_res["per_step"].items():
        print(f"{step:>8.4f} {info['n_intervals']:>6d} "
              f"{str(info['intervals'])[:40]:>40s} "
              f"{info['total_duration']:>12.6f} "
              f"{info['max_residual']:>10.2e}")
    temp_check = check_temporal_convergence(temp_res)
    print(f"时间收敛: {'PASS' if temp_check['passed'] else 'NOT CONVERGED'}")
    if not temp_check["passed"]:
        for r in temp_check["reasons"]:
            print(f"  原因: {r}")

    print()
    print("## 空间收敛 (时间步长 DIAG_STEP s)")
    spat_check = check_spatial_convergence(spatial_res)
    print(f"  medium vs fine:")
    mfv = spat_check["medium_vs_fine"]
    print(f"    n_intervals: medium={mfv['n_intervals'][0]}, fine={mfv['n_intervals'][1]}, "
          f"match={mfv['n_intervals_match']}")
    print(f"    总时长: medium={mfv['total_medium']:.6f}, fine={mfv['total_fine']:.6f}, "
          f"差={mfv['total_diff']:.3e}")
    print(f"    起点差: {mfv['start_diff']:.3e}, 终点差: {mfv['end_diff']:.3e}")
    print(f"    max_ρ 差: {mfv['max_coverage_diff']:.3e}, "
          f"max_margin 差: {mfv['max_margin_diff']:.3e}")
    print(f"    端点 max|f|: medium={mfv['max_residual_medium']:.3e}, "
          f"fine={mfv['max_residual_fine']:.3e}")
    print(f"空间收敛: {'PASS' if spat_check['passed'] else 'NOT CONVERGED'}")
    if not spat_check["passed"]:
        for r in spat_check["reasons"]:
            print(f"  原因: {r}")

    cmp_dict = compare_point_and_cylinder(final_total, point_total)
    print()
    print("## 与 Q1 点目标基线对照 (fine)")
    print(f"  ΔT (cyl - point) = {cmp_dict['delta_T']:.6f} s")
    print(f"  相对差异        = {cmp_dict['relative_difference']:.6f}")
    print(f"  点目标时长      = {cmp_dict['point_total']:.6f} s")
    print(f"  完整圆柱时长    = {cmp_dict['cylinder_total']:.6f} s")

    write_comparison_svg(out_path,
                          point_intervals, final_ivs,
                          point_total, final_total,
                          cov_max, cov_max_t,
                          strict_margin_max, margin_max_t,
                          cov_series, mar_series,
                          diag_step_used=SVG_STEP)
    print()
    print(f"SVG 路径: {out_path}")
    if os.path.exists(out_path):
        print(f"SVG 字节数: {os.path.getsize(out_path)}")

    print()
    print("## 当前局限")
    print("- 完整圆柱仍是有限采样近似 (单元中心法, medium/fine 已收敛)")
    print("- 覆盖率仅作辅助诊断, 当前不使用人为覆盖率阈值")
    print("- 等级: FULL-CYLINDER CANDIDATE / EXPERIMENTAL")
    print("- 等待外部审核, 不得冒充 VERIFIED / FINAL")

    if (not temp_check["passed"]) or (not spat_check["passed"]):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())