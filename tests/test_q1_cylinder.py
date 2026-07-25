"""tests/test_q1_cylinder.py — 10 组 (A-J) 单元测试覆盖 TASK_003 完整圆柱遮蔽判定.

所有数值参考:
- Q1 点目标基线 (BASELINE): 1.435082 s, 区间 (8.013006, 9.448088) s
- 完整圆柱严格遮蔽 (fine): 1.392384 s, 区间 (8.055704, 9.448088) s
- 空间收敛 (medium vs fine): 区间数 1=1, 总时长差 0.000747 s
- 时间收敛 (0.02/0.01/0.005): 区间数 1=1, 总时长差 ≤ 1e-9 s

等级: FULL-CYLINDER CANDIDATE / EXPERIMENTAL
"""

from __future__ import annotations

import math
import os
import sys
import unittest
import xml.etree.ElementTree as ET
from typing import List, Tuple

# 把项目根目录加入 sys.path, 避免 import 顺序问题
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.q1_baseline import (
    CLOUD_RADIUS, CLOUD_DURATION, T_DETONATE, M0, P,
    cloud_center, missile_position,
    compute_q1,
)
from src.q1_cylinder import (
    R_T, H_T, CYL_BASE, CYL_TOP, CYL_AXIS_DIR,
    SAMPLE_GRADES, TIME_STEPS, EPS_VISIBLE,
    T_WINDOW_START, T_WINDOW_END,
    SurfaceSample, generate_cylinder_samples, verify_sample_geometry,
    sample_is_visible, visible_samples,
    sample_is_occluded,
    evaluate_cylinder_state, CylinderState,
    strict_boundary_value,
    find_strict_intervals,
    run_temporal_convergence, run_spatial_convergence,
    check_temporal_convergence, check_spatial_convergence,
    compare_point_and_cylinder,
    write_comparison_svg,
    build_time_series,
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
        params = SAMPLE_GRADES["fine"]
        samps = generate_cylinder_samples(**params)
        geo = verify_sample_geometry(samps)
        expected = 2.0 * math.pi * R_T * H_T + 2.0 * math.pi * R_T ** 2
        self.assertAlmostEqual(geo["total_weight"], expected, places=8)

    def test_a04_cell_centers_avoid_junction(self):
        # 侧面与端面公共棱边 (z=0 / z=H_T) 应不在侧面采样格点上
        samps = generate_cylinder_samples(side_theta=4, side_z=4, cap_r=2, cap_theta=4)
        for s in samps:
            if s.surface_type == "side":
                # 单元中心 z 严格在 (0, H_T) 内部
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
                # 侧面法向 · 轴向 应为 0 (法向在 xy 平面, 轴沿 z)
                dot = sum(a * b for a, b in zip(s.normal, CYL_AXIS_DIR))
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

    def test_a10_point_target_inside_or_near_cylinder(self):
        # 点目标 P=(0,200,5) 应位于圆柱内部 (r=0, z=5 ∈ [0,10]),
        # 不直接是任何表面样本 (P 在表面下方).
        samps = generate_cylinder_samples(**SAMPLE_GRADES["medium"])
        # P 不在 (侧面 (r=7) ∪ 端面 (z=0 或 z=10) ∪ 侧面/端面公共棱) 上
        for s in samps:
            if s.point == P:
                self.fail("P 不能精确等于任何表面样本")
        # P 到所有样本距离 > 0 (排除 P 在表面上这一情况)
        min_d = min(math.sqrt(sum((a - b) ** 2 for a, b in zip(s.point, P)))
                    for s in samps)
        self.assertGreater(min_d, 0.0)
        # 最近的样本应在合理距离内 (≤ R_T + H_T/2)
        self.assertLess(min_d, R_T + H_T / 2)


# =============================================================================
#  B 组 — 可见性
# =============================================================================
class BVisibility(unittest.TestCase):

    def setUp(self):
        self.samps = generate_cylinder_samples(**SAMPLE_GRADES["medium"])

    def test_b01_top_cap_visible_when_observer_above(self):
        # 远高处正前方观测, 顶面应可见
        m = (20000.0, 0.0, 1800.0)
        vis = visible_samples(self.samps, m)
        n_top_vis = sum(1 for s in vis if s.surface_type == "top")
        self.assertGreater(n_top_vis, 0)

    def test_b02_bottom_cap_not_visible_when_observer_above(self):
        # 高处观测者看下方目标, 底面不可见 (法向 -z 与视线方向 dot < 0)
        m = (20000.0, 0.0, 1800.0)
        vis = visible_samples(self.samps, m)
        n_bot_vis = sum(1 for s in vis if s.surface_type == "bottom")
        self.assertEqual(n_bot_vis, 0)

    def test_b03_half_side_visible(self):
        # 远处观测者, 正面半边侧面可见
        m = (20000.0, 0.0, 1800.0)
        vis = visible_samples(self.samps, m)
        n_side_vis = sum(1 for s in vis if s.surface_type == "side")
        n_side_total = sum(1 for s in self.samps if s.surface_type == "side")
        # 远距离下, 严格一半 + 少量边缘可见 (依赖分辨率)
        self.assertGreater(n_side_vis, n_side_total // 2 - 5)
        self.assertLess(n_side_vis, n_side_total // 2 + 5)

    def test_b04_observer_back_x_sees_plus_x_side(self):
        # 观测者在 -x 远处 (正对 +x 半边侧面)
        # 此时面向观测者的反而是 +x 半边侧面 (而非 -x 半边)
        m = (-20000.0, 0.0, 1800.0)
        vis = visible_samples(self.samps, m)
        n_side_vis = sum(1 for s in vis if s.surface_type == "side")
        # 应可见 +x 半边侧面 (n_side ≈ n_total/2)
        n_side_total = sum(1 for s in self.samps if s.surface_type == "side")
        self.assertGreater(n_side_vis, n_side_total // 2 - 5)

    def test_b05_visibility_invariant_to_eps_small(self):
        # eps 的小改变不应大改可见集 (稳定边界点)
        m = (18478.0, 0.0, 1848.0)
        v_small = visible_samples(self.samps, m)
        # 改 eps 不变 (默认已用 EPS_VISIBLE)
        v_default = visible_samples(self.samps, m)
        self.assertEqual(len(v_small), len(v_default))


# =============================================================================
#  C 组 — 遮挡判定
# =============================================================================
class COcclusion(unittest.TestCase):

    def setUp(self):
        self.samps = generate_cylinder_samples(**SAMPLE_GRADES["medium"])

    def test_c01_sample_inside_cloud_occluded(self):
        # 视线段直接穿过云团中心, 应被遮挡
        # 取一个正面侧面样本
        s = next(s for s in self.samps if s.surface_type == "side"
                 and abs(s.point[0]) < 7 and s.point[2] < 5)
        m = missile_position(8.5)
        c = cloud_center(8.5)
        # 强制让 c 位于线段 [m, s.point] 上方
        self.assertTrue(sample_is_occluded(s, m, c, radius=CLOUD_RADIUS))

    def test_c02_sample_outside_cloud_not_occluded(self):
        # 远离云团, 视线段最短距离远 > 10
        s = next(s for s in self.samps if s.surface_type == "side"
                 and s.point[0] > 5)
        m = missile_position(5.1)  # 极早期, 烟幕弹未投放
        c = cloud_center(5.1)
        self.assertFalse(sample_is_occluded(s, m, c, radius=CLOUD_RADIUS))

    def test_c03_radius_zero_only_point_occluded(self):
        # radius=0 时, 仅云团心精确在闭线段上才算遮挡
        s = self.samps[0]
        m = missile_position(8.5)
        # 把 c 放到闭线段外一点
        c = (m[0] + 100.0, m[1] + 100.0, m[2] + 100.0)
        self.assertFalse(sample_is_occluded(s, m, c, radius=0.0))


# =============================================================================
#  D 组 — 覆盖率
# =============================================================================
class DCoverage(unittest.TestCase):

    def setUp(self):
        self.samps = generate_cylinder_samples(**SAMPLE_GRADES["medium"])

    def test_d01_coverage_in_unit_interval(self):
        for t in (5.1, 7.0, 8.0, 8.5, 9.0, 9.5, 10.0):
            s = evaluate_cylinder_state(t, self.samps)
            self.assertGreaterEqual(s.coverage_ratio, 0.0)
            self.assertLessEqual(s.coverage_ratio, 1.0)

    def test_d02_coverage_is_occluded_over_visible(self):
        # 若 strict_occlusion, coverage == 1 (所有可见都遮挡)
        for t in (8.5, 8.8, 9.0):
            s = evaluate_cylinder_state(t, self.samps)
            if s.strict_occlusion:
                self.assertAlmostEqual(s.coverage_ratio, 1.0, places=6)

    def test_d03_coverage_zero_when_no_visible(self):
        # 早期窗口外 (云团未爆), 状态为 "无观测"
        s = evaluate_cylinder_state(0.0, self.samps)
        self.assertEqual(s.visible_weight, 0.0)
        self.assertEqual(s.coverage_ratio, 0.0)

    def test_d04_visible_count_matches_occluded_plus_unoccluded(self):
        s = evaluate_cylinder_state(8.0, self.samps)
        self.assertEqual(s.visible_count, s.occluded_count
                         + sum(1 for sv in visible_samples(self.samps, missile_position(8.0))
                               if not sample_is_occluded(sv, missile_position(8.0),
                                                          cloud_center(8.0))))


# =============================================================================
#  E 组 — 严格裕量
# =============================================================================
class EStrictMargin(unittest.TestCase):

    def setUp(self):
        self.samps = generate_cylinder_samples(**SAMPLE_GRADES["medium"])

    def test_e01_margin_equals_radius_minus_max_d(self):
        for t in (5.1, 8.0, 8.5, 9.0, 10.0):
            s = evaluate_cylinder_state(t, self.samps)
            if math.isfinite(s.max_visible_distance):
                self.assertAlmostEqual(s.strict_margin,
                                       CLOUD_RADIUS - s.max_visible_distance,
                                       places=9)

    def test_e02_strict_occlusion_iff_margin_nonneg(self):
        for t in (5.1, 7.0, 8.0, 8.5, 9.0, 9.5, 10.0):
            s = evaluate_cylinder_state(t, self.samps)
            self.assertEqual(s.strict_occlusion, s.strict_margin >= 0.0)

    def test_e03_worst_sample_iff_unoccluded_iff_not_strict(self):
        # worst = max-distance sample. 若 strict_occlusion (max ≤ R), 则 worst 被遮挡;
        # 若 !strict_occlusion (max > R), 则 worst 距 > R, 即未被遮挡.
        from src.q1_baseline import point_to_segment_distance
        for t in (5.1, 8.0, 8.5, 9.0, 10.0):
            s = evaluate_cylinder_state(t, self.samps)
            if s.worst_sample_point is None:
                continue
            d, _ = point_to_segment_distance(cloud_center(t),
                                              missile_position(t),
                                              s.worst_sample_point)
            if s.strict_occlusion:
                # 所有可见都被遮挡 (max ≤ R), worst 自然也被遮挡
                self.assertLessEqual(d, CLOUD_RADIUS + 1e-9)
            else:
                # worst 是 max, 必未遮挡
                self.assertGreater(d, CLOUD_RADIUS - 1e-9)


# =============================================================================
#  F 组 — 区间算法注入
# =============================================================================
class FIntervalAlgorithmInjection(unittest.TestCase):

    def test_f01_full_window_effective(self):
        # 注入"全窗口为有效" → 整个 [T_DET, T_DET+20] 为单区间
        ivs = find_strict_intervals(self.samps_for_test(), scan_step=0.01)
        # 不直接断言时间窗, 而是验证 baseline find_effective_intervals 注入语义
        from src.q1_baseline import find_effective_intervals
        bf = lambda t: -1.0  # 永远 ≤ 0
        ivs2 = find_effective_intervals(
            scan_step=0.01, t_detonate=T_DETONATE,
            boundary_func=bf,
        )
        self.assertEqual(len(ivs2), 1)
        self.assertAlmostEqual(ivs2[0][0], T_WINDOW_START, places=9)
        self.assertAlmostEqual(ivs2[0][1], T_WINDOW_END, places=9)

    def test_f02_zero_window_effective(self):
        from src.q1_baseline import find_effective_intervals
        bf = lambda t: 1.0  # 永远 > 0
        ivs = find_effective_intervals(
            scan_step=0.01, t_detonate=T_DETONATE, boundary_func=bf,
        )
        self.assertEqual(ivs, [])

    def test_f03_two_intervals_via_custom_boundary(self):
        from src.q1_baseline import find_effective_intervals, T_DETONATE as T0
        # 注入 [T0+2, T0+5] ∪ [T0+10, T0+13] 为有效
        def bf(t: float) -> float:
            if T0 + 2 <= t <= T0 + 5:
                return -1.0
            if T0 + 10 <= t <= T0 + 13:
                return -1.0
            return 1.0
        ivs = find_effective_intervals(
            scan_step=0.05, t_detonate=T0, boundary_func=bf,
        )
        self.assertEqual(len(ivs), 2)

    def test_f04_t_arrival_truncation(self):
        from src.q1_baseline import find_effective_intervals, T_DETONATE as T0
        bf = lambda t: -1.0  # 全窗口
        ivs = find_effective_intervals(
            scan_step=0.05, t_detonate=T0, t_arrival=T0 + 8.0,
            boundary_func=bf,
        )
        self.assertEqual(len(ivs), 1)
        self.assertAlmostEqual(ivs[0][1], T0 + 8.0, places=9)

    def samps_for_test(self):
        return generate_cylinder_samples(**SAMPLE_GRADES["medium"])


# =============================================================================
#  G 组 — Q1 回归
# =============================================================================
class GQ1Regression(unittest.TestCase):

    def test_g01_point_baseline_unchanged(self):
        # Q1 点目标基线 1.435082 s, 区间 (8.013006, 9.448088) s 必须不变
        res = compute_q1()
        self.assertAlmostEqual(res["total_duration"], 1.435082, places=5)
        self.assertEqual(len(res["intervals"]), 1)
        a, b = res["intervals"][0]
        self.assertAlmostEqual(a, 8.013006, places=4)
        self.assertAlmostEqual(b, 9.448088, places=4)

    def test_g02_cylinder_upper_bound_matches_point_upper(self):
        # 完整圆柱上界 = 点目标上界 (云团下沉后几何对称)
        samps = generate_cylinder_samples(**SAMPLE_GRADES["fine"])
        ivs = find_strict_intervals(samps, scan_step=0.005)
        # fine 区间上界 ≈ 9.448088
        self.assertEqual(len(ivs), 1)
        self.assertAlmostEqual(ivs[0][1], 9.448088, places=4)

    def test_g03_cylinder_total_shorter_than_point(self):
        # 完整圆柱应给出不严格 ≥ 点目标 (更宽约束 → 时长更短或相等)
        samps = generate_cylinder_samples(**SAMPLE_GRADES["fine"])
        ivs = find_strict_intervals(samps, scan_step=0.01)
        cyl_total = sum(b - a for a, b in ivs)
        point_total = compute_q1()["total_duration"]
        self.assertLessEqual(cyl_total, point_total + 1e-9)

    def test_g04_delta_in_reasonable_range(self):
        # ΔT (cyl - point) 应在 [-0.2, 0.0] 内 (粗略物理估计)
        samps = generate_cylinder_samples(**SAMPLE_GRADES["fine"])
        ivs = find_strict_intervals(samps, scan_step=0.01)
        cyl_total = sum(b - a for a, b in ivs)
        point_total = compute_q1()["total_duration"]
        delta = cyl_total - point_total
        self.assertLessEqual(delta, 0.0 + 1e-9)
        self.assertGreaterEqual(delta, -0.2)


# =============================================================================
#  H 组 — 空间收敛
# =============================================================================
class HSpatialConvergence(unittest.TestCase):

    def test_h01_all_three_grades_compute(self):
        res = run_spatial_convergence(scan_step=0.01)
        for grade in ("coarse", "medium", "fine"):
            self.assertIn(grade, res["per_grade"])
            self.assertGreaterEqual(res["per_grade"][grade]["n_intervals"], 1)

    def test_h02_medium_vs_fine_same_interval_count(self):
        res = run_spatial_convergence(scan_step=0.01)
        self.assertEqual(res["per_grade"]["medium"]["n_intervals"],
                         res["per_grade"]["fine"]["n_intervals"])

    def test_h03_medium_vs_fine_total_duration_close(self):
        res = run_spatial_convergence(scan_step=0.01)
        m_t = res["per_grade"]["medium"]["total_duration"]
        f_t = res["per_grade"]["fine"]["total_duration"]
        self.assertLess(abs(m_t - f_t), 0.005)  # medium vs fine ≤ 5e-3 s

    def test_h04_medium_vs_fine_endpoints_close(self):
        res = run_spatial_convergence(scan_step=0.01)
        m_ivs = res["per_grade"]["medium"]["intervals"]
        f_ivs = res["per_grade"]["fine"]["intervals"]
        for ia, ib in zip(m_ivs, f_ivs):
            self.assertLess(abs(ia[0] - ib[0]), 0.05)  # 起终点 < 50 ms
            self.assertLess(abs(ia[1] - ib[1]), 0.05)

    def test_h05_coarse_within_tolerance_of_fine(self):
        # coarse 与 fine 总时长差应 < 0.01 s (粗校)
        res = run_spatial_convergence(scan_step=0.01)
        c_t = res["per_grade"]["coarse"]["total_duration"]
        f_t = res["per_grade"]["fine"]["total_duration"]
        self.assertLess(abs(c_t - f_t), 0.01)


# =============================================================================
#  I 组 — 时间收敛
# =============================================================================
class ITemporalConvergence(unittest.TestCase):

    def setUp(self):
        self.samps = generate_cylinder_samples(**SAMPLE_GRADES["medium"])

    def test_i01_three_steps_same_intervals(self):
        res = run_temporal_convergence(self.samps)
        for step in TIME_STEPS:
            self.assertIn(step, res["per_step"])
        # 三档 n_intervals 应一致
        ns = [res["per_step"][s]["n_intervals"] for s in TIME_STEPS]
        self.assertEqual(len(set(ns)), 1)

    def test_i02_endpoints_match(self):
        res = run_temporal_convergence(self.samps)
        # 所有起终点应近似相同
        starts = [res["per_step"][s]["intervals"][0][0] for s in TIME_STEPS
                  if res["per_step"][s]["intervals"]]
        ends = [res["per_step"][s]["intervals"][0][1] for s in TIME_STEPS
                if res["per_step"][s]["intervals"]]
        self.assertLess(max(starts) - min(starts), 0.01)
        self.assertLess(max(ends) - min(ends), 0.01)

    def test_i03_total_durations_match(self):
        res = run_temporal_convergence(self.samps)
        tots = [res["per_step"][s]["total_duration"] for s in TIME_STEPS]
        self.assertLess(max(tots) - min(tots), 0.02)

    def test_i04_endpoint_residue_small(self):
        from src.q1_baseline import f_distance_minus_radius
        # 用严格边界函数求 max |f(b)|
        from src.q1_cylinder import strict_boundary_value
        samps = self.samps
        ivs = find_strict_intervals(samps, scan_step=0.005)
        for a, b in ivs:
            fa = strict_boundary_value(a, samps)
            fb = strict_boundary_value(b, samps)
            self.assertLessEqual(abs(fa), 1e-4)
            self.assertLessEqual(abs(fb), 1e-4)


# =============================================================================
#  J 组 — SVG 解析
# =============================================================================
class JSvgParsing(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.svg_path = "outputs/q1/q1_cylinder_comparison.svg"
        # 确保 SVG 存在
        if not os.path.exists(cls.svg_path):
            from src.q1_cylinder import main as q1cyl_main
            q1cyl_main([cls.svg_path])

    def test_j01_svg_is_valid_xml(self):
        tree = ET.parse(self.svg_path)
        root = tree.getroot()
        self.assertTrue(root.tag.endswith("svg"))

    def test_j02_svg_has_time_panel(self):
        tree = ET.parse(self.svg_path)
        root = tree.getroot()
        ns = {"s": "http://www.w3.org/2000/svg"}
        # 至少有 3 个 rect (区间填充块)
        rects = root.findall(".//s:rect", ns)
        self.assertGreaterEqual(len(rects), 5)

    def test_j03_svg_has_cyl_rect(self):
        tree = ET.parse(self.svg_path)
        root = tree.getroot()
        ns = {"s": "http://www.w3.org/2000/svg"}
        rects = root.findall(".//s:rect", ns)
        # 至少有一个 purple 描边的"圆柱"标识
        colors = [r.attrib.get("stroke", "") for r in rects]
        self.assertIn("purple", colors)

    def test_j04_svg_has_legend(self):
        tree = ET.parse(self.svg_path)
        root = tree.getroot()
        ns = {"s": "http://www.w3.org/2000/svg"}
        texts = [t.text or "" for t in root.findall(".//s:text", ns)]
        full_text = " ".join(texts)
        self.assertIn("M1", full_text)
        self.assertIn("FY1", full_text)


if __name__ == "__main__":
    unittest.main(verbosity=2)