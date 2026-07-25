"""Q1 点目标最小可运行基线 (BASELINE / EXPERIMENTAL)

按 problem/FACTS.md 与本轮 MODEL.md 显式假设:
- g = 9.8 m/s², 方向 -z
- 烟幕弹投放瞬间共速
- 忽略空气阻力、风场、投放误差、起爆误差、云团水平漂移
- 起爆后云团立即以 3 m/s 沿 -z 下沉
- 点目标代表点 P = (0, 200, 5) = 圆柱几何中心
- 方案 A 点目标基线: 闭线段距离 d(t) = ||C(t) - N(t)|| ≤ 10 m
- 只使用 Python 标准库
"""

from __future__ import annotations

import math
import os
import sys
from typing import Callable, List, Sequence, Tuple

# === 关键常量 (集中定义) ===
G: float = 9.8                   # m/s², 重力加速度
DRONE_SPEED: float = 120.0       # m/s, FY1 速度
MISSILE_SPEED: float = 300.0     # m/s, M1 速度
CLOUD_SINK: float = 3.0          # m/s, 云团下沉速度
CLOUD_RADIUS: float = 10.0       # m, 有效遮蔽半径
CLOUD_DURATION: float = 20.0     # s, 起爆后有效时间窗

U0: Tuple[float, float, float] = (17800.0, 0.0, 1800.0)  # FY1 初始位置
M0: Tuple[float, float, float] = (20000.0, 0.0, 2000.0)  # M1 初始位置
O:  Tuple[float, float, float] = (0.0, 0.0, 0.0)         # 假目标 (原点)
P:  Tuple[float, float, float] = (0.0, 200.0, 5.0)       # 点目标代表点 (几何中心)

# Q1 固定参数
V_U: Tuple[float, float, float] = (-DRONE_SPEED, 0.0, 0.0)  # FY1 速度向量
T_RELEASE: float = 1.5
DELAY: float = 3.6
T_DETONATE: float = T_RELEASE + DELAY  # 5.1 s

# 数值求解参数
SCAN_STEPS: Tuple[float, ...] = (0.02, 0.01, 0.005)
BISECT_TOL: float = 1e-8
BISECT_MAX_ITER: int = 200


# === 向量基础 ===
Vec = Tuple[float, float, float]


def vector_add(a: Vec, b: Vec) -> Vec:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def vector_sub(a: Vec, b: Vec) -> Vec:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def vector_scale(a: Vec, s: float) -> Vec:
    return (a[0] * s, a[1] * s, a[2] * s)


def dot(a: Vec, b: Vec) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def norm(a: Vec) -> float:
    return math.sqrt(dot(a, a))


def _check_finite_vec(name: str, v: Vec) -> None:
    for i, c in enumerate(v):
        if not math.isfinite(c):
            raise ValueError(f"{name}[{i}] 非有限值: {c}")


# === 运动学 ===
def missile_velocity(m0: Vec = M0, o: Vec = O, speed: float = MISSILE_SPEED) -> Vec:
    """M1 速度向量: 300 m/s 沿 (o - m0) 单位方向."""
    d = vector_sub(o, m0)
    n = norm(d)
    if n < 1e-12:
        raise ValueError("M1 与假目标重合, 无法确定方向")
    v = vector_scale(d, speed / n)
    _check_finite_vec("missile_velocity", v)
    return v


def missile_arrival_time(m0: Vec = M0, o: Vec = O, speed: float = MISSILE_SPEED) -> float:
    return norm(vector_sub(o, m0)) / speed


def drone_position(t: float, u0: Vec = U0, v_u: Vec = V_U) -> Vec:
    if not math.isfinite(t):
        raise ValueError(f"t 非有限: {t}")
    p = vector_add(u0, vector_scale(v_u, t))
    _check_finite_vec("drone_position", p)
    return p


def missile_position(t: float, m0: Vec = M0, o: Vec = O,
                     speed: float = MISSILE_SPEED) -> Vec:
    if not math.isfinite(t):
        raise ValueError(f"t 非有限: {t}")
    v = missile_velocity(m0, o, speed)
    p = vector_add(m0, vector_scale(v, t))
    _check_finite_vec("missile_position", p)
    return p


def bomb_position(t: float, t_release: float = T_RELEASE,
                  v_b: Vec = V_U, r: Vec | None = None) -> Vec:
    """烟幕弹在投放后做抛体运动 (默认初速度 = FY1 当时速度)."""
    if not math.isfinite(t):
        raise ValueError(f"t 非有限: {t}")
    if t < t_release:
        raise ValueError(f"t={t} 早于 t_release={t_release}")
    if r is None:
        r = drone_position(t_release)
    tau = t - t_release
    p = (r[0] + v_b[0] * tau,
         r[1] + v_b[1] * tau,
         r[2] + v_b[2] * tau - 0.5 * G * tau * tau)
    _check_finite_vec("bomb_position", p)
    return p


def detonation_point(t_release: float = T_RELEASE, delay: float = DELAY,
                     v_b: Vec = V_U, r: Vec | None = None) -> Vec:
    return bomb_position(t_release + delay, t_release, v_b, r)


def cloud_center(t: float, t_detonate: float = T_DETONATE,
                 d: Vec | None = None) -> Vec:
    if not math.isfinite(t):
        raise ValueError(f"t 非有限: {t}")
    if d is None:
        d = detonation_point()
    sink = CLOUD_SINK * max(0.0, t - t_detonate)
    p = (d[0], d[1], d[2] - sink)
    _check_finite_vec("cloud_center", p)
    return p


# === 几何: 点到闭线段距离 ===
def point_to_segment_distance(p: Vec, a: Vec, b: Vec) -> Tuple[float, Vec]:
    """返回 (距离, 最近点 N). 闭线段 [a, b]."""
    ab = vector_sub(b, a)
    ab_sq = dot(ab, ab)
    if ab_sq < 1e-18:
        # 退化线段
        n = vector_sub(p, a)
        return norm(n), a
    ap = vector_sub(p, a)
    lam_raw = dot(ap, ab) / ab_sq
    lam = min(1.0, max(0.0, lam_raw))
    n = vector_add(a, vector_scale(ab, lam))
    d = norm(vector_sub(p, n))
    if not math.isfinite(d):
        raise ValueError("距离非有限")
    return d, n


# === 遮蔽判定 ===
def is_effective(t: float, t_start: float, t_end: float) -> bool:
    return t_start <= t <= t_end


def f_distance_minus_radius(t: float,
                            t_detonate: float = T_DETONATE,
                            t_arrival: float | None = None,
                            p_point: Vec = P) -> float:
    """遮蔽边界函数 f(t) = d(t) - 10. 仅在合法时间窗内有效."""
    if t_detonate <= t <= t_detonate + CLOUD_DURATION and (
        t_arrival is None or t <= t_arrival
    ):
        m = missile_position(t)
        c = cloud_center(t, t_detonate)
        d, _ = point_to_segment_distance(c, m, p_point)
        return d - CLOUD_RADIUS
    # 时间窗外: 返回大正值 (远离遮蔽)
    return 1e9


# === 数值求根: 二分 ===
def bisect_root(f: Callable[[float], float], lo: float, hi: float,
                tol: float = BISECT_TOL, max_iter: int = BISECT_MAX_ITER) -> float:
    f_lo = f(lo)
    f_hi = f(hi)
    if f_lo == 0.0:
        return lo
    if f_hi == 0.0:
        return hi
    if f_lo * f_hi > 0.0:
        raise ValueError("二分端点同号, 无法求根")
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        if (hi - lo) < tol:
            return mid
        f_mid = f(mid)
        if f_mid == 0.0:
            return mid
        if f_lo * f_mid < 0.0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return 0.5 * (lo + hi)


# === 找有效遮蔽区间 ===
def find_effective_intervals(scan_step: float = 0.01,
                              t_detonate: float = T_DETONATE,
                              t_arrival: float | None = None,
                              p_point: Vec = P) -> List[Tuple[float, float]]:
    """扫描 + 二分定位所有 d(t) ≤ 10 的闭区间.

    算法:
    1. 在 [t_detonate, t_end] 上等距取 n 个采样点, 计算 f(t) = d(t) - 10
    2. 找出所有跨零点区间 [t_i, t_{i+1}] (f(t_i)*f(t_{i+1}) ≤ 0 且 f 含负)
    3. 用 bisect 在每个跨零段内精化零点
    4. 配对进入 / 离开点形成区间
    5. 处理整段全部有效 (起爆立即遮蔽 / 直至末端) 的边界情况
    """
    t_end = t_detonate + CLOUD_DURATION
    if t_arrival is not None:
        t_end = min(t_end, t_arrival)
    if t_end <= t_detonate:
        return []

    f = lambda t: f_distance_minus_radius(t, t_detonate, t_arrival, p_point)
    n_steps = max(2, int(math.ceil((t_end - t_detonate) / scan_step)) + 1)
    ts = [t_detonate + (t_end - t_detonate) * i / (n_steps - 1)
          for i in range(n_steps)]
    fs = [f(t) for t in ts]

    inside = [fv <= 0.0 for fv in fs]

    intervals: List[Tuple[float, float]] = []
    i = 0
    while i < n_steps - 1:
        a_in, b_in = inside[i], inside[i + 1]
        if (not a_in) and b_in:
            # 进入遮蔽: 进入点 = 跨零点
            root_entry = bisect_root(f, ts[i], ts[i + 1])
            # 找出下一个离开点 (扫描到 inside 变 False 或到末尾)
            j = i + 1
            while j < n_steps - 1 and inside[j + 1]:
                j += 1
            if j < n_steps - 1:
                root_exit = bisect_root(f, ts[j], ts[j + 1])
            else:
                root_exit = t_end
            intervals.append((root_entry, root_exit))
            i = j
        else:
            i += 1

    # 处理起爆瞬间已遮蔽
    if inside[0] and (not intervals or intervals[0][0] > ts[0] + 1e-9):
        # 找第一个离开点
        j = 0
        while j < n_steps - 1 and inside[j + 1]:
            j += 1
        if j < n_steps - 1:
            root_exit = bisect_root(f, ts[j], ts[j + 1])
        else:
            root_exit = t_end
        intervals.insert(0, (ts[0], root_exit))

    # 合并相邻区间
    merged: List[Tuple[float, float]] = []
    for a, b in intervals:
        if merged and merged[-1][1] >= a - 1e-9:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return merged


def total_effective_duration(intervals: Sequence[Tuple[float, float]]) -> float:
    return sum(b - a for a, b in intervals)


# === Q1 主计算 ===
def compute_q1(scan_step: float = 0.01) -> dict:
    v_m = missile_velocity()
    t_arrival = missile_arrival_time()
    r_release = drone_position(T_RELEASE)
    d_deton = detonation_point()
    intervals = find_effective_intervals(scan_step=scan_step,
                                          t_arrival=t_arrival)
    return {
        "v_u": V_U,
        "v_m": v_m,
        "t_release": T_RELEASE,
        "r_release": r_release,
        "t_detonate": T_DETONATE,
        "d_deton": d_deton,
        "t_arrival": t_arrival,
        "intervals": intervals,
        "total_duration": total_effective_duration(intervals),
    }


# === SVG 绘图 (无第三方库) ===
SVG_HEADER = (
    '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
    '<svg xmlns="http://www.w3.org/2000/svg" '
    'viewBox="0 0 960 640" width="960" height="640" '
    'font-family="Arial, sans-serif" font-size="12">\n'
)
SVG_FOOTER = "</svg>\n"


def write_svg_plot(path: str, result: dict) -> None:
    """x-z 投影. 标注关键点、轨迹、遮蔽区间."""
    # 画布区域
    X0, X1 = 0.0, 20500.0      # 数据 x 范围 (含少量 padding)
    Z0, Z1 = 0.0, 2100.0       # 数据 z 范围
    PL, PR, PT, PB = 80.0, 920.0, 50.0, 560.0  # 画图区域 (left/right/top/bottom)
    W = PR - PL
    H = PB - PT

    def map_x(x: float) -> float:
        return PL + (x - X0) / (X1 - X0) * W

    # SVG y 向下, z 高映射到小 y (画图顶部)
    def map_z(z: float) -> float:
        return PB - (z - Z0) / (Z1 - Z0) * H

    parts: List[str] = [SVG_HEADER]

    # 背景
    parts.append(f'<rect x="0" y="0" width="960" height="640" fill="white"/>\n')
    # 标题
    parts.append(
        '<text x="480" y="28" text-anchor="middle" '
        'font-size="18" font-weight="bold">'
        'Q1 Point-Target Baseline (BASELINE / EXPERIMENTAL)</text>\n'
    )
    # 副标题
    parts.append(
        '<text x="480" y="610" text-anchor="middle" font-size="11" '
        'fill="gray">x-z projection | units in meters | '
        '方案 A 点目标基线, 非完整圆柱正式结果</text>\n'
    )

    # 坐标轴
    parts.append(f'<line x1="{PL}" y1="{PB}" x2="{PR}" y2="{PB}" stroke="black"/>\n')
    parts.append(f'<line x1="{PL}" y1="{PT}" x2="{PL}" y2="{PB}" stroke="black"/>\n')
    parts.append(f'<text x="{PR - 20}" y="{PB + 18}" font-size="12">x (m)</text>\n')
    parts.append(f'<text x="{PL - 30}" y="{PT + 5}" font-size="12">z (m)</text>\n')

    # 刻度 (粗略)
    for xv in range(0, 20001, 5000):
        sx = map_x(xv)
        parts.append(f'<line x1="{sx}" y1="{PB}" x2="{sx}" y2="{PB + 4}" stroke="black"/>\n')
        parts.append(f'<text x="{sx}" y="{PB + 16}" text-anchor="middle">{xv}</text>\n')
    for zv in range(0, 2001, 500):
        sy = map_z(zv)
        parts.append(f'<line x1="{PL - 4}" y1="{sy}" x2="{PL}" y2="{sy}" stroke="black"/>\n')
        parts.append(f'<text x="{PL - 8}" y="{sy + 4}" text-anchor="end">{zv}</text>\n')

    # 假目标
    ox, oy = map_x(0.0), map_z(0.0)
    parts.append(f'<circle cx="{ox}" cy="{oy}" r="4" fill="gray"/>\n')
    parts.append(f'<text x="{ox + 8}" y="{oy - 6}" font-size="11" fill="gray">假目标 O (0,0,0)</text>\n')

    # 点目标代表点
    px, py = map_x(0.0), map_z(5.0)
    parts.append(f'<circle cx="{px}" cy="{py}" r="4" fill="orange"/>\n')
    parts.append(f'<text x="{px + 8}" y="{py - 6}" font-size="11" fill="orange">'
                 '点目标 P (0,200,5) [y=200, 几何中心]</text>\n')

    # M1 轨迹 (从 t=0 到 t=t_arrival, 步长 0.5s)
    v_m = result["v_m"]
    m0 = M0
    t_arr = result["t_arrival"]
    n_m = int(math.ceil(t_arr / 0.5)) + 1
    pts = []
    for i in range(n_m):
        t = i * 0.5
        m = (m0[0] + v_m[0] * t, m0[1] + v_m[1] * t, m0[2] + v_m[2] * t)
        pts.append((map_x(m[0]), map_z(m[2])))
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    parts.append(f'<polyline points="{poly}" fill="none" stroke="red" stroke-width="2"/>\n')
    # M1 起点标签
    mx0, my0 = map_x(m0[0]), map_z(m0[2])
    parts.append(f'<circle cx="{mx0}" cy="{my0}" r="4" fill="red"/>\n')
    parts.append(f'<text x="{mx0 + 8}" y="{my0 - 6}" font-size="11" fill="red">'
                 f'M1 @ t=0 ({m0[0]:.0f}, 0, {m0[2]:.0f})</text>\n')

    # FY1 轨迹 (从 t=0 到 t=t_release, 步长 0.1s)
    n_f = int(math.ceil(T_RELEASE / 0.1)) + 1
    pts = []
    for i in range(n_f):
        t = i * 0.1
        u = drone_position(t)
        pts.append((map_x(u[0]), map_z(u[2])))
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    parts.append(f'<polyline points="{poly}" fill="none" stroke="blue" stroke-width="2"/>\n')
    # FY1 起点
    ux0, uy0 = map_x(U0[0]), map_z(U0[2])
    parts.append(f'<circle cx="{ux0}" cy="{uy0}" r="4" fill="blue"/>\n')
    parts.append(f'<text x="{ux0 - 8}" y="{uy0 - 6}" text-anchor="end" font-size="11" fill="blue">'
                 f'FY1 @ t=0 ({U0[0]:.0f}, 0, {U0[2]:.0f})</text>\n')

    # 投放点
    rr = result["r_release"]
    rsx, rsy = map_x(rr[0]), map_z(rr[2])
    parts.append(f'<circle cx="{rsx}" cy="{rsy}" r="5" fill="blue" '
                 'stroke="black" stroke-width="1"/>\n')
    parts.append(f'<text x="{rsx + 8}" y="{rsy + 4}" font-size="11" fill="blue">'
                 f'投放点 R (t=1.5s) ({rr[0]:.1f}, 0, {rr[2]:.1f})</text>\n')

    # 烟幕弹抛体轨迹 (投放 → 起爆, 步长 0.1s)
    n_b = int(math.ceil((T_DETONATE - T_RELEASE) / 0.1)) + 1
    pts = []
    for i in range(n_b):
        t = T_RELEASE + i * (T_DETONATE - T_RELEASE) / (n_b - 1)
        b = bomb_position(t)
        pts.append((map_x(b[0]), map_z(b[2])))
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    parts.append(f'<polyline points="{poly}" fill="none" stroke="purple" '
                 'stroke-width="2" stroke-dasharray="4,2"/>\n')

    # 起爆点
    dd = result["d_deton"]
    dsx, dsy = map_x(dd[0]), map_z(dd[2])
    parts.append(f'<circle cx="{dsx}" cy="{dsy}" r="5" fill="purple" '
                 'stroke="black" stroke-width="1"/>\n')
    parts.append(f'<text x="{dsx + 8}" y="{dsy + 14}" font-size="11" fill="purple">'
                 f'起爆点 D (t=5.1s) ({dd[0]:.1f}, 0, {dd[2]:.3f})</text>\n')

    # 云团下沉轨迹 (起爆 → 起爆+20, 步长 0.5s)
    n_c = int(math.ceil(CLOUD_DURATION / 0.5)) + 1
    pts = []
    for i in range(n_c):
        t = T_DETONATE + i * CLOUD_DURATION / (n_c - 1)
        c = cloud_center(t)
        pts.append((map_x(c[0]), map_z(c[2])))
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    parts.append(f'<polyline points="{poly}" fill="none" stroke="green" '
                 'stroke-width="2" stroke-dasharray="2,2"/>\n')

    # 云团在 t_detonate, t_detonate+10, t_detonate+20 三个时刻的圆
    for tc, label, opacity in [
        (T_DETONATE, "t=5.1s", 0.20),
        (T_DETONATE + 10.0, "t=15.1s", 0.10),
        (T_DETONATE + 20.0, "t=25.1s", 0.05),
    ]:
        c = cloud_center(tc)
        sx, sy = map_x(c[0]), map_z(c[2])
        # 半径按 10m 缩放到 SVG (简单缩放: 1m ≈ 35.5px on x-axis)
        r_svg = 10.0 * (W / (X1 - X0))
        parts.append(f'<circle cx="{sx}" cy="{sy}" r="{r_svg:.1f}" '
                     f'fill="green" fill-opacity="{opacity}" '
                     f'stroke="green" stroke-width="1"/>\n')

    # 遮蔽区间在云团下沉轨迹上的标注
    for a, b in result["intervals"]:
        if a > T_DETONATE + CLOUD_DURATION:
            continue
        ca = cloud_center(a)
        cb = cloud_center(b)
        ax, ay = map_x(ca[0]), map_z(ca[2])
        bx, by = map_x(cb[0]), map_z(cb[2])
        parts.append(f'<line x1="{ax:.1f}" y1="{ay:.1f}" x2="{bx:.1f}" y2="{by:.1f}" '
                     'stroke="orange" stroke-width="4"/>\n')
    # 起止标签
    if result["intervals"]:
        a, b = result["intervals"][0]
        ca = cloud_center(a)
        sx, sy = map_x(ca[0]), map_z(ca[2])
        parts.append(f'<text x="{sx + 8}" y="{sy - 8}" font-size="10" fill="orange">'
                     f'遮蔽开始 t={a:.4f}s</text>\n')
        cb = cloud_center(b)
        sx, sy = map_x(cb[0]), map_z(cb[2])
        parts.append(f'<text x="{sx + 8}" y="{sy - 8}" font-size="10" fill="orange">'
                     f'遮蔽结束 t={b:.4f}s</text>\n')

    # 图例
    legend_x = PR - 220
    legend_y = PT + 20
    items = [
        ("red", "M1 轨迹"),
        ("blue", "FY1 轨迹"),
        ("purple", "烟幕弹抛体 (投放→起爆)"),
        ("green", "云团下沉 (起爆→+20s)"),
        ("orange", "有效遮蔽区间"),
    ]
    parts.append(f'<rect x="{legend_x - 10}" y="{legend_y - 18}" width="220" '
                 f'height="{20 * len(items) + 10}" fill="white" '
                 f'stroke="gray" stroke-width="1"/>\n')
    for i, (color, label) in enumerate(items):
        y = legend_y + i * 20
        parts.append(f'<line x1="{legend_x}" y1="{y}" x2="{legend_x + 20}" y2="{y}" '
                     f'stroke="{color}" stroke-width="2"/>\n')
        parts.append(f'<text x="{legend_x + 28}" y="{y + 4}" font-size="11">{label}</text>\n')

    parts.append(SVG_FOOTER)

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("".join(parts))


# === 主入口 ===
def main(argv: List[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    out_path = argv[0] if argv else "outputs/q1/q1_baseline_plot.svg"

    result = compute_q1(scan_step=0.01)
    write_svg_plot(out_path, result)

    def f(v: float) -> str:
        return f"{v:.6f}"

    print("模型状态: BASELINE / EXPERIMENTAL")
    print(f"FY1 速度向量: ({f(result['v_u'][0])}, {f(result['v_u'][1])}, {f(result['v_u'][2])}) m/s")
    print(f"M1 速度向量:  ({f(result['v_m'][0])}, {f(result['v_m'][1])}, {f(result['v_m'][2])}) m/s  "
          f"|v|={f(norm(result['v_m']))} m/s")
    print(f"投放时刻: t = {f(result['t_release'])} s")
    print(f"投放点: ({f(result['r_release'][0])}, {f(result['r_release'][1])}, {f(result['r_release'][2])}) m")
    print(f"起爆时刻: t = {f(result['t_detonate'])} s")
    print(f"起爆点: ({f(result['d_deton'][0])}, {f(result['d_deton'][1])}, {f(result['d_deton'][2])}) m")
    print(f"M1 到达假目标理论时刻: t = {f(result['t_arrival'])} s")
    print(f"遮蔽区间: {result['intervals']}")
    print(f"有效遮蔽总时长: {f(result['total_duration'])} s")
    print(f"图像路径: {out_path}")
    print()
    print("模型局限:")
    print("- 仅方案 A 点目标基线, 非完整圆柱正式结果")
    print("- 忽略空气阻力、风场、烟幕弹旋转、投放/起爆时间误差")
    print("- 投放瞬间共速 (v_B = v_U)")
    print("- 点目标代表点 P = (0,200,5) 为圆柱几何中心, 真实圆柱判定待 Q2 之前冻结")
    return 0


if __name__ == "__main__":
    sys.exit(main())
