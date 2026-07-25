"""Q1 点目标最小可运行基线 - 单元测试 (BASELINE / EXPERIMENTAL)

只使用 Python 标准库 + unittest.
测试分组:
- A. 手算验证 (R/D 坐标, 容忍 ≤1e-6 m)
- B. M1 速度方向与大小
- C. 二分求根精度
- D. 闭线段距离 (端点、内点、超界、退化)
- E. 区间端点正确
- F. 数值稳定性 (NaN/Inf 输入)
- G. 时间窗外判定
- H. 收敛性 (3 个扫描步长结果稳定)
"""

from __future__ import annotations

import math
import os
import sys
import unittest

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


# === 工具断言 ===
def vec_close(a, b, tol: float = 1e-9) -> bool:
    return all(abs(a[i] - b[i]) < tol for i in range(3))


# === A. 手算验证 ===
class A_HandCalcVerification(unittest.TestCase):

    def test_release_point_R_17620(self):
        """R = (17620, 0, 1800), 容忍 ≤ 1e-6 m."""
        r = drone_position(T_RELEASE)
        self.assertTrue(vec_close(r, (17620.0, 0.0, 1800.0), tol=1e-6),
                        f"投放点 R={r}")

    def test_detonation_point_D_17188_1736(self):
        """D = (17188, 0, 1736.496), 容忍 ≤ 1e-6 m."""
        d = detonation_point()
        self.assertTrue(vec_close(d, (17188.0, 0.0, 1736.496), tol=1e-6),
                        f"起爆点 D={d}")

    def test_detonate_z_analytic(self):
        """D.z = 1800 - 0.5*9.8*3.6^2 = 1736.496."""
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
        """v_M = (O - M0) / |O - M0| * speed."""
        v = missile_velocity()
        # 显式单位方向
        d = vector_sub(O, M0)
        n = norm(d)
        unit = vector_scale(d, 1.0 / n)
        expected = vector_scale(unit, MISSILE_SPEED)
        self.assertTrue(vec_close(v, expected, tol=1e-9))

    def test_not_3_axes(self):
        """避免常见错误: M1 不是 (-300, 0, 0)."""
        v = missile_velocity()
        self.assertGreater(abs(v[2]), 1.0)
        self.assertLess(abs(v[0]), MISSILE_SPEED)  # 不是 300 而是小一点


# === C. 二分求根 ===
class C_BisectRoot(unittest.TestCase):

    def test_simple_linear(self):
        # f(t) = t - 5, root = 5
        root = bisect_root(lambda t: t - 5.0, 0.0, 10.0)
        self.assertAlmostEqual(root, 5.0, places=9)

    def test_cosine(self):
        # f(t) = cos(t) = 0 在 [1, 2] 内, root ≈ π/2 ≈ 1.570796327
        root = bisect_root(math.cos, 1.0, 2.0)
        self.assertAlmostEqual(root, math.pi / 2, places=8)

    def test_same_sign_raises(self):
        with self.assertRaises(ValueError):
            bisect_root(lambda t: t * t + 1.0, -1.0, 1.0)


# === D. 闭线段距离 ===
class D_PointToSegment(unittest.TestCase):

    def test_orthogonal_projection_inside(self):
        # 线段 (0,0,0)→(10,0,0), 点 (5, 3, 0) → 距离 3, 最近点 (5,0,0)
        d, n = point_to_segment_distance((5, 3, 0), (0, 0, 0), (10, 0, 0))
        self.assertAlmostEqual(d, 3.0, places=9)
        self.assertAlmostEqual(n[0], 5.0, places=9)

    def test_orthogonal_projection_outside_low(self):
        # 点 (-5, 3, 0), 最近点是 (0,0,0), 距离 = sqrt(25 + 9) = sqrt(34)
        d, n = point_to_segment_distance((-5, 3, 0), (0, 0, 0), (10, 0, 0))
        self.assertAlmostEqual(d, math.sqrt(34.0), places=6)
        self.assertAlmostEqual(n[0], 0.0, places=9)
        self.assertAlmostEqual(n[1], 0.0, places=9)

    def test_orthogonal_projection_outside_high(self):
        # 点 (15, 4, 0), 最近点是 (10,0,0), 距离 = sqrt(25+16) = sqrt(41)
        d, n = point_to_segment_distance((15, 4, 0), (0, 0, 0), (10, 0, 0))
        self.assertAlmostEqual(d, math.sqrt(41.0), places=9)
        self.assertAlmostEqual(n[0], 10.0, places=9)

    def test_on_segment(self):
        # 点 (5, 0, 0), 距离 0
        d, n = point_to_segment_distance((5, 0, 0), (0, 0, 0), (10, 0, 0))
        self.assertAlmostEqual(d, 0.0, places=9)

    def test_zero_length_segment(self):
        # 退化: 线段 (5,5,5)→(5,5,5), 点 (1,1,1), 距离 sqrt(48)
        d, n = point_to_segment_distance((1, 1, 1), (5, 5, 5), (5, 5, 5))
        self.assertAlmostEqual(d, math.sqrt(48.0), places=9)


# === E. 区间端点正确 ===
class E_IntervalCorrectness(unittest.TestCase):

    def test_interval_boundary_d_equals_10(self):
        """端点应是 d(t) ≈ 10 (从外向内进入 / 从内向外离开)."""
        intervals = find_effective_intervals(scan_step=0.01)
        self.assertGreaterEqual(len(intervals), 1,
                                "至少存在一段有效遮蔽区间")
        for a, b in intervals:
            da = f_distance_minus_radius(a)
            db = f_distance_minus_radius(b)
            self.assertLessEqual(da, 1e-6,
                                 f"区间端点 t={a} 处 d-R = {da}, 应 ≤ 0 (允许 1e-6 偏差)")
            self.assertLessEqual(db, 1e-6,
                                 f"区间端点 t={b} 处 d-R = {db}, 应 ≤ 0")

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
            bomb_position(t=0.5)  # 早于 T_RELEASE

    def test_cloud_center_nan(self):
        with self.assertRaises(ValueError):
            cloud_center(float("nan"))


# === G. 时间窗外判定 ===
class G_OutOfWindow(unittest.TestCase):

    def test_before_detonate(self):
        """起爆前返回大正值."""
        v = f_distance_minus_radius(t=T_DETONATE - 1.0)
        self.assertGreater(v, 1e6)

    def test_after_20s(self):
        """起爆 + 21 秒外返回大正值."""
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


# === H. 收敛性 ===
class H_Convergence(unittest.TestCase):

    def test_three_steps_stable(self):
        """3 步收敛: max |Δt| ≤ 0.01 s."""
        ds = []
        intervals_list = []
        for step in SCAN_STEPS:
            intervals = find_effective_intervals(scan_step=step)
            d = total_effective_duration(intervals)
            ds.append(d)
            intervals_list.append(intervals)

        # 三档结果两两比较
        for i in range(len(ds) - 1):
            for j in range(i + 1, len(ds)):
                diff = abs(ds[i] - ds[j])
                self.assertLessEqual(diff, 0.01,
                                     f"扫描 {SCAN_STEPS[i]} 与 {SCAN_STEPS[j]} "
                                     f"总时长相差 {diff:.6f} > 0.01")
        # 同时验证区间端点的稳健性 (允许最大差 0.05s 端点漂移)
        if all(intervals_list):
            a0, b0 = intervals_list[0][0]
            for iv in intervals_list[1:]:
                a, b = iv[0]
                self.assertLessEqual(abs(a0 - a), 0.05,
                                     f"区间起点漂移 {abs(a0-a):.6f}")
                self.assertLessEqual(abs(b0 - b), 0.05,
                                     f"区间终点漂移 {abs(b0-b):.6f}")

    def test_compute_q1_keys(self):
        result = compute_q1()
        for k in ("v_u", "v_m", "t_release", "r_release",
                  "t_detonate", "d_deton", "t_arrival",
                  "intervals", "total_duration"):
            self.assertIn(k, result)


# === 可独立运行 ===
if __name__ == "__main__":
    unittest.main(verbosity=2)
