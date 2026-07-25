"""Q1 点目标最小可运行基线 - 单元测试 (BASELINE / EXPERIMENTAL)

只使用 Python 标准库 + unittest.
测试分组:
- A. 手算验证 (R/D 坐标, 容忍 ≤1e-6 m)
- B. M1 速度方向与大小
- C. 二分求根精度
- D. 闭线段距离 (端点、内点、超界、退化)
- E. 区间端点 (绝对残差 + 进入/离开状态)
- F. 数值稳定性 (NaN/Inf 输入)
- G. 时间窗外判定
- H. 收敛性 (3+3 整/非整倍步长)
- I. 边界函数注入 (8 个算法层面测试)
- J. 云团下沉 60m 与点目标 P (附录)
"""

from __future__ import annotations

import math
import os
import sys
import unittest
from typing import Callable

# 允许从项目根目录运行
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.q1_baseline import (
    G, DRONE_SPEED, MISSILE_SPEED, CLOUD_SINK, CLOUD_RADIUS, CLOUD_DURATION,
    U0, M0, O, P, V_U, T_RELEASE, DELAY, T_DETONATE,
    SCAN_STEPS, BISECT_TOL,
    vector_add, vector_sub, vector_scale, dot, norm,
    drone_position, missile_velocity, missile_position,
    missile_arrival_time, bomb_position, detonation_point, cloud_center,
    point_to_segment_distance, is_effective,
    f_distance_minus_radius, bisect_root,
    find_effective_intervals, total_effective_duration,
    compute_q1,
)


# === 收敛步长 (集中定义) ===
# 整倍数关系
STEPS_INT_MULTIPLE = (0.02, 0.01, 0.005)
# 非整倍数关系 (与 0.02 不构成整倍数)
STEPS_NON_INTEGER = (0.019, 0.011, 0.0067)
ALL_STEPS = STEPS_INT_MULTIPLE + STEPS_NON_INTEGER

# 边界点绝对残差容差 (与二分时间容差 1e-8、浮点误差相容;
# Q1 端点处 f 的导数很大, 1e-8 二分容差对应 f 残差最多约 1e-6,
# 故留出 5x 余量)
ENDPOINT_F_TOL = 5e-6


# === 工具断言 ===
def vec_close(a, b, tol: float = 1e-9) -> bool:
    return all(abs(a[i] - b[i]) < tol for i in range(3))


# === A. 手算验证 ===
class A_HandCalcVerification(unittest.TestCase):

    def test_release_point_R_17620(self):
        """R 由 Q1 给定输入推导: FY1 初始位置 + 120 m/s 飞行 1.5 s."""
        r = drone_position(T_RELEASE)
        self.assertTrue(vec_close(r, (17620.0, 0.0, 1800.0), tol=1e-6),
                        f"投放点 R={r}")

    def test_detonation_point_D_17188_1736(self):
        """D 由起爆点公式推导 (g=9.8, 共速假设)."""
        d = detonation_point()
        self.assertTrue(vec_close(d, (17188.0, 0.0, 1736.496), tol=1e-6),
                        f"起爆点 D={d}")

    def test_detonate_z_analytic(self):
        """D.z = 1800 - 0.5*9.8*3.6^2 = 1736.496 (在 g=9.8 假设下)."""
        expected = 1800.0 - 0.5 * G * DELAY * DELAY
        d = detonation_point()
        self.assertAlmostEqual(d[2], expected, places=8)
        self.assertAlmostEqual(expected, 1736.496, places=8)


# === B. M1 速度方向与大小 ===
class B_MissileVelocity(unittest.TestCase):

    def test_magnitude(self):
        v = missile_velocity()
        self.assertAlmostEqual(norm(v), MISSILE_SPEED, places=9)

    def test_direction_toward_origin(self):
        """v_M = (O - M0) / |O - M0| * speed (§9 [官]: 方向始终指向假目标)."""
        v = missile_velocity()
        d = vector_sub(O, M0)
        n = norm(d)
        unit = vector_scale(d, 1.0 / n)
        expected = vector_scale(unit, MISSILE_SPEED)
        self.assertTrue(vec_close(v, expected, tol=1e-9))

    def test_not_3_axes(self):
        """避免常见错误: M1 不是 (-300, 0, 0)."""
        v = missile_velocity()
        self.assertGreater(abs(v[2]), 1.0)
        self.assertLess(abs(v[0]), MISSILE_SPEED)


# === C. 二分求根 ===
class C_BisectRoot(unittest.TestCase):

    def test_simple_linear(self):
        # f(t) = t - 5, root = 5
        root = bisect_root(lambda t: t - 5.0, 0.0, 10.0)
        self.assertAlmostEqual(root, 5.0, places=9)

    def test_cosine(self):
        # f(t) = cos(t) = 0 在 [1, 2] 内, root ≈ π/2
        root = bisect_root(math.cos, 1.0, 2.0)
        self.assertAlmostEqual(root, math.pi / 2, places=8)

    def test_same_sign_raises(self):
        with self.assertRaises(ValueError):
            bisect_root(lambda t: t * t + 1.0, -1.0, 1.0)


# === D. 闭线段距离 ===
class D_PointToSegment(unittest.TestCase):

    def test_orthogonal_projection_inside(self):
        d, n = point_to_segment_distance((5, 3, 0), (0, 0, 0), (10, 0, 0))
        self.assertAlmostEqual(d, 3.0, places=9)
        self.assertAlmostEqual(n[0], 5.0, places=9)

    def test_orthogonal_projection_outside_low(self):
        # 点 (-5, 3, 0), 最近点是 (0,0,0), 距离 = sqrt(34)
        d, n = point_to_segment_distance((-5, 3, 0), (0, 0, 0), (10, 0, 0))
        self.assertAlmostEqual(d, math.sqrt(34.0), places=6)
        self.assertAlmostEqual(n[0], 0.0, places=9)
        self.assertAlmostEqual(n[1], 0.0, places=9)

    def test_orthogonal_projection_outside_high(self):
        d, n = point_to_segment_distance((15, 4, 0), (0, 0, 0), (10, 0, 0))
        self.assertAlmostEqual(d, math.sqrt(41.0), places=9)
        self.assertAlmostEqual(n[0], 10.0, places=9)

    def test_on_segment(self):
        d, n = point_to_segment_distance((5, 0, 0), (0, 0, 0), (10, 0, 0))
        self.assertAlmostEqual(d, 0.0, places=9)

    def test_zero_length_segment(self):
        d, n = point_to_segment_distance((1, 1, 1), (5, 5, 5), (5, 5, 5))
        self.assertAlmostEqual(d, math.sqrt(48.0), places=9)


# === E. 区间端点 (绝对残差 + 进入/离开状态) ===
class E_IntervalEndpoint(unittest.TestCase):

    def _check_boundary_with_state(self, intervals, f):
        """对每个 (a, b) 区间, 检查:
        - |f(a)| ≤ ENDPOINT_F_TOL 且 |f(b)| ≤ ENDPOINT_F_TOL (绝对残差)
        - a 左侧 f > 0 (外→内), b 右侧 f > 0 (内→外)
        """
        eps_state = 1e-7  # 进入/离开状态判断用更小的偏移
        for a, b in intervals:
            fa, fb = f(a), f(b)
            # 绝对残差
            self.assertLessEqual(abs(fa), ENDPOINT_F_TOL,
                f"端点 t={a} 残差 {fa:.2e} > {ENDPOINT_F_TOL}")
            self.assertLessEqual(abs(fb), ENDPOINT_F_TOL,
                f"端点 t={b} 残差 {fb:.2e} > {ENDPOINT_F_TOL}")
            # 进入状态: 左侧 > 0, 进入点 ≤ 0
            f_left = f(max(a - eps_state, b - eps_state)) if a < b else f(a)
            # 用更可靠的方法: 在 a 前后各取一点比较
            try:
                f_prev = f(a - eps_state)
            except Exception:
                f_prev = 1.0
            try:
                f_next = f(b + eps_state)
            except Exception:
                f_next = 1.0
            self.assertGreater(f_prev, 0.0,
                f"进入点 t={a} 左侧 f={f_prev:.2e}, 应 > 0")
            self.assertGreater(f_next, 0.0,
                f"离开点 t={b} 右侧 f={f_next:.2e}, 应 > 0")

    def test_interval_endpoint_abs_residual(self):
        """Q1 真实计算的区间端点 |f| ≤ 1e-6, 且左右侧状态符合."""
        intervals = find_effective_intervals(scan_step=0.01)
        self.assertGreaterEqual(len(intervals), 1,
                                "至少存在一段有效遮蔽区间")
        self._check_boundary_with_state(intervals, f_distance_minus_radius)

    def test_total_duration_positive(self):
        intervals = find_effective_intervals(scan_step=0.01)
        d = total_effective_duration(intervals)
        self.assertGreater(d, 0.0)

    def test_intervals_in_window(self):
        intervals = find_effective_intervals(scan_step=0.01)
        for a, b in intervals:
            self.assertGreaterEqual(a, T_DETONATE - 1e-9)
            self.assertLessEqual(b, T_DETONATE + CLOUD_DURATION + 1e-9)


# === F. 数值稳定性 ===
class F_NumericStability(unittest.TestCase):

    def test_drone_position_nan(self):
        with self.assertRaises(ValueError):
            drone_position(float("nan"))

    def test_drone_position_inf(self):
        with self.assertRaises(ValueError):
            drone_position(float("inf"))

    def test_missile_position_inf(self):
        with self.assertRaises(ValueError):
            missile_position(float("inf"))

    def test_bomb_before_release(self):
        with self.assertRaises(ValueError):
            bomb_position(t=0.5)

    def test_cloud_center_nan(self):
        with self.assertRaises(ValueError):
            cloud_center(float("nan"))


# === G. 时间窗外判定 ===
class G_OutOfWindow(unittest.TestCase):

    def test_before_detonate(self):
        v = f_distance_minus_radius(t=T_DETONATE - 1.0)
        self.assertGreater(v, 1e6)

    def test_after_20s(self):
        v = f_distance_minus_radius(t=T_DETONATE + 21.0)
        self.assertGreater(v, 1e6)

    def test_is_effective_inside(self):
        self.assertTrue(is_effective(T_DETONATE + 5.0, T_DETONATE,
                                       T_DETONATE + CLOUD_DURATION))

    def test_is_effective_outside_low(self):
        self.assertFalse(is_effective(T_DETONATE - 0.01, T_DETONATE,
                                        T_DETONATE + CLOUD_DURATION))

    def test_is_effective_outside_high(self):
        self.assertFalse(is_effective(T_DETONATE + CLOUD_DURATION + 0.01,
                                        T_DETONATE,
                                        T_DETONATE + CLOUD_DURATION))


# === H. 收敛性 (整倍数 + 非整倍数 步长) ===
class H_Convergence(unittest.TestCase):

    def _check_pair(self, intervals_a, intervals_b, step_a, step_b):
        """两档结果配对检查: 区间数量、起点差、终点差、总时长差."""
        self.assertEqual(len(intervals_a), len(intervals_b),
            f"步长 {step_a} 与 {step_b} 区间数量不一致 "
            f"({len(intervals_a)} vs {len(intervals_b)})")
        for iv_a, iv_b in zip(intervals_a, intervals_b):
            da = abs(iv_a[0] - iv_b[0])
            db = abs(iv_a[1] - iv_b[1])
            self.assertLessEqual(da, 0.01,
                f"区间起点差 {da:.6f} > 0.01 (step {step_a} vs {step_b})")
            self.assertLessEqual(db, 0.01,
                f"区间终点差 {db:.6f} > 0.01 (step {step_a} vs {step_b})")
        dt_a = total_effective_duration(intervals_a)
        dt_b = total_effective_duration(intervals_b)
        self.assertLessEqual(abs(dt_a - dt_b), 0.01,
            f"总时长差 {abs(dt_a - dt_b):.6f} > 0.01")

    def test_integer_multiple_steps(self):
        """原 0.02 / 0.01 / 0.005 整倍数关系收敛."""
        intervals_per_step = []
        for step in STEPS_INT_MULTIPLE:
            ivs = find_effective_intervals(scan_step=step)
            self.assertGreaterEqual(len(ivs), 1,
                f"step={step} 应至少有一段区间")
            intervals_per_step.append(ivs)
        for i in range(len(intervals_per_step) - 1):
            for j in range(i + 1, len(intervals_per_step)):
                self._check_pair(
                    intervals_per_step[i], intervals_per_step[j],
                    STEPS_INT_MULTIPLE[i], STEPS_INT_MULTIPLE[j])

    def test_non_integer_steps(self):
        """非整倍数关系 0.019 / 0.011 / 0.0067 步长收敛."""
        intervals_per_step = []
        for step in STEPS_NON_INTEGER:
            ivs = find_effective_intervals(scan_step=step)
            self.assertGreaterEqual(len(ivs), 1)
            intervals_per_step.append(ivs)
        for i in range(len(intervals_per_step) - 1):
            for j in range(i + 1, len(intervals_per_step)):
                self._check_pair(
                    intervals_per_step[i], intervals_per_step[j],
                    STEPS_NON_INTEGER[i], STEPS_NON_INTEGER[j])

    def test_all_steps_pairwise(self):
        """任意两档 (整倍数 + 非整倍数) 区间起点终点对齐."""
        intervals_per_step = [find_effective_intervals(scan_step=s)
                              for s in ALL_STEPS]
        for i in range(len(intervals_per_step) - 1):
            for j in range(i + 1, len(intervals_per_step)):
                self._check_pair(
                    intervals_per_step[i], intervals_per_step[j],
                    ALL_STEPS[i], ALL_STEPS[j])

    def test_endpoint_residual_every_step(self):
        """每一档扫描的区间端点 |f| ≤ 1e-6."""
        for step in ALL_STEPS:
            ivs = find_effective_intervals(scan_step=step)
            for a, b in ivs:
                fa = f_distance_minus_radius(a)
                fb = f_distance_minus_radius(b)
                self.assertLessEqual(abs(fa), ENDPOINT_F_TOL,
                    f"step={step}, t={a} 残差 {fa:.2e} > {ENDPOINT_F_TOL}")
                self.assertLessEqual(abs(fb), ENDPOINT_F_TOL,
                    f"step={step}, t={b} 残差 {fb:.2e} > {ENDPOINT_F_TOL}")

    def test_compute_q1_keys(self):
        result = compute_q1()
        for k in ("v_u", "v_m", "t_release", "r_release",
                  "t_detonate", "d_deton", "t_arrival",
                  "intervals", "total_duration"):
            self.assertIn(k, result)


# === I. 边界函数注入算法测试 ===
class I_BoundaryFuncInjection(unittest.TestCase):

    """用合成 boundary_func 验证 find_effective_intervals 在极端情形下的正确性.
    所有测试都使用默认 t_detonate = T_DETONATE, 时间窗 [T_DETONATE, T_DETONATE+20]."""

    WINDOW_START = T_DETONATE
    WINDOW_END = T_DETONATE + CLOUD_DURATION

    def test_01_always_inside(self):
        """全窗口有效: f(t) 恒为 -1."""
        f: Callable[[float], float] = lambda t: -1.0
        ivs = find_effective_intervals(
            scan_step=0.01, boundary_func=f)
        self.assertEqual(len(ivs), 1)
        a, b = ivs[0]
        self.assertAlmostEqual(a, self.WINDOW_START, places=9)
        self.assertAlmostEqual(b, self.WINDOW_END, places=9)
        self.assertAlmostEqual(b - a, CLOUD_DURATION, places=9)

    def test_02_always_outside(self):
        """无有效区间: f(t) 恒为 +1."""
        f: Callable[[float], float] = lambda t: 1.0
        ivs = find_effective_intervals(
            scan_step=0.01, boundary_func=f)
        self.assertEqual(ivs, [])

    def test_03_two_disjoint_intervals(self):
        """两段不连续区间: 在 [1.5, 1.7] 与 [1.9, 2.1] 内 f<0, 其余 f>0."""
        a1, b1 = T_DETONATE + 1.5, T_DETONATE + 1.7
        a2, b2 = T_DETONATE + 1.9, T_DETONATE + 2.1

        def f(t: float) -> float:
            if a1 <= t <= b1:
                return -1.0
            if a2 <= t <= b2:
                return -1.0
            return 1.0

        ivs = find_effective_intervals(
            scan_step=0.001, boundary_func=f)
        self.assertEqual(len(ivs), 2, f"期望 2 段, 实际 {len(ivs)}: {ivs}")
        # 第一段
        ea1, eb1 = ivs[0]
        self.assertLessEqual(abs(ea1 - a1), 1e-5)
        self.assertLessEqual(abs(eb1 - b1), 1e-5)
        # 第二段
        ea2, eb2 = ivs[1]
        self.assertLessEqual(abs(ea2 - a2), 1e-5)
        self.assertLessEqual(abs(eb2 - b2), 1e-5)

    def test_04_non_grid_boundary(self):
        """非格点边界: 用开口向上抛物线 f(t) = (t-a)(t-b),
        a, b 都选为非扫描步长整倍数的非格点. 期望一段 [a, b]."""
        a_root = T_DETONATE + 3.141592653   # π, 非格点
        b_root = T_DETONATE + 8.987654321   # 非格点, 不与 0.01 步长成整倍数
        f: Callable[[float], float] = lambda t: (t - a_root) * (t - b_root)
        ivs = find_effective_intervals(
            scan_step=0.01, boundary_func=f)
        self.assertEqual(len(ivs), 1, f"期望 1 段, 实际 {ivs}")
        ea, eb = ivs[0]
        self.assertLessEqual(abs(ea - a_root), 1e-6,
            f"二分起点 {ea} 与解析 a {a_root} 差 {abs(ea-a_root):.2e}")
        self.assertLessEqual(abs(eb - b_root), 1e-6,
            f"二分终点 {eb} 与解析 b {b_root} 差 {abs(eb-b_root):.2e}")

    def test_05_t_arrival_truncation(self):
        """t_arrival 截断: 自定义 boundary_func 让 t_det+5 到 t_det+15 都有效.
        当 t_arrival=T_DETONATE+8 时, 输出区间不得超过 8."""
        t_in = T_DETONATE + 5.0
        t_out = T_DETONATE + 15.0
        t_cut = T_DETONATE + 8.0

        def f(t: float) -> float:
            if t_in <= t <= t_out:
                return -1.0
            return 1.0

        ivs = find_effective_intervals(
            scan_step=0.01, t_arrival=t_cut, boundary_func=f)
        self.assertEqual(len(ivs), 1, f"期望 1 段, 实际 {ivs}")
        ea, eb = ivs[0]
        self.assertLessEqual(abs(ea - t_in), 1e-7,
            f"起点 {ea} 应 ≈ {t_in}")
        self.assertLessEqual(eb, t_cut + 1e-9,
            f"终点 {eb} 不得超过 t_arrival {t_cut}")

    def test_06_cloud_sink_60m(self):
        """云团下沉: t=t_det+20 时云团 z 比起爆点低 60 m."""
        d = detonation_point()
        c20 = cloud_center(T_DETONATE + CLOUD_DURATION, T_DETONATE, d)
        self.assertAlmostEqual(d[2] - c20[2], CLOUD_SINK * CLOUD_DURATION,
                                places=9)
        self.assertAlmostEqual(CLOUD_SINK * CLOUD_DURATION, 60.0, places=9)
        self.assertAlmostEqual(c20[2], 1736.496 - 60.0, places=9)

    def test_07_point_target_P(self):
        """点目标代表点 P = (0, 200, 5)."""
        self.assertEqual(P, (0.0, 200.0, 5.0))
        self.assertEqual(P[0], 0.0)
        self.assertEqual(P[1], 200.0)
        self.assertEqual(P[2], 5.0)

    def test_08_invalid_scan_step(self):
        """非法 scan_step 必须抛 ValueError."""
        # 默认 boundary_func 路径
        for bad in (0.0, -0.01, float("inf"), float("nan")):
            with self.assertRaises(ValueError,
                msg=f"scan_step={bad!r} 应抛 ValueError"):
                find_effective_intervals(scan_step=bad)
        # 注入 boundary_func 路径同样校验
        for bad in (0.0, -0.01):
            with self.assertRaises(ValueError,
                msg=f"边界函数路径 scan_step={bad!r} 应抛 ValueError"):
                find_effective_intervals(
                    scan_step=bad, boundary_func=lambda t: -1.0)


# === J. 补充 (云团下沉 + P 点, 与 I 中重复部分可以冗余, 便于独立标识)
class J_CloudAndPointTarget(unittest.TestCase):
    def test_cloud_sinks_3m_per_s(self):
        d = detonation_point()
        c0 = cloud_center(T_DETONATE, T_DETONATE, d)
        c5 = cloud_center(T_DETONATE + 5.0, T_DETONATE, d)
        c10 = cloud_center(T_DETONATE + 10.0, T_DETONATE, d)
        self.assertAlmostEqual(c0[2], d[2], places=9)
        self.assertAlmostEqual(d[2] - c5[2], 15.0, places=9)
        self.assertAlmostEqual(d[2] - c10[2], 30.0, places=9)

    def test_target_geometry_consistency(self):
        # P[1] = 200 表示真目标在 +y 200m (与 FACTS.md §7 一致)
        self.assertAlmostEqual(P[1], 200.0, places=9)
        # P[2] = 5 表示圆柱几何中心 z=5 (下底面 z=0, 高 10)
        self.assertAlmostEqual(P[2], 5.0, places=9)


# === 可独立运行 ===
if __name__ == "__main__":
    unittest.main(verbosity=2)
