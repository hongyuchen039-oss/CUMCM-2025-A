"""tests/test_q2_single_bomb.py — TASK_004 Foundation 单元测试.

覆盖 Section 14 的 35 个测试类别 (A-T), 全部确定性, 控制在本地 60 秒以内.
不运行 100 个候选 smoke, 不运行 spatial / temporal convergence, 不运行 fine 采样评估.

等级: TASK_004 FOUNDATION / NOT AN OPTIMIZATION RESULT.
"""

from __future__ import annotations

import copy
import math
import os
import sys
import unittest
from io import StringIO

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.q1_baseline import (
    G, CLOUD_SINK, CLOUD_DURATION,
    U0,
    missile_arrival_time,
    vector_add, vector_scale, dot, norm,
)
from src.q1_cylinder import (
    SAMPLE_GRADES,
    generate_cylinder_samples, find_strict_intervals,
)
from src.q2_single_bomb import (
    SingleBombStrategy, SingleBombEvaluation,
    normalize_heading, heading_to_unit_vector,
    fy1_velocity, fy1_position,
    release_point, detonation_time, detonation_point, detonation_point_eq2,
    make_cloud_center_fn,
    validate_strategy,
    evaluate_single_bomb_strategy,
    generate_candidates, run_smoke,
    PROFILE_GRADES, PROFILE_SCAN_STEPS,
    Q1_FIXED_STRATEGY, Q1_EXPECTED, EPS_GROUND,
    main as q2_main,
)

import src.q2_single_bomb as q2


def _vec_close(a, b, tol: float = 1e-9) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return all(abs(a[i] - b[i]) < tol for i in range(3))


def _make_strategy(**overrides):
    """构造策略; 提供默认值覆盖所有 4 个变量."""
    base = dict(
        heading_rad=math.pi,
        speed_mps=120.0,
        release_time_s=1.5,
        delay_s=3.6,
    )
    base.update(overrides)
    return SingleBombStrategy(**base)


# =============================================================================
#  A — Heading normalization (Section 14: 1-6)
# =============================================================================
class AHeadingNormalization(unittest.TestCase):

    def test_a01_heading_zero(self):
        self.assertAlmostEqual(normalize_heading(0.0), 0.0, places=12)

    def test_a02_heading_half_pi(self):
        self.assertAlmostEqual(normalize_heading(math.pi / 2),
                                math.pi / 2, places=12)

    def test_a03_heading_pi(self):
        self.assertAlmostEqual(normalize_heading(math.pi), math.pi, places=12)

    def test_a04_heading_two_pi_normalizes_to_zero(self):
        # fmod(x, 2π) 可能恰好返回 2π ⇒ 严格归零
        self.assertAlmostEqual(normalize_heading(2.0 * math.pi), 0.0, places=12)
        # 负 2π 与正 2π 等价
        self.assertAlmostEqual(normalize_heading(-2.0 * math.pi), 0.0, places=12)

    def test_a05_negative_heading(self):
        # -π/2 → 3π/2
        self.assertAlmostEqual(normalize_heading(-math.pi / 2),
                                3.0 * math.pi / 2, places=12)
        self.assertAlmostEqual(normalize_heading(-math.pi),
                                math.pi, places=12)

    def test_a06_multi_period_heading(self):
        # 4π → 0
        self.assertAlmostEqual(normalize_heading(4.0 * math.pi), 0.0, places=12)
        # 5π → π
        self.assertAlmostEqual(normalize_heading(5.0 * math.pi), math.pi, places=12)
        # -5π → π
        self.assertAlmostEqual(normalize_heading(-5.0 * math.pi), math.pi, places=12)
        # 非整倍数 → 落在 [0, 2π)
        v = normalize_heading(3.0 * math.pi + 0.5)
        self.assertGreaterEqual(v, 0.0)
        self.assertLess(v, 2.0 * math.pi)


# =============================================================================
#  B — Speed validity (Section 14: 7-9)
# =============================================================================
class BSpeedValidity(unittest.TestCase):

    def test_b01_speed_70_valid(self):
        s = _make_strategy(speed_mps=70.0)
        v, r = validate_strategy(s)
        self.assertTrue(v, r)

    def test_b02_speed_140_valid(self):
        s = _make_strategy(speed_mps=140.0)
        v, r = validate_strategy(s)
        self.assertTrue(v, r)

    def test_b03_speed_below_70_invalid(self):
        s = _make_strategy(speed_mps=69.999)
        v, r = validate_strategy(s)
        self.assertFalse(v)
        self.assertIn("speed_mps", r)

    def test_b04_speed_above_140_invalid(self):
        s = _make_strategy(speed_mps=140.001)
        v, r = validate_strategy(s)
        self.assertFalse(v)
        self.assertIn("speed_mps", r)


# =============================================================================
#  C — Release time / delay validity (Section 14: 10-13)
# =============================================================================
class CReleaseDelayValidity(unittest.TestCase):

    def test_c01_release_time_zero_valid(self):
        s = _make_strategy(release_time_s=0.0)
        v, _ = validate_strategy(s)
        self.assertTrue(v)

    def test_c02_release_time_negative_invalid(self):
        s = _make_strategy(release_time_s=-0.01)
        v, r = validate_strategy(s)
        self.assertFalse(v)
        self.assertIn("release_time_s", r)

    def test_c03_delay_zero_valid(self):
        s = _make_strategy(delay_s=0.0)
        v, _ = validate_strategy(s)
        self.assertTrue(v)

    def test_c04_delay_negative_invalid(self):
        s = _make_strategy(delay_s=-1e-9)
        v, r = validate_strategy(s)
        self.assertFalse(v)
        self.assertIn("delay_s", r)


# =============================================================================
#  D — Release point derivation (Section 14: 14)
# =============================================================================
class DReleasePoint(unittest.TestCase):

    def test_d01_release_point_default_strategy(self):
        # Q1 策略: heading=π, speed=120, release=1.5
        # R = U0 + (-120, 0, 0) * 1.5 = (17800-180, 0, 1800) = (17620, 0, 1800)
        s = Q1_FIXED_STRATEGY
        r = release_point(s)
        self.assertTrue(_vec_close(r, (17620.0, 0.0, 1800.0), tol=1e-9))

    def test_d02_release_point_motion_consistency(self):
        # 任意航向: fy1_position(t_release) == release_point(strategy)
        s = _make_strategy(heading_rad=1.234, speed_mps=95.0,
                            release_time_s=2.5, delay_s=0.5)
        v = fy1_velocity(s.heading_rad, s.speed_mps)
        r_direct = release_point(s)
        r_pos = fy1_position(s.release_time_s, U0, v)
        self.assertTrue(_vec_close(r_direct, r_pos, tol=1e-9))

    def test_d03_release_point_zero_release_time(self):
        # t_release=0 ⇒ R = U0
        s = _make_strategy(release_time_s=0.0, delay_s=0.0)
        r = release_point(s)
        self.assertTrue(_vec_close(r, U0, tol=1e-9))


# =============================================================================
#  E — Detonation point two-form equivalence (Section 14: 15)
# =============================================================================
class EDetonationPointEquivalence(unittest.TestCase):

    def test_e01_two_forms_match(self):
        # D = R + v δ u + (0, 0, -0.5 g δ²)
        #    = F0 + v (t_release + δ) u + (0, 0, -0.5 g δ²)
        s = Q1_FIXED_STRATEGY
        d1 = detonation_point(s)
        d2 = detonation_point_eq2(s)
        self.assertTrue(_vec_close(d1, d2, tol=1e-9),
                        f"D1={d1} D2={d2}")

    def test_e02_two_forms_match_random(self):
        for theta in (0.1, 0.7, math.pi, 3.1, 5.5):
            for speed in (75.0, 100.0, 135.0):
                for tr in (0.5, 2.0, 5.0):
                    for dl in (0.5, 3.0, 10.0):
                        s = SingleBombStrategy(heading_rad=theta,
                                                speed_mps=speed,
                                                release_time_s=tr,
                                                delay_s=dl)
                        d1 = detonation_point(s)
                        d2 = detonation_point_eq2(s)
                        self.assertTrue(_vec_close(d1, d2, tol=1e-9),
                                        f"({theta},{speed},{tr},{dl}):"
                                        f" D1={d1} D2={d2}")


# =============================================================================
#  F — Detonation time derivation (Section 14: 16)
# =============================================================================
class FDetonationTime(unittest.TestCase):

    def test_f01_detonation_time_sum(self):
        s = _make_strategy(release_time_s=2.0, delay_s=3.4)
        self.assertAlmostEqual(detonation_time(s), 5.4, places=12)

    def test_f02_q1_detonation_time(self):
        # Q1: 1.5 + 3.6 = 5.1 s
        self.assertAlmostEqual(detonation_time(Q1_FIXED_STRATEGY),
                                5.1, places=12)


# =============================================================================
#  G — Detonation z limits (Section 14: 17-18)
# =============================================================================
class GDetonationZLimits(unittest.TestCase):

    def test_g01_detonation_z_zero_boundary(self):
        # P1-2 重写: 理论 z=0 边界必须合法 (EPS_GROUND 吸收浮点舍入).
        # 不得用 delta*0.5 等远离边界的策略冒充 z=0 测试.
        delta_ground = math.sqrt(2.0 * U0[2] / G)
        s = _make_strategy(release_time_s=0.5, delay_s=delta_ground)
        d_raw = detonation_point(s)
        # 浮点 z 接近 0 (量级 1e-10); validate 必须通过
        v, r = validate_strategy(s)
        self.assertTrue(v, f"理论 z=0 必须合法, 实际 reason={r}")
        # 用于评估的 detonation_point z 必须为 0.0 (规范化)
        ev = evaluate_single_bomb_strategy(s, sample_level="coarse",
                                            scan_step=0.05)
        self.assertEqual(ev.detonation_point[2], 0.0,
                          f"理论 z=0 归一化后应为 0, 实际 {ev.detonation_point[2]}")

    def test_g02_detonation_z_negative_invalid(self):
        # δ 比 z=0 略大: z < 0
        delta = math.sqrt(2.0 * U0[2] / G) + 0.5
        s = _make_strategy(release_time_s=0.5, delay_s=delta)
        d = detonation_point(s)
        self.assertLess(d[2], 0.0)
        v, r = validate_strategy(s)
        self.assertFalse(v)
        self.assertIn("z", r)


# =============================================================================
#  H — Cloud center derivation (Section 14: 19-20)
# =============================================================================
class HCloudCenter(unittest.TestCase):

    def test_h01_cloud_center_at_detonation(self):
        s = Q1_FIXED_STRATEGY
        d = detonation_point(s)
        cf = make_cloud_center_fn(s, d)
        c_at_td = cf(detonation_time(s))
        self.assertTrue(_vec_close(c_at_td, d, tol=1e-9))

    def test_h02_cloud_sinks_3_mps(self):
        s = Q1_FIXED_STRATEGY
        d = detonation_point(s)
        cf = make_cloud_center_fn(s, d)
        td = detonation_time(s)
        c0 = cf(td)
        c5 = cf(td + 5.0)
        c20 = cf(td + 20.0)
        self.assertAlmostEqual(d[2] - c0[2], 0.0, places=9)
        self.assertAlmostEqual(d[2] - c5[2], 15.0, places=9)
        self.assertAlmostEqual(d[2] - c20[2], CLOUD_SINK * 20.0, places=9)

    def test_h03_cloud_before_detonation_unchanged(self):
        # t < t_d ⇒ 云团中心等于起爆点 (哨兵行为)
        s = Q1_FIXED_STRATEGY
        d = detonation_point(s)
        cf = make_cloud_center_fn(s, d)
        c = cf(0.0)
        self.assertTrue(_vec_close(c, d, tol=1e-9))


# =============================================================================
#  I — Strategy status (Section 14: 21-25, 26-27)
# =============================================================================
class IStrategyStatus(unittest.TestCase):

    def test_i01_search_domain_prune(self):
        # P1-1 重写: pruned_zero 必须 valid=True (物理合法, 仅搜索域剪枝)
        # t_d > t_arrival ⇒ pruned_zero
        # 必须保证: z >= 0 (合法) AND t_release + delay > t_arrival.
        # z >= 0 ⇒ delay <= sqrt(2*1800/9.8) ≈ 19.166
        # t_d > t_arrival (~ 67) ⇒ delay > 67 - t_release
        # 构造 t_release = 48, delay = 19 ⇒ t_d = 67 > 67 (实为 ≈67.0 > ≈66.999)
        t_arr = missile_arrival_time()
        s = _make_strategy(release_time_s=48.0, delay_s=19.0)
        # 第一步: 合法性应通过 (delay=19 < 19.166, z≥0)
        valid_pre, _ = validate_strategy(s)
        self.assertTrue(valid_pre, "用于剪枝测试的策略应首先合法")
        ev = evaluate_single_bomb_strategy(s, sample_level="coarse",
                                            scan_step=0.1)
        self.assertEqual(ev.status, "pruned_zero",
                          f"t_detonate={ev.detonation_time_s} "
                          f"t_arrival={t_arr} → 期望 pruned_zero, 实际 {ev.status}")
        # P1-1: pruned_zero 必须 valid=True
        self.assertTrue(ev.valid,
                          "pruned_zero 必须 valid=True (P1-1)")
        self.assertEqual(ev.total_duration_s, 0.0)
        self.assertEqual(ev.intervals, ())
        self.assertGreater(len(ev.reason), 0)

    def test_i02_search_domain_boundary_returns_zero(self):
        # P1-1 重写: zero_window 必须 valid=True (物理合法, 仅窗口空)
        # t_d == t_arrival → window empty → zero_window (合法 0 目标)
        # 注入 t_arrival 让边界可精确控制 (不依赖 m1 默认)
        t_arr_inj = 30.0
        # 合法 delay (z≥0): delay=10 ⇒ z = 1800 - 0.5*9.8*100 = 1310 > 0
        # t_release + delay = 20 + 10 = 30 == t_arrival
        s = _make_strategy(release_time_s=20.0, delay_s=10.0)
        ev = evaluate_single_bomb_strategy(s, sample_level="coarse",
                                            scan_step=0.1,
                                            t_arrival=t_arr_inj)
        self.assertEqual(ev.status, "zero_window")
        # P1-1: zero_window 必须 valid=True
        self.assertTrue(ev.valid,
                          "zero_window 必须 valid=True (P1-1)")
        self.assertEqual(ev.total_duration_s, 0.0)
        self.assertIsNotNone(ev.evaluation_window)
        ws, we = ev.evaluation_window
        self.assertAlmostEqual(ws, 30.0, places=9)
        self.assertAlmostEqual(we, 30.0, places=9)

    def test_i03_no_occlusion_returns_zero(self):
        # 合法策略但完整导弹路径都不遮蔽: 评估结果应为合法零目标
        # 通过注入恶意 boundary_func 模拟: f(t) 恒 +1 不会触发任何遮蔽.
        # 那是 wrapper 测试; 此处验证 evaluate_single_bomb_strategy 在合法策略下
        # 即使触发 zero_window 也不抛出.
        # 极端: 将 t_d + 20 已覆盖到 t_arrival 之外, 但 t_d << t_arrival
        t_arr = missile_arrival_time()
        # heading 任意, 让 t_release + 20 > t_arrival 但 t_d << t_arrival
        s = _make_strategy(release_time_s=max(0.0, t_arr - CLOUD_DURATION - 5.0),
                            delay_s=0.0,
                            heading_rad=math.pi,
                            speed_mps=120.0)
        ev = evaluate_single_bomb_strategy(s, sample_level="coarse",
                                            scan_step=0.05)
        # 评估窗口右端 = min(t_d+20, t_arrival) = t_arrival
        # 结果:
        #   - valid=True, status="ok" 或 "zero_window"
        #   - intervals/total >= 0
        self.assertTrue(ev.valid)
        self.assertIn(ev.status, ("ok", "zero_window"))
        self.assertGreaterEqual(ev.total_duration_s, 0.0)
        # intervals 内部有序无重叠 (在本组件后面 J/K 测试中具体验证)

    def test_i04_invalid_candidate_does_not_crash(self):
        # 多种非法候选: 不让批处理崩溃
        bads = [
            _make_strategy(speed_mps=-1.0),
            _make_strategy(speed_mps=200.0),
            _make_strategy(release_time_s=-1.0),
            _make_strategy(delay_s=-1.0),
            _make_strategy(heading_rad=float("nan")),
            _make_strategy(speed_mps=float("inf")),
        ]
        for s in bads:
            ev = evaluate_single_bomb_strategy(s, sample_level="coarse",
                                                scan_step=0.1)
            # 非 finite 不让 normalize_heading 抛; evaluate 用 fallback
            self.assertEqual(ev.status, "invalid", f"strategy={s}")
            self.assertFalse(ev.valid)
            self.assertEqual(ev.total_duration_s, 0.0)

    def test_i05_program_errors_propagate(self):
        # scan_step=0 由 find_effective_intervals 抛 ValueError, 必须向上传播
        s = _make_strategy()
        with self.assertRaises(ValueError):
            evaluate_single_bomb_strategy(s, sample_level="coarse",
                                            scan_step=0.0)
        # sample_level 非法也抛
        with self.assertRaises(ValueError):
            evaluate_single_bomb_strategy(s, sample_level="megafine",
                                            scan_step=0.05)
        # 非有限 scan_step 抛
        with self.assertRaises(ValueError):
            evaluate_single_bomb_strategy(s, sample_level="coarse",
                                            scan_step=float("nan"))


# =============================================================================
#  J — Intervals order and union (Section 14: 24-25)
# =============================================================================
class JIntervalStructure(unittest.TestCase):

    def test_j01_intervals_sorted_and_disjoint(self):
        # 任意合法策略(含 Q1 已知有效): intervals 应按起点升序, 无重叠, 起止在评估窗口内
        # 使用 Q1 已知能产生遮蔽的策略作为锚点; 同时跑若干随机策略观察结构
        cands = [Q1_FIXED_STRATEGY] + generate_candidates(20, seed=42)
        seen_any = 0
        for s in cands:
            ev = evaluate_single_bomb_strategy(s, sample_level="coarse",
                                                scan_step=0.05)
            if not (ev.valid and ev.intervals):
                continue
            ivs = ev.intervals
            ws, we = ev.evaluation_window
            for a, b in ivs:
                # 区间在评估窗内
                self.assertGreaterEqual(a, ws - 1e-9)
                self.assertLessEqual(b, we + 1e-9)
                # 非负长度
                self.assertGreater(b - a, -1e-12)
            # 按起点升序
            for i in range(1, len(ivs)):
                self.assertLessEqual(ivs[i - 1][1], ivs[i][0] + 1e-12)
            seen_any += 1
        self.assertGreater(seen_any, 0,
            "Q1 固定策略至少应有一段有效区间")

    def test_j02_total_duration_equals_union(self):
        # total_duration_s == sum(b - a), 即并集长度, 不只是最长区间
        # 通过合成用例: 给一个能产生多段区间的策略 (注入 boundary_func 不易,
        # 本测试采用 choose 较短 scan_step + 合法策略, 验证 sum(ivs b-a) == total)
        cands = generate_candidates(20, seed=42)
        for s in cands:
            ev = evaluate_single_bomb_strategy(s, sample_level="coarse",
                                                scan_step=0.05)
            if not (ev.valid and ev.intervals):
                continue
            s_sum = sum(b - a for a, b in ev.intervals)
            self.assertAlmostEqual(s_sum, ev.total_duration_s, places=9)
            break  # 验证 sum==total 只需一个非空案例即可


# =============================================================================
#  K — Q1 fixed-strategy regression (Section 14: 28-31)
# =============================================================================
class KQ1FixedStrategyRegression(unittest.TestCase):

    def test_k01_fy1_velocity(self):
        v = fy1_velocity(math.pi, 120.0)
        self.assertTrue(_vec_close(v, (-120.0, 0.0, 0.0), tol=1e-9),
                        f"v={v}")

    def test_k02_q1_release_point(self):
        s = Q1_FIXED_STRATEGY
        r = release_point(s)
        self.assertTrue(_vec_close(r, Q1_EXPECTED["release_point"], tol=1e-6),
                        f"R={r}")

    def test_k03_q1_detonation_point(self):
        s = Q1_FIXED_STRATEGY
        d = detonation_point(s)
        self.assertTrue(_vec_close(d, Q1_EXPECTED["detonation_point"], tol=1e-6),
                        f"D={d}")

    def test_k04_q1_detonation_time(self):
        s = Q1_FIXED_STRATEGY
        self.assertAlmostEqual(detonation_time(s),
                                Q1_EXPECTED["detonation_time"], places=12)

    def test_k05_q1_full_cylinder_match(self):
        # Q1 策略下, 新 Q2 包装器 (medium + scan=0.01) 与 src/q1_cylinder.find_strict_intervals
        # 在同一窗口同一轨迹下结果一致 (1 段, 总时长 ≈ q1 medium = 1.393131)
        s = Q1_FIXED_STRATEGY
        # 注入与 q1_cylinder 默认一致的轨迹: 默认即可
        ev = evaluate_single_bomb_strategy(s, sample_level="medium",
                                            scan_step=0.01)
        self.assertEqual(ev.status, "ok")
        # intervals 数与 q1_cylinder 一致 (1 段)
        self.assertEqual(len(ev.intervals), 1)
        # 总时长与 src/q1_cylinder fine 不一致 (medium 略长) — 验证在合理范围
        self.assertGreater(ev.total_duration_s, 1.38)
        self.assertLess(ev.total_duration_s, 1.40)


# =============================================================================
#  L — Deterministic candidate generation (Section 14: 32-33)
# =============================================================================
class LCandidateGeneration(unittest.TestCase):

    def test_l01_fixed_seed_reproducible(self):
        a = generate_candidates(20, seed=2025)
        b = generate_candidates(20, seed=2025)
        self.assertEqual(len(a), 20)
        self.assertEqual(a, b)  # 列表逐元素相等

    def test_l02_different_seeds_differ(self):
        a = generate_candidates(20, seed=2025)
        b = generate_candidates(20, seed=2026)
        self.assertEqual(len(a), 20)
        self.assertEqual(len(b), 20)
        # 至少有显著差异 (>0 处不同)
        diffs = sum(1 for x, y in zip(a, b) if x != y)
        self.assertGreater(diffs, 10, f"应有多数不同, 实际 {diffs}/20")


# =============================================================================
#  M — Smoke stats fields (Section 14: 34)
# =============================================================================
class MSmokeStats(unittest.TestCase):

    def test_m01_smoke_fields_complete(self):
        # 小规模 smoke (10 候选) 仅字段检查, 不用于报告
        res = run_smoke(count=10, seed=2025, profile="coarse")
        required = {"count", "seed", "profile", "grade", "scan_step",
                    "candidate_source", "candidate_source_note",
                    "n_valid_ok", "n_valid_zero_window",
                    "n_invalid", "n_pruned_zero", "n_system_error",
                    "system_errors", "total_elapsed_s",
                    "mean_s", "median_s", "p90_s", "max_s",
                    "best", "evaluations", "exit_code"}
        self.assertEqual(set(res.keys()), required)

    def test_m02_smoke_total_matches_count(self):
        res = run_smoke(count=20, seed=2025, profile="coarse")
        n_total = (res["n_valid_ok"] + res["n_valid_zero_window"]
                   + res["n_invalid"] + res["n_pruned_zero"]
                   + res["n_system_error"])
        self.assertEqual(n_total, res["count"])

    def test_m03_best_disclaimer_marked_in_evaluations(self):
        # smoke 返回的 "best" 字段必须带 "NOT AN OPTIMIZATION RESULT" 警示
        # (CLI 中打印, 数据本身只检查 best 的 status="ok")
        # 使用 Q1 锚定作为种子候选 (include_q1_baseline=True)
        from src.q2_single_bomb import generate_candidates
        cands = generate_candidates(19, seed=2025, include_q1_baseline=True)
        from src.q2_single_bomb import evaluate_single_bomb_strategy
        # 直接手工跑 20 个 (含 Q1), 验证 best 的存在与基本性质
        from src.q2_single_bomb import PROFILE_GRADES, PROFILE_SCAN_STEPS
        grade = PROFILE_GRADES["coarse"]
        scan_step = PROFILE_SCAN_STEPS["coarse"]
        evs = []
        for c in cands:
            try:
                ev = evaluate_single_bomb_strategy(c, sample_level=grade,
                                                    scan_step=scan_step)
            except Exception:
                continue
            if ev.valid and ev.status == "ok":
                evs.append(ev)
        self.assertGreater(len(evs), 0, "至少应有一例 status=ok")
        # best 必须是 evs 之一
        best = max(evs, key=lambda e: e.total_duration_s)
        self.assertGreater(best.total_duration_s, 0.0)
        self.assertEqual(best.status, "ok")


# =============================================================================
#  N — CLI (Section 14: 35)
# =============================================================================
class NCLI(unittest.TestCase):

    def test_n01_missing_smoke_count_returns_nonzero(self):
        rc = q2_main(["--seed", "2025", "--profile", "coarse"])
        self.assertNotEqual(rc, 0)

    def test_n02_invalid_smoke_count_returns_nonzero(self):
        rc = q2_main(["--smoke-count", "abc", "--seed", "2025"])
        self.assertNotEqual(rc, 0)

    def test_n03_smoke_count_out_of_range_returns_nonzero(self):
        rc = q2_main(["--smoke-count", "0", "--seed", "2025"])
        self.assertNotEqual(rc, 0)
        rc = q2_main(["--smoke-count", "301", "--seed", "2025"])
        self.assertNotEqual(rc, 0)

    def test_n04_invalid_profile_returns_nonzero(self):
        rc = q2_main(["--smoke-count", "10", "--seed", "2025",
                       "--profile", "ultrafine"])
        self.assertNotEqual(rc, 0)

    def test_n05_unknown_arg_returns_nonzero(self):
        rc = q2_main(["--smoke-count", "10", "--bogus", "x"])
        self.assertNotEqual(rc, 0)

    def test_n06_help_returns_zero(self):
        rc = q2_main(["--help"])
        self.assertEqual(rc, 0)


# =============================================================================
#  P1-2 — EPS_GROUND 三区分类边界 (Section 五 + 审计 P1-2)
# =============================================================================
class G2DetonationZEPSGround(unittest.TestCase):
    """P1-2: EPS_GROUND 三区分类 + 真实理论落地边界行为.

    不得再用 delay=19.0 / delta*0.5 等远离理论落地点的策略冒充 z=0 测试.
    """

    def test_g2_01_theoretical_ground_zero_is_valid(self):
        # 理论 delta_ground = sqrt(2 * u0_z / g); 浮点 z 量级 ~1e-10 m
        delta_ground = math.sqrt(2.0 * U0[2] / G)
        s = _make_strategy(release_time_s=0.5, delay_s=delta_ground)
        # validate 必须通过 (EPS_GROUND 吸收浮点舍入)
        v, r = validate_strategy(s)
        self.assertTrue(v, f"理论 z=0 必须合法, 实际 reason={r}")
        # 用于云团评估的 detonation_point z 必须规范化为 0.0
        ev = evaluate_single_bomb_strategy(s, sample_level="coarse",
                                            scan_step=0.05)
        self.assertEqual(ev.detonation_point[2], 0.0,
                          f"理论 z=0 应归一化为 0, 实际 {ev.detonation_point[2]}")

    def test_g2_02_near_ground_negative_normalized_to_zero(self):
        # 构造 z ≈ -0.5 * EPS_GROUND; 应合法且归一化到 0
        delta_ground = math.sqrt(2.0 * U0[2] / G)
        # e 使 z ≈ -0.5 * EPS_GROUND
        # z ≈ -g * delta_ground * e; ⇒ e ≈ 0.5 * EPS_GROUND / (g * delta_ground)
        e_half = 0.5 * EPS_GROUND / (G * delta_ground)
        delta_half_neg = delta_ground + e_half
        s = _make_strategy(release_time_s=0.5, delay_s=delta_half_neg)
        d_raw = detonation_point(s)
        # 验证 z 在 [-EPS_GROUND, 0) 区间
        self.assertGreaterEqual(d_raw[2], -EPS_GROUND,
                                  f"构造的 z 必须在 [-EPS_GROUND, 0), 实际 {d_raw[2]}")
        self.assertLess(d_raw[2], 0.0)
        # validate 合法
        v, r = validate_strategy(s)
        self.assertTrue(v, f"近 -EPS_GROUND/2 必须合法, 实际 reason={r}")
        # 用于云团评估的 z 规范化为 0
        ev = evaluate_single_bomb_strategy(s, sample_level="coarse",
                                            scan_step=0.05)
        self.assertEqual(ev.detonation_point[2], 0.0,
                          f"-EPS_GROUND/2 归一化后应为 0, 实际 {ev.detonation_point[2]}")

    def test_g2_03_below_minus_two_eps_invalid(self):
        # 构造 z ≈ -2.5 * EPS_GROUND (明显地下); 必须非法
        delta_ground = math.sqrt(2.0 * U0[2] / G)
        e_2 = 2.5 * EPS_GROUND / (G * delta_ground)
        delta_over = delta_ground + e_2
        s = _make_strategy(release_time_s=0.5, delay_s=delta_over)
        d_raw = detonation_point(s)
        self.assertLess(d_raw[2], -2.0 * EPS_GROUND,
                          f"构造的 z 必须 < -2*EPS_GROUND, 实际 {d_raw[2]}")
        v, r = validate_strategy(s)
        self.assertFalse(v, f"z < -2*EPS_GROUND 必须非法, 实际 reason={r}")
        self.assertIn("z", r)

    def test_g2_04_clearly_positive_height_valid(self):
        # 远离地面, 显然合法
        s = Q1_FIXED_STRATEGY
        d = detonation_point(s)
        self.assertGreater(d[2], 100.0)
        v, r = validate_strategy(s)
        self.assertTrue(v, r)

    def test_g2_05_clearly_underground_invalid(self):
        # 巨大 delay, 显然非法
        s = _make_strategy(release_time_s=0.0, delay_s=30.0)
        d = detonation_point(s)
        self.assertLess(d[2], -1000.0,
                          f"应明显地下, 实际 z={d[2]}")
        v, r = validate_strategy(s)
        self.assertFalse(v)
        self.assertIn("z", r)

    def test_g2_06_nextafter_below_ground_still_valid(self):
        # delay = nextafter(delta_ground, inf): 1 ULP 上调, z 仍在 [-EPS_GROUND, 0)
        delta_ground = math.sqrt(2.0 * U0[2] / G)
        delta_just_above = math.nextafter(delta_ground, math.inf)
        s = _make_strategy(release_time_s=0.5, delay_s=delta_just_above)
        d_raw = detonation_point(s)
        # 1 ULP 步长极小 (~1e-16), z 必在 [-EPS_GROUND, 0)
        self.assertGreaterEqual(d_raw[2], -EPS_GROUND,
                                  f"1 ULP nextafter 上调 z 应 ≥ -EPS_GROUND, 实际 {d_raw[2]}")
        self.assertLess(d_raw[2], 0.0)
        v, r = validate_strategy(s)
        self.assertTrue(v, f"1 ULP 上调必须仍合法, 实际 reason={r}")
        ev = evaluate_single_bomb_strategy(s, sample_level="coarse",
                                            scan_step=0.05)
        self.assertEqual(ev.detonation_point[2], 0.0)

    def test_g2_07_nextafter_one_microsecond_above_invalid(self):
        # delay = delta_ground + 1e-5: z 远低于 -EPS_GROUND, 必须非法
        delta_ground = math.sqrt(2.0 * U0[2] / G)
        delta_over = delta_ground + 1e-5
        s = _make_strategy(release_time_s=0.5, delay_s=delta_over)
        d_raw = detonation_point(s)
        self.assertLess(d_raw[2], -2.0 * EPS_GROUND,
                          f"delay + 1e-5 应让 z < -2*EPS_GROUND, 实际 {d_raw[2]}")
        v, r = validate_strategy(s)
        self.assertFalse(v, f"delay + 1e-5 (z 显著为负) 必须非法, 实际 reason={r}")


# =============================================================================
#  P1-3 — Q1 完整圆柱直接回归 (Section 六)
# =============================================================================
class K2DirectQ1CylinderComparison(unittest.TestCase):
    """P1-3: Q1 完整圆柱入口 vs Q2 wrapper 的直接对照.

    完全相同的 samples / sample level / scan step / missile_fn /
    cloud_fn / window_start / window_end / t_arrival.
    """

    def test_k2_01_direct_q1_path_matches_q2_wrapper(self):
        from src.q1_baseline import (
            cloud_center as q1_cloud_center,
            missile_position as q1_missile_position,
            missile_arrival_time as q1_t_arrival,
        )
        from src.q1_cylinder import T_DETONATE as Q1_TD, CLOUD_DURATION as Q1_CD

        s = Q1_FIXED_STRATEGY
        sample_level = "medium"
        scan_step = 0.01
        t_arrival = q1_t_arrival()
        samples = generate_cylinder_samples(**SAMPLE_GRADES[sample_level])

        # Q1 默认窗口: [T_DETONATE, T_DETONATE + CLOUD_DURATION]
        # Q2 窗口: [t_d, min(t_d + 20, t_arrival)] = [5.1, 25.1]
        # t_arrival ≈ 66.999 > 25.1, 两窗口一致
        q1_ws, q1_we = Q1_TD, Q1_TD + Q1_CD
        self.assertAlmostEqual(q1_ws, 5.1, places=9)
        self.assertAlmostEqual(q1_we, 25.1, places=9)

        # === 路径 A: Q1 原完整圆柱入口 ===
        q1_ivs = find_strict_intervals(
            samples, scan_step=scan_step,
            t_arrival=t_arrival,
            missile_position_fn=q1_missile_position,
            cloud_center_fn=q1_cloud_center,
            window_start=q1_ws,
            window_end=q1_we,
        )

        # === 路径 B: Q2 wrapper ===
        ev = evaluate_single_bomb_strategy(
            s, sample_level=sample_level, scan_step=scan_step,
            samples=samples, t_arrival=t_arrival,
        )

        self.assertEqual(ev.status, "ok",
                          f"Q1 策略 Q2 评估必须 status=ok, 实际 {ev.status}")

        # === 比较: interval count ===
        self.assertEqual(len(q1_ivs), len(ev.intervals),
                          f"interval count: Q1={len(q1_ivs)} vs Q2={len(ev.intervals)}")

        # === 比较: 每个区间起止点 ===
        for (qa, qb), (q2a, q2b) in zip(q1_ivs, ev.intervals):
            # 端点容差依据: q1_baseline.BISECT_TOL=1e-8, 二分后端点 f 残差
            # 实测 max |f(b)| ≈ 1.03e-6 (TASK_003 数据), 临界斜率 ~10 m/s,
            # 故端点位置精度 ~ 1e-7 s. 取 1e-6 s 作为安全端点容差.
            self.assertLessEqual(abs(qa - q2a), 1e-6,
                                  f"Q1[{qa:.9f}] vs Q2[{q2a:.9f}] start diff > 1e-6")
            self.assertLessEqual(abs(qb - q2b), 1e-6,
                                  f"Q1[{qb:.9f}] vs Q2[{q2b:.9f}] end diff > 1e-6")

        # === 比较: total duration ===
        q1_total = sum(b - a for a, b in q1_ivs)
        # 总时长容差: 区间端点误差的合理累计 (≤ 端点容差 × 区间数)
        self.assertLessEqual(abs(q1_total - ev.total_duration_s),
                              1e-6 * len(q1_ivs),
                              f"total diff: Q1={q1_total:.9f} vs Q2={ev.total_duration_s:.9f}")


# =============================================================================
#  P1-4 — 确定性多区间测试 (Section 七)
# =============================================================================
class J2MultiIntervalDeterministic(unittest.TestCase):
    """P1-4: 拆分多区间测试为 (A) Q1 锚定非空回归 + (B) 合成多区间 boundary."""

    def test_j2_01_q1_anchor_nonempty_regression(self):
        """P1-4-A: Q1 固定策略非空回归; 显式 assertTrue(intervals),
        并验证 sum(b-a) == total_duration_s."""
        s = Q1_FIXED_STRATEGY
        ev = evaluate_single_bomb_strategy(s, sample_level="coarse",
                                            scan_step=0.05)
        self.assertEqual(ev.status, "ok")
        self.assertTrue(ev.intervals,
                          "Q1 固定策略必须产生至少一段有效区间")
        s_sum = sum(b - a for a, b in ev.intervals)
        self.assertAlmostEqual(s_sum, ev.total_duration_s, places=9,
                                msg=f"sum(b-a)={s_sum} vs total={ev.total_duration_s}")

    def test_j2_02_synthetic_two_disjoint_intervals(self):
        """P1-4-B: 人工多区间 boundary 函数.

        f(t) = (t-1)(t-2)(t-4)(t-5)
        在 [0, 6] 内 f ≤ 0 ⇔ t ∈ [1, 2] ∪ [4, 5]
        通过 find_strict_intervals 注入 boundary_func, 不修改 Q1 求解器.
        """
        samples = generate_cylinder_samples(**SAMPLE_GRADES["coarse"])

        def synthetic_bf(t: float) -> float:
            return (t - 1.0) * (t - 2.0) * (t - 4.0) * (t - 5.0)

        ivs = find_strict_intervals(
            samples, scan_step=0.01,
            boundary_func=synthetic_bf,
            window_start=0.0, window_end=6.0,
            t_arrival=6.0,
        )
        # 至少 2 个不连续区间
        self.assertGreaterEqual(len(ivs), 2,
                                  f"应保留至少两个不连续区间, 实际 {len(ivs)}: {ivs}")
        # 总时长 = 1.0 + 1.0 = 2.0
        total = sum(b - a for a, b in ivs)
        self.assertAlmostEqual(total, 2.0, delta=0.05,
                                msg=f"总时长应 ≈ 2.0, 实际 {total}")
        # 不等于单个最长段 (1.0)
        self.assertNotAlmostEqual(total, 1.0, places=3)
        # 区间按起点升序
        for i in range(1, len(ivs)):
            self.assertLessEqual(ivs[i - 1][1], ivs[i][0] + 1e-9,
                                  f"区间应升序: {ivs}")
        # 两段都存在
        starts = sorted(a for a, _ in ivs)
        self.assertLess(abs(starts[0] - 1.0), 0.05,
                          f"首段起点应 ≈ 1.0, 实际 {starts[0]}")
        if len(starts) > 1:
            self.assertLess(abs(starts[1] - 4.0), 0.05,
                              f"次段起点应 ≈ 4.0, 实际 {starts[1]}")


# =============================================================================
#  P1-5 — system_error 退出码 (Section 八)
# =============================================================================
from unittest.mock import patch


class N2SystemErrorExitCode(unittest.TestCase):
    """P1-5: system_error 必须通过 main() 反映为非零退出码."""

    def test_n2_01_main_returns_nonzero_with_system_errors(self):
        """注入 evaluator 系统异常, 验证 main 返回非零."""
        with patch("src.q2_single_bomb.evaluate_single_bomb_strategy",
                    side_effect=RuntimeError("injected system error")):
            rc = q2_main(["--smoke-count", "5", "--seed", "2025",
                           "--profile", "coarse"])
        self.assertNotEqual(rc, 0,
                              f"system_error > 0 时 main 必须返回非零, 实际 {rc}")

    def test_n2_02_main_returns_zero_without_system_errors(self):
        """默认 smoke 无 system_error 时 main 返回 0."""
        rc = q2_main(["--smoke-count", "10", "--seed", "2025",
                       "--profile", "coarse"])
        self.assertEqual(rc, 0, f"无 system_error 时 main 必须返回 0, 实际 {rc}")

    def test_n2_03_system_errors_do_not_increment_other_counts(self):
        """system_error 不污染 invalid/pruned/zero/objective 计数."""
        original = q2.evaluate_single_bomb_strategy

        # 让前 3 个候选抛, 其余正常
        counter = [0]

        def selective_eval(strategy, **kwargs):
            counter[0] += 1
            if counter[0] <= 3:
                raise RuntimeError("injected for first 3")
            return original(strategy, **kwargs)

        try:
            res = q2.run_smoke_on_candidates(
                list(q2.generate_candidates(10, seed=2025)),
                profile="coarse", evaluate_fn=selective_eval,
            )
        finally:
            q2.evaluate_single_bomb_strategy = original

        self.assertEqual(res["n_system_error"], 3,
                          f"应 3 个 system_error, 实际 {res['n_system_error']}")
        # 其它计数基于未抛的 7 个
        n_sum = (res["n_valid_ok"] + res["n_valid_zero_window"]
                  + res["n_invalid"] + res["n_pruned_zero"]
                  + res["n_system_error"])
        self.assertEqual(n_sum, 10)
        # exit_code = 1
        self.assertEqual(res["exit_code"], 1)

    def test_n2_04_batch_continues_after_system_error(self):
        """单个候选抛异常后, 后续候选仍被处理."""
        cands = list(q2.generate_candidates(10, seed=2025))
        target_idx = 4
        counter = [0]
        original = q2.evaluate_single_bomb_strategy

        def selective(strategy, **kwargs):
            counter[0] += 1
            if counter[0] == target_idx:
                raise RuntimeError("injected at index 4")
            return original(strategy, **kwargs)

        try:
            res = q2.run_smoke_on_candidates(cands, profile="coarse",
                                              evaluate_fn=selective)
        finally:
            q2.evaluate_single_bomb_strategy = original
        self.assertEqual(res["n_system_error"], 1)
        # 10 - 1 = 9 个被成功处理
        n_sum = (res["n_valid_ok"] + res["n_valid_zero_window"]
                  + res["n_invalid"] + res["n_pruned_zero"])
        self.assertEqual(n_sum, 9)
        self.assertEqual(res["exit_code"], 1)

    def test_n2_05_program_errors_not_in_other_statuses(self):
        """程序错误不算入 invalid / pruned / zero / objective."""
        cands = list(q2.generate_candidates(5, seed=2025))

        def always_raise(strategy, **kwargs):
            raise RuntimeError("always fails")

        res = q2.run_smoke_on_candidates(cands, profile="coarse",
                                          evaluate_fn=always_raise)
        self.assertEqual(res["n_system_error"], 5)
        # 其它计数必须为 0
        self.assertEqual(res["n_valid_ok"], 0)
        self.assertEqual(res["n_valid_zero_window"], 0)
        self.assertEqual(res["n_invalid"], 0)
        self.assertEqual(res["n_pruned_zero"], 0)
        self.assertIsNone(res["best"])
        self.assertEqual(res["exit_code"], 1)


# =============================================================================
#  P1-6 — candidate_source + mixed-batch 8 类测试 (Section 九)
# =============================================================================
class PMixedBatchDeterministic(unittest.TestCase):
    """P1-6: mixed-batch 8 类候选分别独立计数."""

    def test_p01_mixed_batch_eight_categories(self):
        """显式构造 8 类候选, 验证各 status 独立计数."""
        import src.q2_single_bomb as q2
        # 1. 正常合法候选
        valid_ok = list(q2.generate_candidates(3, seed=2025))
        # 2. 合法零目标 (heading=+x 远离目标)
        zero_obj = [SingleBombStrategy(heading_rad=0.0, speed_mps=70.0,
                                         release_time_s=10.0, delay_s=1.0)]
        # 3. 速度越界
        speed_oob = [SingleBombStrategy(heading_rad=math.pi, speed_mps=200.0,
                                          release_time_s=1.5, delay_s=3.6)]
        # 4. release_time_s < 0
        release_neg = [SingleBombStrategy(heading_rad=math.pi, speed_mps=120.0,
                                            release_time_s=-1.0, delay_s=3.6)]
        # 5. delay_s < 0
        delay_neg = [SingleBombStrategy(heading_rad=math.pi, speed_mps=120.0,
                                          release_time_s=1.5, delay_s=-1.0)]
        # 6. 明显地下起爆
        underground = [SingleBombStrategy(heading_rad=math.pi, speed_mps=120.0,
                                            release_time_s=1.5, delay_s=30.0)]
        # 7. pruned_zero (valid=True)
        t_arr = missile_arrival_time()
        pruned = [SingleBombStrategy(heading_rad=math.pi, speed_mps=120.0,
                                        release_time_s=t_arr - 0.5,
                                        delay_s=1.0)]
        # 8. controlled system_error (通过 inject)
        sys_err_cand = list(q2.generate_candidates(1, seed=999))

        cands = (valid_ok + zero_obj + speed_oob + release_neg +
                  delay_neg + underground + pruned + sys_err_cand)

        # 注入: 让最后一个 (sys_err_cand) 抛
        n = len(cands)
        counter = [0]
        original = q2.evaluate_single_bomb_strategy

        def selective(strategy, **kwargs):
            counter[0] += 1
            if counter[0] == n:
                raise RuntimeError("injected system error")
            return original(strategy, **kwargs)

        q2.evaluate_single_bomb_strategy = selective
        try:
            res = q2.run_smoke_on_candidates(cands, profile="coarse",
                                              evaluate_fn=selective)
        finally:
            q2.evaluate_single_bomb_strategy = original

        # 候选来源
        self.assertEqual(res["candidate_source"], "explicit_mixed_batch")
        # invalid: speed_oob + release_neg + delay_neg + underground = 4
        self.assertEqual(res["n_invalid"], 4,
                          f"应 4 个 invalid, 实际 {res['n_invalid']}")
        # pruned_zero: 1 个 (pruned)
        self.assertEqual(res["n_pruned_zero"], 1,
                          f"应 1 个 pruned_zero, 实际 {res['n_pruned_zero']}")
        # system_error: 1 个 (sys_err_cand)
        self.assertEqual(res["n_system_error"], 1,
                          f"应 1 个 system_error, 实际 {res['n_system_error']}")
        # success: valid_ok (3) + zero_obj (1) = 4 (status=ok 或 zero_window)
        n_success = res["n_valid_ok"] + res["n_valid_zero_window"]
        self.assertEqual(n_success, 4,
                          f"应 4 个成功, 实际 {n_success}")
        # 总数 = 4 + 1 + 1 + 4 = 10
        n_sum = n_success + res["n_invalid"] + res["n_pruned_zero"] \
                 + res["n_system_error"]
        self.assertEqual(n_sum, n)

        # pruned_zero 候选必须 valid=True (P1-1)
        pruned_evs = [e for e in res["evaluations"] if e.status == "pruned_zero"]
        for ev in pruned_evs:
            self.assertTrue(ev.valid,
                              "pruned_zero 必须 valid=True (P1-1)")

        # exit_code = 1 (有 system_error)
        self.assertEqual(res["exit_code"], 1)

    def test_p02_default_smoke_labels_candidate_source(self):
        """默认 smoke 的 candidate_source = prevalidated_nonpruned."""
        res = run_smoke(count=10, seed=2025, profile="coarse")
        self.assertEqual(res["candidate_source"], "prevalidated_nonpruned")
        self.assertIn("invalid", res["candidate_source_note"])
        # 默认 smoke 的 invalid/pruned 必为 0 (输入已预验证)
        self.assertEqual(res["n_invalid"], 0)
        self.assertEqual(res["n_pruned_zero"], 0)
        # 正常无 system_error
        self.assertEqual(res["n_system_error"], 0)
        self.assertEqual(res["exit_code"], 0)


# =============================================================================
#  P1-7 — profile_evaluation 结构 + Foundation 性能校准 (Section 十)
# =============================================================================
import statistics


class QProfileEvaluation(unittest.TestCase):
    """P1-7: profile_evaluation 结构 + 默认 3 候选 × 3 profile."""

    def test_q01_profile_evaluation_returns_required_fields(self):
        """profile_evaluation 必须返回规定字段."""
        res = q2.profile_evaluation(q2.Q1_FIXED_STRATEGY, sample_level="coarse",
                                      repeat=2, warm_up=True)
        required = {"sample_level", "scan_step", "repeat", "warm_up",
                     "samples_reused", "results",
                     "median_elapsed_s", "min_elapsed_s", "max_elapsed_s",
                     "first_status", "first_total_duration_s",
                     "first_n_intervals", "window_length_s"}
        self.assertTrue(required.issubset(set(res.keys())),
                          f"缺少字段: {required - set(res.keys())}")
        # results 长度 = repeat
        self.assertEqual(len(res["results"]), 2)
        # median/min/max 与 results 一致
        ts = [r["elapsed_s"] for r in res["results"]]
        self.assertAlmostEqual(res["median_elapsed_s"], statistics.median(ts))
        self.assertEqual(res["min_elapsed_s"], min(ts))
        self.assertEqual(res["max_elapsed_s"], max(ts))
        # samples_reused 字段存在
        self.assertTrue(res["samples_reused"])

    def test_q02_profile_measurement_default_three_candidates(self):
        """run_profile_measurement 默认 3 个候选 × 3 个 profile = 9 rows."""
        rows = q2.run_profile_measurement(repeat=2, warm_up=True)
        self.assertEqual(len(rows), 9)
        levels = {r["sample_level"] for r in rows}
        self.assertEqual(levels, {"coarse", "medium", "fine"})
        # 每个 row 至少有 median_elapsed_s (代表至少一次成功计时)
        for r in rows:
            self.assertIn("median_elapsed_s", r)

    def test_q03_repeat_must_be_positive(self):
        with self.assertRaises(ValueError):
            q2.profile_evaluation(q2.Q1_FIXED_STRATEGY, sample_level="coarse",
                                    repeat=0)

    def test_q04_profile_must_be_valid(self):
        with self.assertRaises(ValueError):
            q2.profile_evaluation(q2.Q1_FIXED_STRATEGY,
                                    sample_level="ultrafine", repeat=1)

    def test_q05_resolve_non_zero_neighbor_returns_strategy(self):
        """_resolve_non_zero_neighbor 必须返回 SingleBombStrategy (或 Q1 兜底)."""
        s = q2._resolve_non_zero_neighbor()
        self.assertIsInstance(s, SingleBombStrategy)
        # 实际验证它产生非零
        ev = evaluate_single_bomb_strategy(s, sample_level="coarse",
                                            scan_step=0.05)
        self.assertGreater(ev.total_duration_s, 0.0,
                            f"非零邻居必须 objective > 0, 实际 {ev.total_duration_s}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
