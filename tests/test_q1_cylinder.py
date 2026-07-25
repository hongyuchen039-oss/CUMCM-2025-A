"""tests/test_q1_cylinder.py — TASK_003 完整圆柱遮蔽判定 单元测试.

所有数值参考 (PR #3 修复后真实输出):
- 完整圆柱 fine: 区间 (~8.055xxx, 9.448088) s, 总时长 (~1.3923xx) s
- 空间收敛 medium vs fine 起点/终点/总时长差均 < 阈值
- 时间收敛三档完全一致
- 区间端点 max |f_cylinder| <= 1e-4
- coverage_ratio 在 [0, 1], 严格遮蔽时 = 1 形成平台
- margin 局部加密后达到 (约 5.x m)

等级: FULL-CYLINDER CANDIDATE / EXPERIMENTAL.
本文件不预设测试总数, 实际数量以 unittest 输出为准.
"""

from __future__ import annotations

import math
import os
import sys
import unittest
import xml.etree.ElementTree as ET
from typing import List, Sequence, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.q1_baseline import (
    CLOUD_RADIUS, CLOUD_DURATION, T_DETONATE, M0, P,
    cloud_center, missile_position, compute_q1,
)
from src.q1_cylinder import (
    R_T, H_T,
    SAMPLE_GRADES, TIME_STEPS, EPS_VISIBLE, DIAG_STEP,
    SPATIAL_THR_START, SPATIAL_THR_END, SPATIAL_THR_TOTAL,
    SPATIAL_THR_COVERAGE, SPATIAL_THR_MARGIN, SPATIAL_THR_RESIDUAL,
    TEMPORAL_THR_START, TEMPORAL_THR_END, TEMPORAL_THR_TOTAL, TEMPORAL_THR_RESIDUAL,
    T_WINDOW_START, T_WINDOW_END,
    SurfaceSample, generate_cylinder_samples, verify_sample_geometry,
    sample_is_visible, visible_samples,
    sample_is_occluded,
    evaluate_occlusion_geometry, evaluate_cylinder_state, CylinderState,
    strict_boundary_value,
    find_strict_intervals,
    run_temporal_convergence, run_spatial_convergence,
    check_temporal_convergence, check_spatial_convergence,
    compare_point_and_cylinder,
    write_comparison_svg, build_time_series,
    refine_margin_max, coverage_plateau,
)


# =============================================================================
#  A 组 — 圆柱采样几何
# =============================================================================
class ACylinderSamplingGeometry(unittest.TestCase):

    def test_a01_side_cell_count(self):
        params = SAMPLE_GRADES["medium"]
        samps = generate_cylinder_samples(**params)
        n_side = sum(1 for s in samps if s.surface_type == "side")
        self.assertEqual(n_side, params["side_theta"] * params["side_z"])

    def test_a02_caps_cell_count(self):
        params = SAMPLE_GRADES["medium"]
        samps = generate_cylinder_samples(**params)
        n_top = sum(1 for s in samps if s.surface_type == "top")
        n_bot = sum(1 for s in samps if s.surface_type == "bottom")
        self.assertEqual(n_top, params["cap_r"] * params["cap_theta"])
        self.assertEqual(n_bot, params["cap_r"] * params["cap_theta"])

    def test_a03_total_weight_matches_geometry(self):
        for grade, params in SAMPLE_GRADES.items():
            samps = generate_cylinder_samples(**params)
            geo = verify_sample_geometry(samps)
            expected = 2.0 * math.pi * R_T * H_T + 2.0 * math.pi * R_T ** 2
            self.assertAlmostEqual(geo["total_weight"], expected, places=8,
                                    msg=f"grade={grade}")

    def test_a04_cell_centers_avoid_junction(self):
        samps = generate_cylinder_samples(side_theta=4, side_z=4, cap_r=2, cap_theta=4)
        for s in samps:
            if s.surface_type == "side":
                self.assertGreater(s.point[2], 0.0)
                self.assertLess(s.point[2], H_T)

    def test_a05_normals_are_unit_vectors(self):
        samps = generate_cylinder_samples(side_theta=8, side_z=4, cap_r=2, cap_theta=8)
        for s in samps:
            mag = math.sqrt(sum(c * c for c in s.normal))
            self.assertAlmostEqual(mag, 1.0, places=10)

    def test_a06_side_weight_matches_formula(self):
        params = SAMPLE_GRADES["medium"]
        samps = generate_cylinder_samples(**params)
        w_side_expected = 2.0 * math.pi * R_T * H_T / (params["side_theta"] * params["side_z"])
        for s in samps:
            if s.surface_type == "side":
                self.assertAlmostEqual(s.weight, w_side_expected, places=12)

    def test_a07_cap_weight_matches_formula(self):
        params = SAMPLE_GRADES["medium"]
        samps = generate_cylinder_samples(**params)
        w_cap_expected = math.pi * R_T ** 2 / (params["cap_r"] * params["cap_theta"])
        for s in samps:
            if s.surface_type in ("top", "bottom"):
                self.assertAlmostEqual(s.weight, w_cap_expected, places=12)

    def test_a08_axis_alignment(self):
        samps = generate_cylinder_samples(side_theta=8, side_z=4, cap_r=2, cap_theta=8)
        for s in samps:
            if s.surface_type == "side":
                dot = sum(a * b for a, b in zip(s.normal, (0.0, 0.0, 1.0)))
                self.assertAlmostEqual(dot, 0.0, places=12)
            elif s.surface_type == "top":
                self.assertEqual(s.normal, (0.0, 0.0, 1.0))
            elif s.surface_type == "bottom":
                self.assertEqual(s.normal, (0.0, 0.0, -1.0))

    def test_a09_invalid_params_raise(self):
        with self.assertRaises(ValueError):
            generate_cylinder_samples(side_theta=0, side_z=16, cap_r=8, cap_theta=96)
        with self.assertRaises(ValueError):
            generate_cylinder_samples(side_theta=96, side_z=16, cap_r=8, cap_theta=-1)
        with self.assertRaises(ValueError):
            generate_cylinder_samples(side_theta=1.5, side_z=16, cap_r=8, cap_theta=96)


# =============================================================================
#  B 组 — 可见性 (保守规则 + 人工 ±x 几何 + EPS 校验)
# =============================================================================
class BVisibility(unittest.TestCase):

    def setUp(self):
        self.plus_x = SurfaceSample(point=(7.0, 200.0, 5.0),
                                     normal=(1.0, 0.0, 0.0),
                                     weight=1.0, surface_type="side")
        self.minus_x = SurfaceSample(point=(-7.0, 200.0, 5.0),
                                      normal=(-1.0, 0.0, 0.0),
                                      weight=1.0, surface_type="side")
        self.plus_y = SurfaceSample(point=(0.0, 207.0, 5.0),
                                     normal=(0.0, 1.0, 0.0),
                                     weight=1.0, surface_type="side")
        self.minus_y = SurfaceSample(point=(0.0, 193.0, 5.0),
                                      normal=(0.0, -1.0, 0.0),
                                      weight=1.0, surface_type="side")

    def test_b01_observer_plus_x_sees_plus_x(self):
        m = (100.0, 200.0, 5.0)
        self.assertTrue(sample_is_visible(self.plus_x, m))
        self.assertFalse(sample_is_visible(self.minus_x, m))

    def test_b02_observer_minus_x_sees_minus_x(self):
        m = (-100.0, 200.0, 5.0)
        self.assertFalse(sample_is_visible(self.plus_x, m))
        self.assertTrue(sample_is_visible(self.minus_x, m))

    def test_b03_observer_plus_y_sees_plus_y(self):
        m = (0.0, 300.0, 5.0)
        self.assertTrue(sample_is_visible(self.plus_y, m))
        self.assertFalse(sample_is_visible(self.minus_y, m))

    def test_b04_observer_minus_y_sees_minus_y(self):
        m = (0.0, 100.0, 5.0)
        self.assertFalse(sample_is_visible(self.plus_y, m))
        self.assertTrue(sample_is_visible(self.minus_y, m))

    def test_b05_score_greater_than_eps_visible(self):
        # score = +1 > eps ⇒ visible
        m = (100.0, 200.0, 5.0)
        self.assertTrue(sample_is_visible(self.plus_x, m, eps=0.5))

    def test_b06_score_within_eps_band_visible(self):
        # score = 0.5, eps = 1.0 ⇒ 0.5 >= -1.0 ⇒ visible (旧规则会因 >eps=1 排除)
        m = (107.0, 200.0, 5.0)  # 视线差分 (100,0,0), dot((1,0,0),(100,0,0))=100
        # 实际 score = 100; 改 m 让 score ≈ 0.5
        m = (7.5, 200.0, 5.0)  # M-X = (0.5, 0, 0), dot((1,0,0),(0.5,0,0))=0.5
        self.assertTrue(sample_is_visible(self.plus_x, m, eps=1.0))
        # 当 score = -0.5 (小于 -eps=-1.0 不应; 但 0.5 >= -1 仍可见)
        m = (6.5, 200.0, 5.0)  # score = -0.5
        # -0.5 >= -1.0 ⇒ visible
        self.assertTrue(sample_is_visible(self.plus_x, m, eps=1.0))

    def test_b07_score_less_than_neg_eps_invisible(self):
        # 旧规则因 >eps 排除了 score ≈ 0 的样本; 新规则要求 score < -eps 排除
        # score = -2, eps = 1 ⇒ -2 < -1 ⇒ 不可见
        m = (5.0, 200.0, 5.0)  # M-X = (-2,0,0), score = dot((1,0,0),(-2,0,0))=-2
        self.assertFalse(sample_is_visible(self.plus_x, m, eps=1.0))

    def test_b08_invalid_eps_raises(self):
        m = (100.0, 200.0, 5.0)
        with self.assertRaises(ValueError):
            sample_is_visible(self.plus_x, m, eps=-1.0)
        with self.assertRaises(ValueError):
            sample_is_visible(self.plus_x, m, eps=float("nan"))
        with self.assertRaises(ValueError):
            sample_is_visible(self.plus_x, m, eps=float("inf"))

    def test_b09_visible_samples_filters(self):
        # 观测者在 +x, +y 方向远处: +x 与 +y 侧面可见, -x 与 -y 不可见
        m = (100.0, 300.0, 5.0)
        v = visible_samples([self.plus_x, self.minus_x, self.plus_y, self.minus_y], m)
        self.assertEqual(len(v), 2)
        self.assertIn(self.plus_x, v)
        self.assertIn(self.plus_y, v)

    def test_b10_observer_on_axis_plus_x_visible(self):
        # 轴线上 (+x) 距离很远, 应可见 +x 侧面
        m = (200.0, 200.0, 5.0)
        v = visible_samples([self.plus_x, self.minus_x, self.plus_y, self.minus_y], m)
        self.assertEqual(v, [self.plus_x])


# =============================================================================
#  C 组 — 遮挡 (纯人工几何, M=(0,0,0), X=(10,0,0))
# =============================================================================
class COcclusion(unittest.TestCase):

    def setUp(self):
        self.m = (0.0, 0.0, 0.0)
        self.x = (10.0, 0.0, 0.0)
        self.s = SurfaceSample(point=self.x, normal=(1.0, 0.0, 0.0),
                                weight=1.0, surface_type="side")

    def test_c01_cloud_on_segment_center_occluded(self):
        # C=(5,0,0), 距离 0, radius 任意>0 ⇒ 遮挡
        self.assertTrue(sample_is_occluded(self.s, self.m, (5.0, 0.0, 0.0), radius=10.0))

    def test_c02_cloud_at_y_axis_distance_9_occluded(self):
        # C=(5,9,0), 距离 9 ≤ 10 ⇒ 遮挡
        self.assertTrue(sample_is_occluded(self.s, self.m, (5.0, 9.0, 0.0), radius=10.0))

    def test_c03_cloud_at_y_axis_distance_11_not_occluded(self):
        # C=(5,11,0), 距离 11 > 10 ⇒ 不遮挡
        self.assertFalse(sample_is_occluded(self.s, self.m, (5.0, 11.0, 0.0), radius=10.0))

    def test_c04_cloud_beyond_endpoint_not_occluded_when_radius_small(self):
        # C=(20,0,0), 在延长线上, 闭线段距离 = 10
        # radius < 10 ⇒ 不遮挡; radius = 10 ⇒ 遮挡 (端点闭合)
        self.assertFalse(sample_is_occluded(self.s, self.m, (20.0, 0.0, 0.0), radius=9.0))
        self.assertFalse(sample_is_occluded(self.s, self.m, (20.0, 0.0, 0.0), radius=5.0))
        # 端点距离 10 ⇒ radius=10 正好相等, 遮挡 (≤ radius)
        self.assertTrue(sample_is_occluded(self.s, self.m, (20.0, 0.0, 0.0), radius=10.0))

    def test_c05_invalid_radius_raises(self):
        with self.assertRaises(ValueError):
            sample_is_occluded(self.s, self.m, (5.0, 0.0, 0.0), radius=0.0)
        with self.assertRaises(ValueError):
            sample_is_occluded(self.s, self.m, (5.0, 0.0, 0.0), radius=-1.0)
        with self.assertRaises(ValueError):
            sample_is_occluded(self.s, self.m, (5.0, 0.0, 0.0), radius=float("nan"))
        with self.assertRaises(ValueError):
            sample_is_occluded(self.s, self.m, (5.0, 0.0, 0.0), radius=float("inf"))


# =============================================================================
#  D 组 — 覆盖率 (人工权重)
# =============================================================================
class DCoverage(unittest.TestCase):

    def _weight1(self, x):
        return SurfaceSample(point=x, normal=(1.0, 0.0, 0.0), weight=1.0,
                              surface_type="side")

    def _weight9(self, x):
        return SurfaceSample(point=x, normal=(1.0, 0.0, 0.0), weight=9.0,
                              surface_type="side")

    def test_d01_coverage_in_unit_interval(self):
        for t in (5.1, 7.0, 8.0, 8.5, 9.0, 9.5, 10.0):
            samps = generate_cylinder_samples(**SAMPLE_GRADES["medium"])
            st = evaluate_cylinder_state(t, samps)
            self.assertGreaterEqual(st.coverage_ratio, 0.0)
            self.assertLessEqual(st.coverage_ratio, 1.0)

    def test_d02_coverage_strict_implies_one(self):
        for t in (8.5, 8.8, 9.0):
            samps = generate_cylinder_samples(**SAMPLE_GRADES["medium"])
            st = evaluate_cylinder_state(t, samps)
            if st.strict_occlusion:
                self.assertAlmostEqual(st.coverage_ratio, 1.0, places=6)

    def test_d03_weighted_coverage_one_of_two(self):
        # 人工: M=(20,0,0) 位于样本的 +x 一侧, 两个样本均可见.
        s1 = self._weight1((10.0, 0.0, 0.0))
        s2 = self._weight9((10.0, 0.0, 0.0))  # 同位置不同权重
        # 云团覆盖: C=(10,0,0) 在线段 [m=(20,0,0), X=(10,0,0)] 上, 距离 0 ⇒ 遮挡
        st = evaluate_occlusion_geometry((20.0, 0.0, 0.0), (10.0, 0.0, 0.0),
                                          [s1, s2], radius=10.0)
        self.assertEqual(st.visible_count, 2)
        self.assertEqual(st.coverage_ratio, 1.0)

    def test_d04_weighted_coverage_partial(self):
        # 干净合成的两个样本: m=(20,0,0) 在 +x 一侧
        # s1=(10,0,0), 法向 +x, 权重 1
        # s2=(0,10,0), 法向 +x, 权重 9
        # 两个样本对 m 都可见 (M-X score > -eps)
        m = (20.0, 0.0, 0.0)
        s1 = SurfaceSample(point=(10.0, 0.0, 0.0), normal=(1.0, 0.0, 0.0),
                            weight=1.0, surface_type="side")
        s2 = SurfaceSample(point=(0.0, 10.0, 0.0), normal=(1.0, 0.0, 0.0),
                            weight=9.0, surface_type="side")

        # === Case 1: 仅 s1 遮挡, coverage = 1/10 = 0.1 ===
        # C=(10, 0, 0), radius=3
        # s1: q=(10-20, 0, 0)=(-10, 0, 0), C-m=(-10, 0, 0), 共线, λ=1
        #      N=(10, 0, 0), d=0 ≤ 3 ⇒ 遮挡
        # s2: q=(0-20, 10-0, 0)=(-20, 10, 0), C-m=(-10, 0, 0)
        #      λ=clamp(200/500, 0, 1) = 0.4
        #      N=(20-0.4·20, 0+0.4·10, 0) = (12, 4, 0)
        #      d = |(-10-12-(-10), 0-4-0, 0)| = |(-22+10-12, -4, 0)|
        #      更直接: C-N = (10-12, 0-4, 0) = (-2, -4, 0), |CN|=sqrt(20)≈4.47 > 3 ⇒ 未遮挡
        st1 = evaluate_occlusion_geometry(m, (10.0, 0.0, 0.0), [s1, s2], radius=3.0)
        self.assertEqual(st1.visible_count, 2)
        self.assertEqual(st1.occluded_count, 1)
        self.assertAlmostEqual(st1.coverage_ratio, 0.1, places=9)
        self.assertAlmostEqual(st1.occluded_weight / 10.0, 0.1, places=9)

        # === Case 2: 仅 s2 遮挡, coverage = 9/10 = 0.9 ===
        # C=(0, 10, 0), radius=5
        # s1: q=(-10, 0, 0), C-m=(-20, 10, 0)
        #      λ=clamp(200/100, 0, 1) = 1
        #      N=(10, 0, 0), d=|(−20, 10, 0) − (−10, 0, 0)| = |(−10, 10, 0)| = sqrt(200) ≈ 14.14 > 5 ⇒ 未遮挡
        # s2: q=(-20, 10, 0), C-m=(-20, 10, 0), 共线, λ=1
        #      N=(0, 10, 0), d=0 ≤ 5 ⇒ 遮挡
        st2 = evaluate_occlusion_geometry(m, (0.0, 10.0, 0.0), [s1, s2], radius=5.0)
        self.assertEqual(st2.visible_count, 2)
        self.assertEqual(st2.occluded_count, 1)
        self.assertAlmostEqual(st2.coverage_ratio, 0.9, places=9)
        self.assertAlmostEqual(st2.occluded_weight / 10.0, 0.9, places=9)

        # === Case 3: 两都遮挡, coverage = 1.0 ===
        # C=(5, 5, 0), radius=15
        # s1: C-N: q=(-10, 0, 0), C-m=(-15, 5, 0)
        #      λ=clamp(150/100, 0, 1) = 1
        #      N=(10, 0, 0), d=|(-15-10+15, 5-0-0)|=|(−10, 5, 0)|=sqrt(125)≈11.18 ≤ 15 ⇒ 遮挡
        # s2: q=(-20, 10, 0), C-m=(-15, 5, 0)
        #      λ=clamp((300+50)/500, 0, 1) = 0.7
        #      N=(20-14, 0+7, 0) = (6, 7, 0), d = |(5-6, 5-7, 0)|=|(−1, −2, 0)|=sqrt(5)≈2.24 ≤ 15 ⇒ 遮挡
        st3 = evaluate_occlusion_geometry(m, (5.0, 5.0, 0.0), [s1, s2], radius=15.0)
        self.assertEqual(st3.visible_count, 2)
        self.assertEqual(st3.occluded_count, 2)
        self.assertAlmostEqual(st3.coverage_ratio, 1.0, places=9)

        # === Case 4: 两都不遮挡, coverage = 0 ===
        # C=(100, 100, 100), radius=1
        # s1: q=(-10, 0, 0), C-m=(80, 100, 100)
        #      N=(20, 0, 0) (λ=1 因为 dot=800>q·q=100), d=|(80,100,100)|=sqrt(24864)>1 ⇒ 未遮挡
        # s2: q=(-20, 10, 0), C-m=(80, 100, 100)
        #      λ=clamp((−1600+1000)/500, 0, 1) = clamp(−1.2, 0, 1) = 0
        #      N=(20, 0, 0), d=|(80,100,100)|≈157.7 > 1 ⇒ 未遮挡
        st4 = evaluate_occlusion_geometry(m, (100.0, 100.0, 100.0), [s1, s2], radius=1.0)
        self.assertEqual(st4.visible_count, 2)
        self.assertEqual(st4.occluded_count, 0)
        self.assertAlmostEqual(st4.coverage_ratio, 0.0, places=9)

    def test_d05_no_visible_raises(self):
        # m 在 -x 方向 (50,0,0); 样本在 +x (100,0,0) 法向 +x; M-X=(-50,0,0), score=-50 < -eps
        s1 = SurfaceSample(point=(100.0, 0.0, 0.0), normal=(1.0, 0.0, 0.0),
                            weight=1.0, surface_type="side")
        with self.assertRaises(ValueError):
            evaluate_occlusion_geometry((50.0, 0.0, 0.0), (5.0, 0.0, 0.0),
                                          [s1], radius=10.0)

    def test_d06_empty_samples_raises(self):
        with self.assertRaises(ValueError):
            evaluate_occlusion_geometry((0.0, 0.0, 0.0), (5.0, 0.0, 0.0),
                                          [], radius=10.0)


# =============================================================================
#  E 组 — 严格裕量
# =============================================================================
class EStrictMargin(unittest.TestCase):

    def test_e01_margin_equals_radius_minus_max_d(self):
        samps = generate_cylinder_samples(**SAMPLE_GRADES["medium"])
        for t in (5.1, 7.0, 8.0, 8.5, 9.0, 9.5, 10.0):
            st = evaluate_cylinder_state(t, samps)
            if math.isfinite(st.max_visible_distance):
                self.assertAlmostEqual(st.strict_margin,
                                       CLOUD_RADIUS - st.max_visible_distance,
                                       places=9)

    def test_e02_strict_iff_margin_nonneg(self):
        samps = generate_cylinder_samples(**SAMPLE_GRADES["medium"])
        for t in (5.1, 7.0, 8.0, 8.5, 9.0, 9.5, 10.0):
            st = evaluate_cylinder_state(t, samps)
            self.assertEqual(st.strict_occlusion, st.strict_margin >= 0.0)

    def test_e03_worst_point_matches_max_distance(self):
        samps = generate_cylinder_samples(**SAMPLE_GRADES["medium"])
        from src.q1_baseline import point_to_segment_distance
        for t in (5.1, 7.0, 8.0, 8.5, 9.0, 9.5, 10.0):
            st = evaluate_cylinder_state(t, samps)
            if st.worst_sample_point is None:
                continue
            d, _ = point_to_segment_distance(cloud_center(t),
                                              missile_position(t),
                                              st.worst_sample_point)
            self.assertAlmostEqual(d, st.max_visible_distance, places=9)

    def test_e04_strict_implies_worst_occluded(self):
        samps = generate_cylinder_samples(**SAMPLE_GRADES["medium"])
        for t in (8.5, 8.8, 9.0):
            st = evaluate_cylinder_state(t, samps)
            if st.strict_occlusion:
                # worst sample 也必被遮
                self.assertLessEqual(st.max_visible_distance,
                                     CLOUD_RADIUS + 1e-9)

    def test_e05_no_visible_raises_in_window(self):
        # 时间窗内 m 进入圆柱 → visible_count == 0
        # 用 m 位于圆柱几何中心 (0, 200, 5), 没有法向指向它的样本
        samps = generate_cylinder_samples(**SAMPLE_GRADES["medium"])
        # 我们用轨迹回调注入让 m 出现在 (0, 200, 5)
        def missile_at_center(t):
            return (0.0, 200.0, 5.0)
        with self.assertRaises(ValueError):
            evaluate_cylinder_state(8.5, samps,
                                     missile_position_fn=missile_at_center)

    def test_e06_out_of_window_no_visible_no_raise(self):
        # 时间窗外: 返回 sentinel, 不抛 ValueError
        samps = generate_cylinder_samples(**SAMPLE_GRADES["medium"])
        st = evaluate_cylinder_state(0.0, samps)
        self.assertFalse(st.strict_occlusion)
        self.assertEqual(st.strict_margin, -float("inf"))


# =============================================================================
#  F 组 — 区间包装函数 (find_strict_intervals 注入与异常)
# =============================================================================
class FIntervalWrapper(unittest.TestCase):

    def _minimal_samples(self):
        # 一个简单可见侧面样本
        return [SurfaceSample(point=(10.0, 0.0, 0.0), normal=(1.0, 0.0, 0.0),
                               weight=1.0, surface_type="side")]

    def test_f01_full_window_effective(self):
        samples = self._minimal_samples()
        # f <= 0 (例如 -1) ⇒ 全窗口有效
        bf = lambda t: -1.0
        ivs = find_strict_intervals(samples, scan_step=0.01,
                                     window_start=T_DETONATE,
                                     window_end=T_WINDOW_END,
                                     boundary_func=bf)
        self.assertEqual(len(ivs), 1)
        self.assertAlmostEqual(ivs[0][0], T_DETONATE, places=9)
        self.assertAlmostEqual(ivs[0][1], T_WINDOW_END, places=9)

    def test_f02_zero_window_effective(self):
        samples = self._minimal_samples()
        bf = lambda t: 1.0
        ivs = find_strict_intervals(samples, scan_step=0.01,
                                     window_start=T_DETONATE,
                                     window_end=T_WINDOW_END,
                                     boundary_func=bf)
        self.assertEqual(ivs, [])

    def test_f03_single_non_grid_interval(self):
        samples = self._minimal_samples()
        # 故意选非格点
        T0 = T_DETONATE
        a, b = T0 + math.pi, T0 + math.pi + 1.5  # pi 不在 0.01 网格上
        bf = lambda t: -1.0 if a <= t <= b else 1.0
        ivs = find_strict_intervals(samples, scan_step=0.01,
                                     window_start=T0, window_end=T0 + 20.0,
                                     boundary_func=bf)
        self.assertEqual(len(ivs), 1)
        self.assertAlmostEqual(ivs[0][0], a, places=6)
        self.assertAlmostEqual(ivs[0][1], b, places=6)

    def test_f04_two_disjoint_intervals(self):
        samples = self._minimal_samples()
        T0 = T_DETONATE
        a1, b1 = T0 + 1.0, T0 + 3.0
        a2, b2 = T0 + 8.0, T0 + 10.0
        def bf(t):
            if a1 <= t <= b1 or a2 <= t <= b2:
                return -1.0
            return 1.0
        ivs = find_strict_intervals(samples, scan_step=0.05,
                                     window_start=T0, window_end=T0 + 20.0,
                                     boundary_func=bf)
        self.assertEqual(len(ivs), 2)

    def test_f05_immediate_start_effective(self):
        samples = self._minimal_samples()
        T0 = T_DETONATE
        bf = lambda t: -1.0 if t >= T0 else 1.0
        ivs = find_strict_intervals(samples, scan_step=0.01,
                                     window_start=T0, window_end=T0 + 5.0,
                                     boundary_func=bf)
        self.assertEqual(len(ivs), 1)
        self.assertAlmostEqual(ivs[0][0], T0, places=9)
        self.assertAlmostEqual(ivs[0][1], T0 + 5.0, places=9)

    def test_f06_effective_through_end(self):
        samples = self._minimal_samples()
        T0 = T_DETONATE
        bf = lambda t: -1.0 if t <= T0 + 5.0 else 1.0
        ivs = find_strict_intervals(samples, scan_step=0.01,
                                     window_start=T0, window_end=T0 + 5.0,
                                     boundary_func=bf)
        self.assertEqual(len(ivs), 1)
        self.assertAlmostEqual(ivs[0][0], T0, places=6)
        # 终点二分收敛到 BISECT_TOL 量级, 放宽到 places=6
        self.assertAlmostEqual(ivs[0][1], T0 + 5.0, places=6)

    def test_f07_t_arrival_truncates(self):
        samples = self._minimal_samples()
        T0 = T_DETONATE
        bf = lambda t: -1.0
        ivs = find_strict_intervals(samples, scan_step=0.05,
                                     window_start=T0, window_end=T0 + 20.0,
                                     t_arrival=T0 + 8.0,
                                     boundary_func=bf)
        self.assertEqual(len(ivs), 1)
        self.assertAlmostEqual(ivs[0][1], T0 + 8.0, places=9)

    def test_f08_invalid_scan_step_raises(self):
        samples = self._minimal_samples()
        from src.q1_baseline import find_effective_intervals
        # 非正值 / NaN / Inf 都抛 ValueError (基线函数本身抛)
        with self.assertRaises(ValueError):
            find_strict_intervals(samples, scan_step=0.0,
                                  window_start=T_DETONATE,
                                  window_end=T_WINDOW_END,
                                  boundary_func=lambda t: -1.0)
        with self.assertRaises(ValueError):
            find_strict_intervals(samples, scan_step=float("nan"),
                                  window_start=T_DETONATE,
                                  window_end=T_WINDOW_END,
                                  boundary_func=lambda t: -1.0)


# =============================================================================
#  G 组 — Q1 回归与对照公式
# =============================================================================
class GQ1Regression(unittest.TestCase):

    def test_g01_point_baseline_unchanged(self):
        res = compute_q1()
        self.assertAlmostEqual(res["total_duration"], 1.435082, places=5)
        self.assertEqual(len(res["intervals"]), 1)
        a, b = res["intervals"][0]
        self.assertAlmostEqual(a, 8.013006, places=4)
        self.assertAlmostEqual(b, 9.448088, places=4)

    def test_g02_cylinder_upper_bound_matches_point_upper(self):
        samps = generate_cylinder_samples(**SAMPLE_GRADES["fine"])
        ivs = find_strict_intervals(samps, scan_step=0.005)
        self.assertEqual(len(ivs), 1)
        self.assertAlmostEqual(ivs[0][1], 9.448088, places=4)

    def test_g03_cylinder_total_le_point_total(self):
        samps = generate_cylinder_samples(**SAMPLE_GRADES["fine"])
        ivs = find_strict_intervals(samps, scan_step=0.01)
        cyl_total = sum(b - a for a, b in ivs)
        point_total = compute_q1()["total_duration"]
        # 严格约束 ⇒ 时长不严格多于点目标
        self.assertLessEqual(cyl_total, point_total + 1e-9)

    def test_g04_compare_formula(self):
        cmp_dict = compare_point_and_cylinder(1.0, 2.0)
        self.assertAlmostEqual(cmp_dict["delta_T"], -1.0)
        self.assertAlmostEqual(cmp_dict["relative_difference"], -0.5)
        self.assertAlmostEqual(cmp_dict["point_total"], 2.0)
        self.assertAlmostEqual(cmp_dict["cylinder_total"], 1.0)

    def test_g05_compare_uses_real_outputs(self):
        samps = generate_cylinder_samples(**SAMPLE_GRADES["fine"])
        ivs = find_strict_intervals(samps, scan_step=0.01)
        cyl_total = sum(b - a for a, b in ivs)
        point_total = compute_q1()["total_duration"]
        cmp_dict = compare_point_and_cylinder(cyl_total, point_total)
        self.assertAlmostEqual(cmp_dict["delta_T"], cyl_total - point_total)
        self.assertAlmostEqual(cmp_dict["relative_difference"],
                               (cyl_total - point_total) / point_total)
        # 不硬编码范围, 只要求数值有限
        self.assertTrue(math.isfinite(cmp_dict["delta_T"]))
        self.assertTrue(math.isfinite(cmp_dict["relative_difference"]))


# =============================================================================
#  H 组 — 空间收敛 (直接调用 check_spatial_convergence 并断言 passed=True)
# =============================================================================
class HSpatialConvergence(unittest.TestCase):

    def test_h01_check_passed_true_with_real_threshold(self):
        res = run_spatial_convergence(scan_step=DIAG_STEP)
        check = check_spatial_convergence(res)
        self.assertTrue(check["passed"],
                         msg=f"reasons: {check['reasons']}")

    def test_h02_medium_vs_fine_interval_count_match(self):
        res = run_spatial_convergence(scan_step=DIAG_STEP)
        m = res["per_grade"]["medium"]
        f = res["per_grade"]["fine"]
        self.assertEqual(m["n_intervals"], f["n_intervals"])

    def test_h03_medium_vs_fine_start_diff_under_threshold(self):
        res = run_spatial_convergence(scan_step=DIAG_STEP)
        check = check_spatial_convergence(res)
        self.assertLessEqual(check["medium_vs_fine"]["start_diff"],
                              SPATIAL_THR_START)

    def test_h04_medium_vs_fine_end_diff_under_threshold(self):
        res = run_spatial_convergence(scan_step=DIAG_STEP)
        check = check_spatial_convergence(res)
        self.assertLessEqual(check["medium_vs_fine"]["end_diff"],
                              SPATIAL_THR_END)

    def test_h05_medium_vs_fine_total_diff_under_threshold(self):
        res = run_spatial_convergence(scan_step=DIAG_STEP)
        check = check_spatial_convergence(res)
        self.assertLessEqual(check["medium_vs_fine"]["total_diff"],
                              SPATIAL_THR_TOTAL)

    def test_h06_medium_vs_fine_coverage_diff_under_threshold(self):
        res = run_spatial_convergence(scan_step=DIAG_STEP)
        check = check_spatial_convergence(res)
        self.assertLessEqual(check["medium_vs_fine"]["max_coverage_diff"],
                              SPATIAL_THR_COVERAGE)

    def test_h07_medium_vs_fine_margin_diff_under_threshold(self):
        res = run_spatial_convergence(scan_step=DIAG_STEP)
        check = check_spatial_convergence(res)
        self.assertLessEqual(check["medium_vs_fine"]["max_margin_diff"],
                              SPATIAL_THR_MARGIN)

    def test_h08_endpoint_residuals_under_threshold(self):
        res = run_spatial_convergence(scan_step=DIAG_STEP)
        for grade in ("medium", "fine"):
            self.assertLessEqual(res["per_grade"][grade]["max_residual"],
                                  SPATIAL_THR_RESIDUAL)


# =============================================================================
#  I 组 — 时间收敛 (多区间支持)
# =============================================================================
class ITemporalConvergence(unittest.TestCase):

    def test_i01_check_passed_true_with_real_threshold(self):
        samps = generate_cylinder_samples(**SAMPLE_GRADES["medium"])
        res = run_temporal_convergence(samps)
        check = check_temporal_convergence(res)
        self.assertTrue(check["passed"], msg=f"reasons: {check['reasons']}")

    def test_i02_three_steps_same_n_intervals(self):
        samps = generate_cylinder_samples(**SAMPLE_GRADES["medium"])
        res = run_temporal_convergence(samps)
        ns = [info["n_intervals"] for info in res["per_step"].values()]
        self.assertEqual(len(set(ns)), 1)

    def test_i03_start_end_total_under_thresholds(self):
        samps = generate_cylinder_samples(**SAMPLE_GRADES["medium"])
        res = run_temporal_convergence(samps)
        check = check_temporal_convergence(res)
        for comp in check["comparisons"]:
            self.assertLessEqual(comp["max_start_diff"], TEMPORAL_THR_START)
            self.assertLessEqual(comp["max_end_diff"], TEMPORAL_THR_END)
            self.assertLessEqual(comp["total_diff"], TEMPORAL_THR_TOTAL)

    def test_i04_endpoint_residuals_under_threshold(self):
        samps = generate_cylinder_samples(**SAMPLE_GRADES["medium"])
        res = run_temporal_convergence(samps)
        for info in res["per_step"].values():
            self.assertLessEqual(info["max_residual"], TEMPORAL_THR_RESIDUAL)

    def test_i05_supports_multiple_intervals_synthetic(self):
        # 构造两段区间, 验证比较器对多区间工作
        T0 = T_DETONATE
        bf = lambda t: -1.0 if (T0 + 1 <= t <= T0 + 3
                                  or T0 + 5 <= t <= T0 + 7) else 1.0
        ivs = find_strict_intervals(
            [SurfaceSample(point=(10.0, 0.0, 0.0), normal=(1.0, 0.0, 0.0),
                            weight=1.0, surface_type="side")],
            scan_step=0.05, window_start=T0, window_end=T0 + 10.0,
            boundary_func=bf,
        )
        self.assertEqual(len(ivs), 2)


# =============================================================================
#  J 组 — SVG 解析与文本内容
# =============================================================================
class JSvgParsing(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.svg_path = "outputs/q1/q1_cylinder_comparison.svg"
        if not os.path.exists(cls.svg_path):
            from src.q1_cylinder import main as q1cyl_main
            q1cyl_main([cls.svg_path])

    def test_j01_svg_is_valid_xml(self):
        tree = ET.parse(self.svg_path)
        root = tree.getroot()
        self.assertTrue(root.tag.endswith("svg"))

    def test_j02_svg_contains_title(self):
        tree = ET.parse(self.svg_path)
        root = tree.getroot()
        ns = {"s": "http://www.w3.org/2000/svg"}
        texts = [t.text or "" for t in root.findall(".//s:text", ns)]
        full = " ".join(texts)
        self.assertIn("Q1 Point vs Full-Cylinder Comparison", full)

    def test_j03_svg_contains_grade_label(self):
        tree = ET.parse(self.svg_path)
        root = tree.getroot()
        ns = {"s": "http://www.w3.org/2000/svg"}
        texts = [t.text or "" for t in root.findall(".//s:text", ns)]
        full = " ".join(texts)
        self.assertIn("FULL-CYLINDER CANDIDATE / EXPERIMENTAL", full)

    def test_j04_svg_has_time_panel_rects(self):
        tree = ET.parse(self.svg_path)
        root = tree.getroot()
        ns = {"s": "http://www.w3.org/2000/svg"}
        rects = root.findall(".//s:rect", ns)
        self.assertGreaterEqual(len(rects), 5)


# =============================================================================
#  K 组 — 时间 / 覆盖率 / 裕量细节
# =============================================================================
class KCoverageMarginDetails(unittest.TestCase):

    def test_k01_refine_margin_improves_or_matches(self):
        samps = generate_cylinder_samples(**SAMPLE_GRADES["fine"])
        # 找 SVG step 网格上的最大 margin 时刻
        # build_time_series 返回 (cov_series, mar_series, cov_max, cov_max_t, mar_max, mar_max_t)
        _, _, _, _, mar_max_grid, mar_max_t_grid = build_time_series(samps)
        # mar_max_t_grid 必须在时间窗内
        self.assertGreaterEqual(mar_max_t_grid, T_WINDOW_START)
        self.assertLessEqual(mar_max_t_grid, T_WINDOW_END)
        # 局部加密
        refined, t_refined = refine_margin_max(samps, mar_max_t_grid,
                                                half_window=0.1, step=0.001)
        self.assertTrue(math.isfinite(refined))
        self.assertTrue(math.isfinite(t_refined))
        # 加密后的值不应小于网格最大值 (允许 1e-3 容差)
        self.assertGreaterEqual(refined, mar_max_grid - 1e-3)

    def test_k02_coverage_plateau_in_strict_interval(self):
        samps = generate_cylinder_samples(**SAMPLE_GRADES["fine"])
        plat = coverage_plateau(samps, step=0.01)
        # 至少一个平台, 且平台时长 > 0
        self.assertGreater(len(plat["plateaus"]), 0)
        for a, b in plat["plateaus"]:
            self.assertGreater(b - a, 0.0)

    def test_k03_build_time_series_finite(self):
        samps = generate_cylinder_samples(**SAMPLE_GRADES["fine"])
        cov_series, mar_series, cov_max, cov_max_t, mar_max, mar_max_t = \
            build_time_series(samps)
        self.assertGreaterEqual(cov_max, 0.0)
        # coverage 在 [0, 1] 闭区间, 浮点误差放宽 1e-9
        self.assertLessEqual(cov_max, 1.0 + 1e-9)
        for _, rho in cov_series:
            self.assertTrue(math.isfinite(rho))
        for _, m_val in mar_series:
            self.assertTrue(math.isfinite(m_val))


# =============================================================================
#  L 组 — 几何层 API 校验
# =============================================================================
class LGeometryAPI(unittest.TestCase):

    def test_l01_non_finite_m_raises(self):
        s = SurfaceSample(point=(10.0, 0.0, 0.0), normal=(1.0, 0.0, 0.0),
                           weight=1.0, surface_type="side")
        with self.assertRaises(ValueError):
            evaluate_occlusion_geometry((float("nan"), 0.0, 0.0),
                                          (5.0, 0.0, 0.0), [s], 10.0)
        with self.assertRaises(ValueError):
            evaluate_occlusion_geometry((float("inf"), 0.0, 0.0),
                                          (5.0, 0.0, 0.0), [s], 10.0)

    def test_l02_non_finite_c_raises(self):
        s = SurfaceSample(point=(10.0, 0.0, 0.0), normal=(1.0, 0.0, 0.0),
                           weight=1.0, surface_type="side")
        with self.assertRaises(ValueError):
            evaluate_occlusion_geometry((0.0, 0.0, 0.0),
                                          (float("nan"), 0.0, 0.0), [s], 10.0)

    def test_l03_invalid_radius_raises(self):
        s = SurfaceSample(point=(10.0, 0.0, 0.0), normal=(1.0, 0.0, 0.0),
                           weight=1.0, surface_type="side")
        with self.assertRaises(ValueError):
            evaluate_occlusion_geometry((0.0, 0.0, 0.0), (5.0, 0.0, 0.0),
                                          [s], 0.0)
        with self.assertRaises(ValueError):
            evaluate_occlusion_geometry((0.0, 0.0, 0.0), (5.0, 0.0, 0.0),
                                          [s], -1.0)

    def test_l04_inject_trajectory_works(self):
        # Q2 可注入新轨迹: 自定义 m(t), c(t) 与窗口
        # 两个对称样本保证在测试窗口内可见
        samples = [
            SurfaceSample(point=(10.0, 0.0, 0.0), normal=(1.0, 0.0, 0.0),
                           weight=1.0, surface_type="side"),
            SurfaceSample(point=(-10.0, 0.0, 0.0), normal=(-1.0, 0.0, 0.0),
                           weight=1.0, surface_type="side"),
        ]
        # m 在原点, c 在原点 ⇒ 距离 10 ⇒ 遮挡边界
        # 设 m=(20,0,0), c=(10,0,0): 在线段 [m,s1] 上, 距离 0 ⇒ 遮挡
        ivs = find_strict_intervals(
            samples, scan_step=0.01,
            missile_position_fn=lambda t: (20.0, 0.0, 0.0),
            cloud_center_fn=lambda t: (10.0, 0.0, 0.0),
            window_start=0.0, window_end=10.0,
        )
        self.assertGreaterEqual(len(ivs), 1)
        for a, b in ivs:
            self.assertGreaterEqual(a, 0.0)
            self.assertLessEqual(b, 10.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)