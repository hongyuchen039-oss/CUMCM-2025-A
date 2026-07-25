"""Q1 完整圆柱遮蔽判定冻结与 Q1 对照 (FULL-CYLINDER CANDIDATE / EXPERIMENTAL)

按 FACTS.md §11 与本轮 MODEL.md"完整圆柱遮蔽正式候选"章节定义:

- 真目标 K = {(x,y,z) | x² + (y-200)² ≤ 49, 0 ≤ z ≤ 10}
- 严格遮蔽主判定: 所有当前可见表面采样点的视线均与烟幕球体相交
- 覆盖率仅作辅助诊断, 当前不使用人为覆盖率阈值
- 空间采样: coarse / medium / fine 三档 (按 MODEL.md §九 表格)
- 时间扫描: 0.02 / 0.01 / 0.005 s (medium 空间采样下)
- 严格遮蔽边界函数: f_cylinder(t) = max_visible_distance(t) - 10

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

# === 圆柱参数 ===
R_T: float = 7.0        # 圆柱半径 (FACTS.md §11 [官])
H_T: float = 10.0       # 圆柱高度 (FACTS.md §11 [官])
CYL_BASE: Vec = (0.0, 200.0, 0.0)        # 下底面圆心
CYL_TOP:  Vec = (0.0, 200.0, 10.0)       # 上底面圆心
CYL_AXIS_DIR: Vec = (0.0, 0.0, 1.0)      # 圆柱轴向 (沿 +z)

# 采样等级 (MODEL.md §九)
SAMPLE_GRADES = {
    "coarse":  dict(side_theta=48,  side_z=8,  cap_r=4,  cap_theta=48),
    "medium":  dict(side_theta=96,  side_z=16, cap_r=8,  cap_theta=96),
    "fine":    dict(side_theta=192, side_z=32, cap_r=16, cap_theta=192),
}

# 数值参数
EPS_VISIBLE: float = 1e-9      # 可见性判定容差 (n·(M-X) > 0)
EPS_GRID_BORDER: float = 1e-9  # 采样避开侧面/端面公共棱边 (单元中心已避免)
T_WINDOW_START: float = T_DETONATE
T_WINDOW_END: float = T_DETONATE + CLOUD_DURATION

# 时间扫描步长 (MODEL.md §十)
TIME_STEPS: Tuple[float, ...] = (0.02, 0.01, 0.005)


# === 表面样本 ===
@dataclass(frozen=True)
class SurfaceSample:
    point: Vec                # (x, y, z)
    normal: Vec              # 单位外法向量
    weight: float            # 面积权重
    surface_type: str        # "side" / "top" / "bottom"


# === 采样生成 ===
def generate_cylinder_samples(side_theta: int = 96,
                              side_z: int = 16,
                              cap_r: int = 8,
                              cap_theta: int = 96) -> List[SurfaceSample]:
    """生成圆柱三面 (侧面 + 顶面 + 底面) 单元中心样本.

    单元中心: theta 和 z 均使用单元中心 (避免采样在侧面与端面公共棱边上).
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

    # 侧面: theta_j = 2π(j+0.5)/n_theta, z_k = H_T · (k+0.5)/n_z
    w_side = 2.0 * math.pi * R_T * H_T / (side_theta * side_z)
    for j in range(side_theta):
        theta = 2.0 * math.pi * (j + 0.5) / side_theta
        ct = math.cos(theta)
        st = math.sin(theta)
        for k in range(side_z):
            z = H_T * (k + 0.5) / side_z
            x = R_T * ct
            y = 200.0 + R_T * st
            n_vec: Vec = (ct, st, 0.0)  # 单位外法向 (已归一)
            assert abs(math.sqrt(n_vec[0] ** 2 + n_vec[1] ** 2 + n_vec[2] ** 2) - 1.0) < 1e-12
            samples.append(SurfaceSample((x, y, z), n_vec, w_side, "side"))

    # 端面: 径向 r_i = R_T·sqrt((i+0.5)/n_r), 角度 theta_j 同上
    w_cap = math.pi * R_T ** 2 / (cap_r * cap_theta)
    for r_idx in range(cap_r):
        r = R_T * math.sqrt((r_idx + 0.5) / cap_r)
        for j in range(cap_theta):
            theta = 2.0 * math.pi * (j + 0.5) / cap_theta
            ct = math.cos(theta)
            st = math.sin(theta)
            x = r * ct
            y = 200.0 + r * st
            # 顶面 (z=10): 法向 (0, 0, 1)
            samples.append(SurfaceSample((x, y, H_T), (0.0, 0.0, 1.0), w_cap, "top"))
            # 底面 (z=0): 法向 (0, 0, -1)
            samples.append(SurfaceSample((x, y, 0.0), (0.0, 0.0, -1.0), w_cap, "bottom"))

    return samples


def verify_sample_geometry(samples: Sequence[SurfaceSample]) -> dict:
    """返回圆柱采样几何统计, 用于测试."""
    n_side = sum(1 for s in samples if s.surface_type == "side")
    n_top = sum(1 for s in samples if s.surface_type == "top")
    n_bot = sum(1 for s in samples if s.surface_type == "bottom")
    w_side_sum = sum(s.weight for s in samples if s.surface_type == "side")
    w_cap_sum = sum(s.weight for s in samples
                    if s.surface_type in ("top", "bottom"))
    total_weight = sum(s.weight for s in samples)
    expected_total = 2.0 * math.pi * R_T * H_T + 2.0 * math.pi * R_T ** 2
    return {
        "n_side": n_side, "n_top": n_top, "n_bot": n_bot,
        "total": len(samples),
        "w_side_sum": w_side_sum,
        "w_cap_sum": w_cap_sum,
        "total_weight": total_weight,
        "expected_total_weight": expected_total,
    }


# === 可见性 ===
def sample_is_visible(sample: SurfaceSample, m: Vec,
                       eps: float = EPS_VISIBLE) -> bool:
    """凸体表面支持平面可见性: n(X) · (M(t) - X) > 0.

    使用 eps 处理接近 0 的轮廓边界 (视为可见).
    """
    diff = vector_sub(m, sample.point)
    return dot(sample.normal, diff) > eps


def visible_samples(samples: Sequence[SurfaceSample], m: Vec
                     ) -> List[SurfaceSample]:
    return [s for s in samples if sample_is_visible(s, m)]


# === 遮挡判定 ===
def sample_is_occluded(sample: SurfaceSample, m: Vec, c: Vec,
                        radius: float = CLOUD_RADIUS) -> bool:
    """闭线段 [M(t), X] 是否被烟幕球遮挡.

    使用闭线段距离 (在 [M, X] 段内最近点距离 ≤ radius).
    投影落在线段延长线但不在闭线段上时, 距离会退化到端点, 不会误判.
    """
    d, _ = point_to_segment_distance(c, m, sample.point)
    return d <= radius


# === 圆柱状态评估 ===
@dataclass(frozen=True)
class CylinderState:
    t: float
    visible_count: int
    visible_weight: float
    occluded_count: int
    occluded_weight: float
    coverage_ratio: float     # 0 ≤ rho ≤ 1 (辅助诊断)
    max_visible_distance: float
    strict_margin: float      # = CLOUD_RADIUS - max_visible_distance, ≥ 0 ⇔ 严格遮蔽
    worst_sample_point: Vec | None
    worst_sample_surface: str | None
    strict_occlusion: bool    # 是否严格遮蔽


def evaluate_cylinder_state(t: float,
                              samples: Sequence[SurfaceSample]
                              ) -> CylinderState:
    """对完整圆柱在时刻 t 评估严格遮蔽与覆盖率."""
    if not math.isfinite(t):
        raise ValueError(f"t 非有限: {t}")

    m = missile_position(t)

    # 时间窗外: 返回 "无观测" 状态 (后续算法识别)
    if not (T_WINDOW_START <= t <= T_WINDOW_END):
        return CylinderState(
            t=t, visible_count=0, visible_weight=0.0,
            occluded_count=0, occluded_weight=0.0,
            coverage_ratio=0.0, max_visible_distance=float("inf"),
            strict_margin=-float("inf"),
            worst_sample_point=None, worst_sample_surface=None,
            strict_occlusion=False,
        )

    c = cloud_center(t)

    visible = visible_samples(samples, m)
    v_count = len(visible)
    v_weight = sum(s.weight for s in visible)

    if v_count == 0:
        # 视线无可见表面: missile 进入圆柱 / 视角上无暴露.
        # 在 [T_DETONATE, T_DETONATE+20] 内不应该发生 (导弹仍远).
        # 但防御性返回: margin = +CLOUD_RADIUS (严格遮蔽成立);
        #             coverage_ratio = 0 (无可见 = 无遮挡).
        return CylinderState(
            t=t, visible_count=0, visible_weight=0.0,
            occluded_count=0, occluded_weight=0.0,
            coverage_ratio=0.0, max_visible_distance=0.0,
            strict_margin=CLOUD_RADIUS,
            worst_sample_point=None, worst_sample_surface=None,
            strict_occlusion=True,
        )

    max_d = -1.0
    occ_count = 0
    occ_weight = 0.0
    worst_pt = None
    worst_surf = None

    for s in visible:
        d, _ = point_to_segment_distance(c, m, s.point)
        if d <= CLOUD_RADIUS:
            occ_count += 1
            occ_weight += s.weight
        if d > max_d:
            max_d = d
            worst_pt = s.point
            worst_surf = s.surface_type

    coverage = (occ_weight / v_weight) if v_weight > 0 else 0.0
    margin = CLOUD_RADIUS - max_d

    return CylinderState(
        t=t,
        visible_count=v_count,
        visible_weight=v_weight,
        occluded_count=occ_count,
        occluded_weight=occ_weight,
        coverage_ratio=coverage,
        max_visible_distance=max_d,
        strict_margin=margin,
        worst_sample_point=worst_pt,
        worst_sample_surface=worst_surf,
        strict_occlusion=(max_d <= CLOUD_RADIUS),
    )


def strict_boundary_value(t: float,
                            samples: Sequence[SurfaceSample]) -> float:
    """f_cylinder(t) = max_visible_distance(t) - CLOUD_RADIUS.

    严格有效遮蔽 ⇔ f_cylinder(t) ≤ 0.

    时间窗外返回大正值 (远离遮蔽).
    """
    st = evaluate_cylinder_state(t, samples)
    if st.strict_margin == -float("inf"):
        return 1e9
    return st.max_visible_distance - CLOUD_RADIUS


# === 区间求解 (复用 find_effective_intervals) ===
def find_strict_intervals(samples: Sequence[SurfaceSample],
                           scan_step: float = 0.01,
                           t_arrival: float | None = None,
                           ) -> List[Tuple[float, float]]:
    """扫描 + 二分, 找出所有严格遮蔽区间.

    使用 q1_baseline.find_effective_intervals, 注入 boundary_func = strict_boundary_value.
    """
    return find_effective_intervals(
        scan_step=scan_step,
        t_detonate=T_DETONATE,
        t_arrival=t_arrival,
        boundary_func=lambda t: strict_boundary_value(t, samples),
    )


# === 收敛验证 ===
def run_temporal_convergence(samples: Sequence[SurfaceSample]
                              ) -> dict:
    """在固定空间采样下, 用不同时间步长求严格区间."""
    per_step = {}
    intervals_per_step = []
    for step in TIME_STEPS:
        ivs = find_strict_intervals(samples, scan_step=step)
        per_step[step] = {
            "intervals": ivs,
            "n_intervals": len(ivs),
            "total_duration": total_effective_duration(ivs),
        }
        intervals_per_step.append((step, ivs))
    return {"per_step": per_step, "list": intervals_per_step}


def run_spatial_convergence(scan_step: float = 0.01
                              ) -> dict:
    """在固定时间步长下, 用三档空间采样求严格区间."""
    per_grade = {}
    intervals_per_grade = []
    for grade, params in SAMPLE_GRADES.items():
        samples = generate_cylinder_samples(**params)
        ivs = find_strict_intervals(samples, scan_step=scan_step)
        per_grade[grade] = {
            "samples": len(samples),
            "intervals": ivs,
            "n_intervals": len(ivs),
            "total_duration": total_effective_duration(ivs),
        }
        intervals_per_grade.append((grade, ivs))
    return {"per_grade": per_grade, "list": intervals_per_grade}


def check_temporal_convergence(temporal_result: dict) -> dict:
    """对时间收敛三档两两检查 (区间数量 / 起终 / 总时长 / 残差)."""
    entries = list(temporal_result["per_step"].items())
    summary = {"comparisons": [], "passed": True}
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
                for ia, ib in zip(da["intervals"], db["intervals"]):
                    starts_diff = max(starts_diff, abs(ia[0] - ib[0]))
                    ends_diff = max(ends_diff, abs(ia[1] - ib[1]))
            comp["max_start_diff"] = starts_diff
            comp["max_end_diff"] = ends_diff
            comp["total_diff"] = abs(da["total_duration"] - db["total_duration"])
            summary["comparisons"].append(comp)
    return summary


def check_spatial_convergence(spatial_result: dict) -> dict:
    """对空间收敛 medium vs fine 重点检查, coarse 仅作参考."""
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
        },
        "coarse_vs_medium": {
            "total_coarse": per["coarse"]["total_duration"],
            "total_medium": medium["total_duration"],
            "total_diff": abs(per["coarse"]["total_duration"]
                              - medium["total_duration"]),
        },
    }
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


# === SVG 对照图 ===
def write_comparison_svg(path: str,
                          point_intervals: Sequence[Tuple[float, float]],
                          cyl_intervals: Sequence[Tuple[float, float]],
                          point_total: float,
                          cyl_total: float,
                          coverage_max: float,
                          coverage_max_t: float,
                          strict_margin_max: float,
                          coverage_series: Sequence[Tuple[float, float]],
                          margin_series: Sequence[Tuple[float, float]]
                          ) -> None:
    """x-z 投影 + 时间对照面板."""
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

    # ===== 上半: x-z 投影 =====
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

    # 假目标 / 点目标 P
    ox, oy = map_x(0.0), map_z(0.0)
    parts.append(f'<circle cx="{ox}" cy="{oy}" r="4" fill="gray"/>\n')
    parts.append(f'<text x="{ox + 8}" y="{oy - 6}" font-size="11" fill="gray">'
                 '假目标 O (0,0,0)</text>\n')
    px, py = map_x(0.0), map_z(5.0)
    parts.append(f'<circle cx="{px}" cy="{py}" r="4" fill="orange"/>\n')
    parts.append(f'<text x="{px + 8}" y="{py - 6}" font-size="11" fill="orange">'
                 '点目标 P=(0,200,5)</text>\n')

    # 真目标圆柱 (x=0, z ∈ [0, 10])
    cyl_x_svg = map_x(0.0)
    cyl_top = map_z(10.0)
    cyl_bot = map_z(0.0)
    parts.append(f'<rect x="{cyl_x_svg - 3}" y="{cyl_top}" width="6" '
                 f'height="{cyl_bot - cyl_top}" fill="none" '
                 'stroke="purple" stroke-width="2"/>\n')
    parts.append(f'<text x="{cyl_x_svg + 6}" y="{(cyl_top + cyl_bot) / 2}" '
                 f'font-size="11" fill="purple">'
                 '真目标圆柱 (x=0, y=200, z∈[0,10])</text>\n')

    # M1 / FY1 / 烟幕弹 / 云团 / 投放点 / 起爆点 (与 Q1 baseline 一致)
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

    # 区间标注: 点目标 (orange), 完整圆柱 (purple 加粗)
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

    # 副标题 (上半)
    parts.append(f'<text x="500" y="{PB + 40}" text-anchor="middle" '
                 'font-size="11">'
                 f'点目标总时长 {point_total:.4f}s | 完整圆柱总时长 '
                 f'{cyl_total:.4f}s | max ρ {coverage_max:.4f} @ '
                 f't={coverage_max_t:.3f}s | max margin {strict_margin_max:.4f}m'
                 '</text>\n')

    # ===== 下半: 时间对照 =====
    TL, TR, TP, TB = 80.0, 940.0, 430.0, 700.0
    TW = TR - TL
    TH = TB - TP
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

    # 时间刻度
    for tv in (5.1, 8.0, 12.0, 16.0, 20.0, 25.1):
        sx = map_t(tv)
        parts.append(f'<line x1="{sx}" y1="{TB}" x2="{sx}" y2="{TB + 4}" '
                     'stroke="black"/>\n')
        parts.append(f'<text x="{sx}" y="{TB + 16}" text-anchor="middle" '
                     f'font-size="10">{tv:.1f}</text>\n')

    # 通道 1: 点目标有效 (高 60 px)
    ch1_top = TP + 5
    ch1_bot = ch1_top + 60
    parts.append(f'<text x="{TL - 5}" y="{(ch1_top + ch1_bot) / 2 + 4}" '
                 'text-anchor="end" font-size="11">点目标</text>\n')
    for a, b in point_intervals:
        ax = map_t(max(a, t_min)); bx = map_t(min(b, t_max))
        parts.append(f'<rect x="{ax:.1f}" y="{ch1_top}" width="{max(1, bx - ax):.1f}" '
                     f'height="{ch1_bot - ch1_top}" fill="orange" '
                     'fill-opacity="0.7"/>\n')

    # 通道 2: 圆柱严格有效
    ch2_top = ch1_bot + 10
    ch2_bot = ch2_top + 60
    parts.append(f'<text x="{TL - 5}" y="{(ch2_top + ch2_bot) / 2 + 4}" '
                 'text-anchor="end" font-size="11">圆柱严格</text>\n')
    for a, b in cyl_intervals:
        ax = map_t(max(a, t_min)); bx = map_t(min(b, t_max))
        parts.append(f'<rect x="{ax:.1f}" y="{ch2_top}" width="{max(1, bx - ax):.1f}" '
                     f'height="{ch2_bot - ch2_top}" fill="red" '
                     'fill-opacity="0.7"/>\n')

    # 通道 3: 覆盖率 rho ∈ [0, 1]
    ch3_top = ch2_bot + 10
    ch3_bot = ch3_top + 80
    parts.append(f'<text x="{TL - 5}" y="{(ch3_top + ch3_bot) / 2 + 4}" '
                 'text-anchor="end" font-size="11">ρ(t)</text>\n')
    if coverage_series:
        # y 轴 0~1
        prev_x = prev_y = None
        for t, rho in coverage_series:
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

    # 通道 4: margin (单位 m), 零线明显
    ch4_top = ch3_bot + 10
    ch4_bot = ch4_top + 80
    parts.append(f'<text x="{TL - 5}" y="{(ch4_top + ch4_bot) / 2 + 4}" '
                 'text-anchor="end" font-size="11">margin(m)</text>\n')
    if margin_series:
        # 找 y 范围
        ms = [m for _, m in margin_series]
        m_min = min(-0.5, min(ms))
        m_max = max(0.5, max(ms))
        if m_max == m_min:
            m_max = m_min + 1.0
        zero_y = ch4_bot - (0 - m_min) / (m_max - m_min) * (ch4_bot - ch4_top)
        parts.append(f'<line x1="{TL}" y1="{zero_y:.1f}" x2="{TR}" '
                     f'y2="{zero_y:.1f}" stroke="green" stroke-width="1.5"/>\n')
        parts.append(f'<text x="{TR + 5}" y="{zero_y + 3:.1f}" font-size="10" '
                     'fill="green">margin=0</text>\n')

        prev_x = prev_y = None
        for t, m_val in margin_series:
            sx = map_t(t)
            sy = ch4_bot - (m_val - m_min) / (m_max - m_min) * (ch4_bot - ch4_top)
            if prev_x is not None:
                parts.append(f'<line x1="{prev_x:.1f}" y1="{prev_y:.1f}" '
                             f'x2="{sx:.1f}" y2="{sy:.1f}" '
                             'stroke="black" stroke-width="1"/>\n')
            prev_x, prev_y = sx, sy

    # 图例
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
def build_time_series(samples: Sequence[SurfaceSample],
                       scan_step: float = 0.05,
                       ) -> Tuple[List[Tuple[float, float]],
                                  List[Tuple[float, float]],
                                  float, float, float, float]:
    """在整个时间窗上每 scan_step 评估一次, 返回用于 SVG 下部的 series.

    默认 0.05 s = 20 Hz, 用于 SVG 绘制足够光滑, 不会过度膨胀 SVG 体积.
    区间求解 (find_strict_intervals) 仍用更细的 scan_step (0.01 s 或更小).
    """
    ts = []
    n = int(math.ceil((T_WINDOW_END - T_WINDOW_START) / scan_step)) + 1
    for i in range(n):
        ts.append(T_WINDOW_START + (T_WINDOW_END - T_WINDOW_START)
                  * i / (n - 1))

    cov_series = []
    mar_series = []
    cov_max = -1.0
    cov_max_t = T_DETONATE
    margin_max = -float("inf")
    margin_max_t = T_DETONATE

    for t in ts:
        s = evaluate_cylinder_state(t, samples)
        cov_series.append((t, s.coverage_ratio))
        mar_series.append((t, s.strict_margin))
        if s.coverage_ratio > cov_max:
            cov_max = s.coverage_ratio
            cov_max_t = t
        if s.strict_margin > margin_max:
            margin_max = s.strict_margin
            margin_max_t = t

    return cov_series, mar_series, cov_max, cov_max_t, margin_max, margin_max_t


def main(argv: List[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    out_path = argv[0] if argv else "outputs/q1/q1_cylinder_comparison.svg"

    print("模型状态: FULL-CYLINDER CANDIDATE / EXPERIMENTAL")
    print("=" * 70)

    # Q1 点目标基线
    point_result = compute_q1()
    point_intervals = point_result["intervals"]
    point_total = point_result["total_duration"]
    print("## 方案 A: 点目标基线")
    print(f"  遮蔽区间: {point_intervals}")
    print(f"  总时长:   {point_total:.6f} s")
    print(f"  代表点:   P = (0, 200, 5)")
    print()

    # 三档空间采样
    print("## 方案 B: 完整圆柱严格遮蔽")
    print(f"{'grade':<10s} {'samples':>8s} {'intervals':>12s} {'total(s)':>12s}")
    print("-" * 50)
    per_grade_ivs = {}
    per_grade_samples = {}
    for grade, params in SAMPLE_GRADES.items():
        samps = generate_cylinder_samples(**params)
        ivs = find_strict_intervals(samps, scan_step=0.01)
        per_grade_samples[grade] = samps
        per_grade_ivs[grade] = ivs
        tot = total_effective_duration(ivs)
        print(f"{grade:<10s} {len(samps):>8d} {str(ivs):>12s} {tot:>12.6f}")

    # 候选 = fine
    final_ivs = per_grade_ivs["fine"]
    final_total = total_effective_duration(final_ivs)
    print()
    print(f"  最终候选 (fine): 区间={final_ivs}, 总时长={final_total:.6f} s")

    # 时间 / 覆盖率 / 裕量
    cov_series, mar_series, cov_max, cov_max_t, margin_max, margin_max_t = \
        build_time_series(per_grade_samples["fine"], scan_step=0.05)
    print(f"  最大覆盖率: {cov_max:.6f} @ t={cov_max_t:.4f} s")
    print(f"  最大严格遮蔽裕量: {margin_max:.6f} m @ t={margin_max_t:.4f} s")

    # 时间收敛
    print()
    print("## 时间收敛 (medium 空间采样)")
    temp_res = run_temporal_convergence(per_grade_samples["medium"])
    print(f"{'step':>8s} {'n_ivs':>6s} {'intervals':>40s} {'total(s)':>12s}")
    print("-" * 80)
    for step, info in temp_res["per_step"].items():
        print(f"{step:>8.4f} {info['n_intervals']:>6d} "
              f"{str(info['intervals'])[:40]:>40s} {info['total_duration']:>12.6f}")

    # 空间收敛
    print()
    print("## 空间收敛 (时间步长 0.01 s)")
    spat_res = run_spatial_convergence(scan_step=0.01)
    print(f"{'grade':<10s} {'samples':>8s} {'intervals':>40s} {'total(s)':>12s}")
    print("-" * 80)
    for grade, info in spat_res["per_grade"].items():
        print(f"{grade:<10s} {info['samples']:>8d} "
              f"{str(info['intervals'])[:40]:>40s} "
              f"{info['total_duration']:>12.6f}")

    # 与点目标对照
    cmp_dict = compare_point_and_cylinder(final_total, point_total)
    print()
    print("## 与 Q1 点目标基线对照 (fine)")
    print(f"  ΔT (cyl - point) = {cmp_dict['delta_T']:.6f} s")
    print(f"  相对差异        = {cmp_dict['relative_difference']:.6f}")
    print(f"  点目标时长      = {cmp_dict['point_total']:.6f} s")
    print(f"  完整圆柱时长    = {cmp_dict['cylinder_total']:.6f} s")

    # SVG
    write_comparison_svg(out_path,
                          point_intervals, final_ivs,
                          point_total, final_total,
                          cov_max, cov_max_t, margin_max,
                          cov_series, mar_series)
    print()
    print(f"SVG 路径: {out_path}")
    print()
    print("## 当前局限")
    print("- 完整圆柱仍是有限采样近似 (单元中心法, medium/fine 两档)")
    print("- 覆盖率仅作辅助诊断, 当前不使用人为覆盖率阈值")
    print("- 凸体支持平面可见性; 不处理圆柱自遮挡奇异情况 (远距离下不发生)")
    print("- 仍是 FULL-CYLINDER CANDIDATE / EXPERIMENTAL")
    print("- 等待外部审核, 不得冒充 VERIFIED / FINAL")
    return 0


if __name__ == "__main__":
    sys.exit(main())
