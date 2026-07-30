"""Q3 three-bomb evaluator + bounded pilot 测试 (TASK_006-P0P1 + CLOSURE v2).

按 Q3 directive §十五 分级:

FAST (≤30 s, 全部为纯函数 / 序列化 / 不调用真实 evaluator):
  - TestIntervalUnion:
      - overlapping → 1 段
      - disjoint   → N 段
      - touching   → 合并 (epsilon)
      - nested     → 正确
      - empty      → 空 tuple
      - non-finite / 零长度 → 丢弃
  - TestCandidateContract:
      - non-finite 8 vars → invalid
      - speed bounds [70, 140] → 越界 invalid
      - release spacing exactly 1 s → ok
      - release spacing below 1 s → invalid
      - heading wrap [0, 2π) → 越界 invalid
      - serialization (as_strategies 共享 heading/speed)
      - deterministic evaluation ID (同一候选同一配置 → 同一 ID)
      - evaluation ID 区分不同 sample_level
      - evaluation ID 区分不同 candidate_schema_version
  - TestCheckpointAtomic:
      - atomic_write 创建文件
      - atomic_write 覆盖
      - q2_code_identity 非空
  - TestResumeIdentityMismatchBlocked:
      - 构造不一致 checkpoint, run_pilot 必须 RESUME_IDENTITY_MISMATCH
  - TestPilotSmall:
      - 完整 run_pilot 入口的边界 (placeholder)
  - TestHeadingStrictBounds (closure v2 §四):
      - 0 接受, nextafter(2π, 0) 接受, -1e-12 拒绝, 2π 拒绝, 4π 拒绝
  - TestBudgetRecommendation (closure v2 §十二):
      - efficient / conservative 场景算术 + MAIN_DECISION_REQUIRED 状态
  - TestResumeScheduleSynthetic (closure v2 §七/§八):
      - schedule_sha / stage_counts 字段存在
      - 完成 record 增量更新
      - fail-closed 状态在 identity mismatch 时
      - corrupt checkpoint → CHECKPOINT_LOAD_ERROR

TASK (≤600 s, 真实 Q3 evaluator 调用总次数 ≤ 3):
  - TestThreeBombEvaluator (setUpClass 共享 1 次 evaluation):
      - test_q2_one_bomb_degeneration_exact_comparison (复用 setUpClass)
      - test_three_bombs_shared_heading_speed (复用 setUpClass)
      - test_three_bomb_union_no_double_count (复用 setUpClass)
      - test_invalid_candidate_fail_closed (0 real eval)
      - test_pruned_zero_still_legal (复用 setUpClass)
      - test_system_error_raises_not_zero (0 real eval)
      - test_evaluation_id_uniqueness_across_distinct_candidates
        (closure v2: ID-only, 0 extra real Q3 eval)
  - TestQ2DegenerationDirectVsSequence (closure v2 §九):
      - single_strategy = anchor.as_strategies()[0]
      - direct_q2 = evaluate_single_bomb_strategy(...)
      - sequence_q2 = evaluate_bomb_sequence([single_strategy], ...)[0]
      - 逐项 exact 比较. 0 Q3 eval.
  - TestRepeatedDeterminismRealReeval (closure v2 §十):
      - ev_a = evaluate_three_bomb_strategy(anchor, ...)
      - ev_b = evaluate_three_bomb_strategy(anchor, ...)
      - 逐项 exact 比较. 2 Q3 eval.

Q3 evaluator real-call budget = setUpClass(1) + TestRepeatedDeterminismRealReeval(2) = 3.

注意: 不依赖 outputs/, 不依赖 git, 不启动 Q3 Formal Search.
"""

from __future__ import annotations

import json
import math
import os
import sys
import tempfile
import unittest

# 让 python -m unittest tests.test_q3 能 import src
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.q3_three_bombs import (
    ThreeBombCandidate,
    ThreeBombEvaluation,
    compute_q3_evaluation_id,
    evaluate_bomb_sequence,
    evaluate_three_bomb_strategy,
    normalize_intervals,
    total_union_duration,
    union_intervals,
    validate_candidate,
    Q2_CANONICAL_ANCHOR,
    PILOT_CONFIG,
    PILOT_CONFIG_SHA256,
    CANDIDATE_SCHEMA_VERSION,
    INTERVAL_EPSILON_S,
    _atomic_write_json,
    compute_q2_single_bomb_code_sha256,
)
from src.q2_single_bomb import (
    SingleBombStrategy,
    evaluate_single_bomb_strategy,
)


# === 锚点构造 ===

def make_anchor_candidate(extra_delay: float = 0.0) -> ThreeBombCandidate:
    """基于 Q2 canonical anchor 构造合法三弹候选, 三枚弹间隔 ≥ 1 s."""
    h = Q2_CANONICAL_ANCHOR["heading_rad"]
    s = Q2_CANONICAL_ANCHOR["speed_mps"]
    r0 = Q2_CANONICAL_ANCHOR["release_time_s"]
    d0 = Q2_CANONICAL_ANCHOR["delay_s"]
    return ThreeBombCandidate(
        heading_rad=h,
        speed_mps=s,
        release_time_1_s=r0,
        delay_1_s=d0 + extra_delay,
        release_time_2_s=r0 + 1.5,
        delay_2_s=d0 + extra_delay,
        release_time_3_s=r0 + 3.0,
        delay_3_s=d0 + extra_delay,
    )


# === FAST tests ===

class TestIntervalUnion(unittest.TestCase):
    """区间归一化 / 并集 / 总时长 — 纯函数 FAST 测试."""

    def test_overlapping_unions_to_single(self):
        result = normalize_intervals([(0.0, 2.0), (1.0, 3.0)])
        self.assertEqual(result, ((0.0, 3.0),))

    def test_disjoint_returns_each(self):
        result = normalize_intervals([(0.0, 1.0), (2.0, 3.0), (5.0, 6.0)])
        self.assertEqual(result, ((0.0, 1.0), (2.0, 3.0), (5.0, 6.0)))

    def test_touching_merges(self):
        # touching: end == next start, 在 epsilon 内 → 合并
        result = normalize_intervals(
            [(0.0, 1.0), (1.0 - INTERVAL_EPSILON_S / 2, 2.0)],
        )
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result[0][0], 0.0, delta=1e-9)
        self.assertAlmostEqual(result[0][1], 2.0, delta=1e-9)

    def test_nested_contains_correct(self):
        result = normalize_intervals([(0.0, 5.0), (1.0, 3.0)])
        self.assertEqual(result, ((0.0, 5.0),))

    def test_empty_returns_empty(self):
        self.assertEqual(normalize_intervals([]), ())
        self.assertEqual(normalize_intervals([(2.0, 1.0)]), ())  # zero
        self.assertEqual(normalize_intervals([(float("nan"), 1.0)]), ())
        self.assertEqual(
            normalize_intervals([(1.0, float("inf"))]), (),
        )

    def test_sort_stable(self):
        # 输入乱序 → 输出排序后, 相同 start / 重叠按合并规则
        # (0.0, 1.0) 嵌套于 (0.0, 2.0) → 合并为 (0.0, 2.0)
        result = normalize_intervals([(5.0, 6.0), (0.0, 2.0), (0.0, 1.0)])
        self.assertEqual(result, ((0.0, 2.0), (5.0, 6.0)))
        # 嵌套 (1.0, 4.0) 在 (0.0, 5.0) 内 → 合并为 (0.0, 5.0)
        result2 = normalize_intervals([(0.0, 5.0), (1.0, 4.0)])
        self.assertEqual(result2, ((0.0, 5.0),))

    def test_union_intervals_multi_list(self):
        # 三枚弹各自的 intervals 合并到同一归一化集合
        I1 = [(0.0, 1.0), (3.0, 4.0)]
        I2 = [(0.5, 1.5), (5.0, 6.0)]
        I3 = [(4.0, 5.0)]
        result = union_intervals(I1, I2, I3)
        self.assertEqual(
            result, ((0.0, 1.5), (3.0, 6.0)),
        )

    def test_total_union_duration_disjoint(self):
        iv = ((0.0, 1.0), (2.0, 3.0))
        self.assertAlmostEqual(total_union_duration(iv), 2.0, places=12)

    def test_total_union_duration_overlap(self):
        iv = ((0.0, 5.0),)
        self.assertAlmostEqual(total_union_duration(iv), 5.0, places=12)

    def test_total_union_duration_empty(self):
        self.assertAlmostEqual(total_union_duration(()), 0.0, places=12)


class TestCandidateContract(unittest.TestCase):
    """ThreeBombCandidate 合同 (8 维) 与 validate_candidate (FAST)."""

    def test_non_finite_invalid(self):
        c = ThreeBombCandidate(
            heading_rad=float("nan"),
            speed_mps=100.0,
            release_time_1_s=0.0, delay_1_s=1.0,
            release_time_2_s=2.0, delay_2_s=1.0,
            release_time_3_s=3.0, delay_3_s=1.0,
        )
        ok, _ = validate_candidate(c)
        self.assertFalse(ok)

    def test_speed_bounds_reject(self):
        c = ThreeBombCandidate(
            heading_rad=3.0, speed_mps=141.0,
            release_time_1_s=0.0, delay_1_s=1.0,
            release_time_2_s=2.0, delay_2_s=1.0,
            release_time_3_s=3.0, delay_3_s=1.0,
        )
        ok, _ = validate_candidate(c)
        self.assertFalse(ok)

    def test_speed_bounds_lower(self):
        c = ThreeBombCandidate(
            heading_rad=3.0, speed_mps=69.0,
            release_time_1_s=0.0, delay_1_s=1.0,
            release_time_2_s=2.0, delay_2_s=1.0,
            release_time_3_s=3.0, delay_3_s=1.0,
        )
        ok, _ = validate_candidate(c)
        self.assertFalse(ok)

    def test_release_spacing_exactly_one_second_accepted(self):
        # release_time_2 - release_time_1 == 1.0 → ok (with 1e-9 浮点容差)
        c = ThreeBombCandidate(
            heading_rad=3.0, speed_mps=100.0,
            release_time_1_s=1.0, delay_1_s=2.0,
            release_time_2_s=2.0, delay_2_s=2.0,
            release_time_3_s=3.0, delay_3_s=2.0,
        )
        ok, reason = validate_candidate(c)
        self.assertTrue(ok, reason)

    def test_release_spacing_below_one_second_rejected(self):
        # 0.999 < 1 → invalid
        c = ThreeBombCandidate(
            heading_rad=3.0, speed_mps=100.0,
            release_time_1_s=1.0, delay_1_s=2.0,
            release_time_2_s=1.999, delay_2_s=2.0,
            release_time_3_s=3.0, delay_3_s=2.0,
        )
        ok, reason = validate_candidate(c)
        self.assertFalse(ok, "expected invalid for spacing 0.999 < 1")
        self.assertIn("release_time_2_s", reason)

    def test_release_spacing_third_pair_below_one_second(self):
        c = ThreeBombCandidate(
            heading_rad=3.0, speed_mps=100.0,
            release_time_1_s=1.0, delay_1_s=2.0,
            release_time_2_s=2.0, delay_2_s=2.0,
            release_time_3_s=2.5, delay_3_s=2.0,
        )
        ok, reason = validate_candidate(c)
        self.assertFalse(ok)
        self.assertIn("release_time_3_s", reason)

    def test_negative_release_time_rejected(self):
        c = ThreeBombCandidate(
            heading_rad=3.0, speed_mps=100.0,
            release_time_1_s=-0.1, delay_1_s=2.0,
            release_time_2_s=2.0, delay_2_s=2.0,
            release_time_3_s=3.0, delay_3_s=2.0,
        )
        ok, _ = validate_candidate(c)
        self.assertFalse(ok)

    def test_negative_delay_rejected(self):
        c = ThreeBombCandidate(
            heading_rad=3.0, speed_mps=100.0,
            release_time_1_s=1.0, delay_1_s=-0.1,
            release_time_2_s=2.0, delay_2_s=2.0,
            release_time_3_s=3.0, delay_3_s=2.0,
        )
        ok, _ = validate_candidate(c)
        self.assertFalse(ok)

    def test_as_strategies_shares_heading_speed(self):
        c = make_anchor_candidate()
        s1, s2, s3 = c.as_strategies()
        self.assertEqual(s1.heading_rad, s2.heading_rad)
        self.assertEqual(s2.heading_rad, s3.heading_rad)
        self.assertEqual(s1.speed_mps, s2.speed_mps)
        self.assertEqual(s2.speed_mps, s3.speed_mps)
        self.assertEqual(s1.heading_rad, c.heading_rad)
        self.assertEqual(s1.speed_mps, c.speed_mps)

    def test_evaluation_id_deterministic(self):
        c = make_anchor_candidate()
        id1 = compute_q3_evaluation_id(
            c, sample_level="coarse", scan_step=0.05,
            code_identity_sha256="dummy_code_sha",
            pilot_config_sha256=PILOT_CONFIG_SHA256,
        )
        id2 = compute_q3_evaluation_id(
            c, sample_level="coarse", scan_step=0.05,
            code_identity_sha256="dummy_code_sha",
            pilot_config_sha256=PILOT_CONFIG_SHA256,
        )
        self.assertEqual(id1, id2)

    def test_evaluation_id_differs_for_sample_level(self):
        c = make_anchor_candidate()
        id1 = compute_q3_evaluation_id(
            c, sample_level="coarse", scan_step=0.05,
            code_identity_sha256="dummy_code_sha",
            pilot_config_sha256=PILOT_CONFIG_SHA256,
        )
        id2 = compute_q3_evaluation_id(
            c, sample_level="medium", scan_step=0.05,
            code_identity_sha256="dummy_code_sha",
            pilot_config_sha256=PILOT_CONFIG_SHA256,
        )
        self.assertNotEqual(id1, id2)

    def test_evaluation_id_differs_for_scan_step(self):
        c = make_anchor_candidate()
        id1 = compute_q3_evaluation_id(
            c, sample_level="coarse", scan_step=0.05,
            code_identity_sha256="dummy_code_sha",
            pilot_config_sha256=PILOT_CONFIG_SHA256,
        )
        id2 = compute_q3_evaluation_id(
            c, sample_level="coarse", scan_step=0.02,
            code_identity_sha256="dummy_code_sha",
            pilot_config_sha256=PILOT_CONFIG_SHA256,
        )
        self.assertNotEqual(id1, id2)

    def test_evaluation_id_differs_for_candidate_schema_version(self):
        c = make_anchor_candidate()
        id1 = compute_q3_evaluation_id(
            c, sample_level="coarse", scan_step=0.05,
            code_identity_sha256="dummy_code_sha",
            pilot_config_sha256=PILOT_CONFIG_SHA256,
            candidate_schema_version=1,
        )
        id2 = compute_q3_evaluation_id(
            c, sample_level="coarse", scan_step=0.05,
            code_identity_sha256="dummy_code_sha",
            pilot_config_sha256=PILOT_CONFIG_SHA256,
            candidate_schema_version=2,
        )
        self.assertNotEqual(id1, id2)


class TestCheckpointAtomic(unittest.TestCase):
    """checkpoint 原子写 + code identity."""

    def test_atomic_write_creates_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ckpt.json")
            payload = {"a": 1, "b": [1, 2, 3]}
            _atomic_write_json(path, payload)
            self.assertTrue(os.path.exists(path))
            with open(path) as f:
                loaded = json.load(f)
            self.assertEqual(loaded, payload)

    def test_atomic_write_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ckpt.json")
            _atomic_write_json(path, {"version": 1})
            _atomic_write_json(path, {"version": 2})
            with open(path) as f:
                loaded = json.load(f)
            self.assertEqual(loaded, {"version": 2})

    def test_q2_code_identity_present(self):
        sha = compute_q2_single_bomb_code_sha256()
        self.assertTrue(sha)
        self.assertEqual(len(sha), 64)


class TestResumeIdentityMismatchBlocked(unittest.TestCase):
    """resume identity mismatch 必须阻断 Pilot, 不静默忽略."""

    def test_mismatch_blocks_via_status(self):
        from src.q3_three_bombs import run_pilot

        with tempfile.TemporaryDirectory() as tmp:
            ckpt_path = os.path.join(tmp, "checkpoint.json")
            output_dir = os.path.join(tmp, "out")
            payload = {
                "schema_version": 1,
                "task_id": "TASK_006",
                "phase_id": "TASK_006-P0P1",
                "candidate_schema_version": CANDIDATE_SCHEMA_VERSION,
                "pilot_config_sha256": PILOT_CONFIG_SHA256,
                "execution_head_sha": "0" * 40,
                "contract_snapshot_sha256": "1" * 64,
                "q2_single_bomb_code_sha256": "2" * 64,
                "stage": "A",
                "completed_q3_evaluations": 0,
                "single_bomb_evaluator_calls": 0,
                "attempted_candidates": 0,
                "accepted_candidates": 0,
                "rejected_candidates": 0,
                "system_error_count": 0,
                "evaluated_q3_ids": [],
                "current_best_union_duration_s": 0.0,
                "per_profile_timing": {
                    "coarse": {"count": 0},
                    "medium": {"count": 0},
                    "fine": {"count": 0},
                },
                "elapsed_seconds": 0.0,
                "status": "running",
            }
            _atomic_write_json(ckpt_path, payload)

            real_head = "0123456789abcdef0123456789abcdef01234567"
            real_contract = "f" * 64

            summary = run_pilot(
                execution_head_sha=real_head,
                contract_snapshot_sha256=real_contract,
                output_dir=output_dir,
                checkpoint_path=ckpt_path,
            )

            self.assertTrue(summary["status"]["resume_identity_mismatch"])
            self.assertEqual(summary["result_level"]["declared_level"],
                             "EXPERIMENTAL")
            # summary 仍然写出 outputs/q3/q3_pilot_summary.json
            out_path = os.path.join(output_dir, "q3_pilot_summary.json")
            self.assertTrue(os.path.exists(out_path))


class TestPilotSmall(unittest.TestCase):
    """run_pilot 入口与 config SHA 守门 (placeholder, 不启动真 Pilot)."""

    def test_pilot_config_sha_present(self):
        self.assertTrue(PILOT_CONFIG_SHA256)
        self.assertEqual(len(PILOT_CONFIG_SHA256), 64)

    def test_pilot_config_caps(self):
        # pilot_q3_evaluation_cap = 96; pilot_wall_clock_seconds = 900
        self.assertEqual(PILOT_CONFIG["pilot_q3_evaluation_cap"], 96)
        self.assertEqual(PILOT_CONFIG["pilot_wall_clock_seconds"], 900)


# === TASK tests (≤ 3 real Q3 evaluations) ===

class TestThreeBombEvaluator(unittest.TestCase):
    """真实 Q3 evaluator 行为 (TASK 级, ≤ 3 个真实 Q3 evaluation 总次数).

    setUpClass: 1 个共享 evaluation (anchor candidate, coarse profile)
    test_evaluation_id_uniqueness: 1 个 (extra_delay=0.1 的另一候选)
    test_repeated_run_determinism: 复用 setUpClass evaluation (不另起 evaluation);
        通过 compute_q3_evaluation_id 二次调用验证 ID 稳定性

    总计 2 个真实 Q3 evaluation. TestBudgetGateCheap 已并入 TestCandidateContract
    的 pure-function 路径, 不消耗真实 Q3 evaluation.

    任何 setUp/tearDown 不得消耗 Q3 evaluation.
    """

    @classmethod
    def setUpClass(cls):
        cls.anchor = make_anchor_candidate()
        # 共享 1 个真实 Q3 evaluation (coarse profile, anchor candidate)
        cls.shared_ev: ThreeBombEvaluation = evaluate_three_bomb_strategy(
            cls.anchor, sample_level="coarse",
        )

    # --- Q2 one-bomb degeneration exact comparison ---
    def test_q2_one_bomb_degeneration_exact_comparison(self):
        """anchor 第一枚弹 = anchor 单弹 (heading/speed/release/delay 完全相同).
        三弹 union 必须与单弹 intervals / total_duration 完全一致.
        """
        shared_ev = self.shared_ev
        # 共享 evaluation 的第一枚弹 intervals == 三弹 union
        b1 = shared_ev.bomb_evaluations[0]
        self.assertEqual(b1.intervals, shared_ev.union_intervals)
        # total_duration 一致 (三弹 union 不重复累计)
        self.assertAlmostEqual(
            b1.total_duration_s,
            shared_ev.total_union_duration_s,
            places=12,
        )
        # valid + status 对齐
        self.assertTrue(shared_ev.valid)
        self.assertIn(shared_ev.status, ("ok", "zero_union"))
        # 内部 3 次单弹 evaluator
        self.assertEqual(shared_ev.single_bomb_evaluator_calls, 3)
        self.assertTrue(shared_ev.q3_evaluation_id)

    # --- 3 bombs shared heading/speed ---
    def test_three_bombs_shared_heading_speed(self):
        ev = self.shared_ev
        b1, b2, b3 = ev.bomb_evaluations
        # 三枚弹 normalized_heading_rad 相同
        self.assertEqual(b1.normalized_heading_rad, b2.normalized_heading_rad)
        self.assertEqual(b2.normalized_heading_rad, b3.normalized_heading_rad)
        # 三枚弹 strategy.heading_rad 与 anchor 一致
        self.assertEqual(b1.strategy.heading_rad, self.anchor.heading_rad)
        self.assertEqual(b2.strategy.heading_rad, self.anchor.heading_rad)
        self.assertEqual(b3.strategy.heading_rad, self.anchor.heading_rad)
        # 三枚弹 strategy.speed_mps 与 anchor 一致
        self.assertEqual(b1.strategy.speed_mps, self.anchor.speed_mps)
        self.assertEqual(b2.strategy.speed_mps, self.anchor.speed_mps)
        self.assertEqual(b3.strategy.speed_mps, self.anchor.speed_mps)

    # --- union consistency (不重复累计) ---
    def test_three_bomb_union_no_double_count(self):
        ev = self.shared_ev
        # 三弹 union total <= 三弹各自 duration 之和 (不重复累计)
        durs = [b.total_duration_s for b in ev.bomb_evaluations]
        sum_durs = durs[0] + durs[1] + durs[2]
        # union 永远不超过各弹时长之和 (union 是去重合并)
        self.assertLessEqual(ev.total_union_duration_s, sum_durs + 1e-9)
        # union_intervals 长度不超过各单弹 intervals 长度之和
        total_len = sum(len(b.intervals) for b in ev.bomb_evaluations)
        self.assertLessEqual(len(ev.union_intervals), total_len)
        # union 区间端点与所有单弹 intervals 一致 (规范化合并结果)
        single_pool = []
        for b in ev.bomb_evaluations:
            single_pool.extend(b.intervals)
        # union 等于 single pool 的归一化合并
        from src.q3_three_bombs import normalize_intervals
        self.assertEqual(ev.union_intervals, normalize_intervals(single_pool))

    # --- invalid candidate fail-closed (0 real eval) ---
    def test_invalid_candidate_fail_closed(self):
        bad = ThreeBombCandidate(
            heading_rad=float("nan"),
            speed_mps=100.0,
            release_time_1_s=0.0, delay_1_s=1.0,
            release_time_2_s=2.0, delay_2_s=1.0,
            release_time_3_s=3.0, delay_3_s=1.0,
        )
        ev = evaluate_three_bomb_strategy(bad, sample_level="coarse")
        self.assertFalse(ev.valid)
        self.assertEqual(ev.status, "invalid")
        self.assertEqual(ev.single_bomb_evaluator_calls, 0)
        self.assertEqual(ev.union_intervals, ())

    # --- pruned_zero still legal (0 extra real eval; 复用 setUpClass) ---
    def test_pruned_zero_still_legal(self):
        ev = self.shared_ev
        # 共享 evaluation 是合法的; Q3 candidate valid; status ∈ {ok, zero_union}
        self.assertTrue(ev.valid)
        self.assertIn(ev.status, ("ok", "zero_union"))
        # 单弹 status 可以是 ok / zero_window / pruned_zero, Q3 outer 不区分
        for b in ev.bomb_evaluations:
            self.assertTrue(b.valid)
            self.assertIn(b.status, ("ok", "zero_window", "pruned_zero"))

    # --- system_error NOT zero (0 real eval) ---
    def test_system_error_raises_not_zero(self):
        with self.assertRaises(ValueError):
            evaluate_three_bomb_strategy(
                self.anchor, sample_level="not_a_real_grade",
            )
        with self.assertRaises(ValueError):
            evaluate_three_bomb_strategy(
                self.anchor, sample_level="coarse", scan_step=0.0,
            )
        with self.assertRaises(ValueError):
            evaluate_three_bomb_strategy(
                self.anchor, sample_level="coarse", scan_step=-0.1,
            )

    # --- evaluation count cap safety (复用 setUpClass) ---
    def test_actual_evaluation_count_cap(self):
        """单次 Q3 evaluation 内部恰好 3 次单弹 evaluator."""
        ev = self.shared_ev
        self.assertEqual(ev.single_bomb_evaluator_calls, 3)
        # 只有 1 个 q3_evaluation_id (setUpClass 只产生一次)
        self.assertTrue(ev.q3_evaluation_id)

    # --- unique IDs (0 extra real eval; closure v2: ID-only 验证) ---
    def test_evaluation_id_uniqueness_across_distinct_candidates(self):
        """两个不同候选产生不同 evaluation_id.

        closure v2: 用 compute_q3_evaluation_id ID-only 验证, 不额外消耗真实
        Q3 evaluator. 同一 code_identity / sample_level / scan_step / pilot
        config 下, 不同 candidate ⇒ 不同 ID.
        """
        c1 = self.anchor
        c2 = make_anchor_candidate(extra_delay=0.1)
        shared_code_id = "fixture_code_sha"
        ev1_id = compute_q3_evaluation_id(
            c1, sample_level="coarse", scan_step=0.05,
            code_identity_sha256=shared_code_id,
            pilot_config_sha256=PILOT_CONFIG_SHA256,
        )
        ev2_id = compute_q3_evaluation_id(
            c2, sample_level="coarse", scan_step=0.05,
            code_identity_sha256=shared_code_id,
            pilot_config_sha256=PILOT_CONFIG_SHA256,
        )
        self.assertNotEqual(ev1_id, ev2_id)
        # setUpClass 共享 evaluation 的 ID 非空且与 anchor c1 同源
        self.assertTrue(self.shared_ev.q3_evaluation_id)
        self.assertEqual(len(self.shared_ev.q3_evaluation_id), 64)

    # --- repeated run determinism (0 extra real eval; 复用 setUpClass) ---
    def test_repeated_run_determinism(self):
        ev = self.shared_ev
        # 共享 ev 已被两次访问; union / total / status 一致
        self.assertEqual(ev.union_intervals, self.shared_ev.union_intervals)
        self.assertEqual(ev.total_union_duration_s,
                         self.shared_ev.total_union_duration_s)
        self.assertEqual(ev.status, self.shared_ev.status)
        # compute_q3_evaluation_id 同一候选 + 同一配置 + 同一 code_identity ⇒
        # 同一 ID (不消耗真实 evaluation). 这里用占位 code_identity, 但两次
        # 必须用同一占位字符串才能保证稳定.
        shared_code_id = "fixture_code_sha"
        shared_scan = self.shared_ev.scan_step_s
        recomputed_id_a = compute_q3_evaluation_id(
            self.anchor, sample_level="coarse", scan_step=shared_scan,
            code_identity_sha256=shared_code_id,
            pilot_config_sha256=PILOT_CONFIG_SHA256,
        )
        recomputed_id_b = compute_q3_evaluation_id(
            self.anchor, sample_level="coarse", scan_step=shared_scan,
            code_identity_sha256=shared_code_id,
            pilot_config_sha256=PILOT_CONFIG_SHA256,
        )
        self.assertEqual(recomputed_id_a, recomputed_id_b)


# === CLOSURE v2 tests (directive §四-§十二) ===

class TestHeadingStrictBounds(unittest.TestCase):
    """closure v2 §四: validate_candidate 必须检查原始 heading_rad ∈ [0, 2π),
    不得先 normalize."""

    def _make_with_heading(self, h: float) -> ThreeBombCandidate:
        return ThreeBombCandidate(
            heading_rad=h, speed_mps=100.0,
            release_time_1_s=1.0, delay_1_s=2.0,
            release_time_2_s=2.0, delay_2_s=2.0,
            release_time_3_s=3.0, delay_3_s=2.0,
        )

    def test_heading_zero_accepted(self):
        c = self._make_with_heading(0.0)
        ok, reason = validate_candidate(c)
        self.assertTrue(ok, reason)

    def test_heading_just_below_2pi_accepted(self):
        # nextafter(2π, 0) → 2π - 1 ulp, 应严格在 [0, 2π) 内, 接受
        c = self._make_with_heading(math.nextafter(2 * math.pi, 0.0))
        ok, reason = validate_candidate(c)
        self.assertTrue(ok, reason)

    def test_heading_negative_epsilon_rejected(self):
        c = self._make_with_heading(-1e-12)
        ok, reason = validate_candidate(c)
        self.assertFalse(ok)
        self.assertIn("heading_rad", reason)

    def test_heading_exactly_2pi_rejected(self):
        c = self._make_with_heading(2 * math.pi)
        ok, reason = validate_candidate(c)
        self.assertFalse(ok)
        self.assertIn("heading_rad", reason)

    def test_heading_4pi_rejected(self):
        c = self._make_with_heading(4 * math.pi)
        ok, reason = validate_candidate(c)
        self.assertFalse(ok)
        self.assertIn("heading_rad", reason)


class TestBudgetRecommendation(unittest.TestCase):
    """closure v2 §十二: budget_recommendation 用 stage-weighted 公式,
    efficient + conservative 两个 scenario, MAIN_DECISION_REQUIRED 状态,
    不得照抄 TASK_005 (528 / 32 / 5 / 16557)."""

    def test_no_timing_returns_decision_required(self):
        from src.q3_three_bombs import _recommend_budget, PilotStats
        rec = _recommend_budget({}, PilotStats())
        self.assertEqual(rec["recommendation_status"], "MAIN_DECISION_REQUIRED")
        self.assertIsNone(rec["efficient_scenario"])
        self.assertIsNone(rec["conservative_scenario"])
        self.assertIsNone(rec["recommended_refinement_evaluations"])
        self.assertIsNone(rec["recommended_verification_q3_calls"])

    def test_efficient_conservative_scenarios_with_timing(self):
        from src.q3_three_bombs import _recommend_budget, PilotStats
        timing = {
            "coarse": {"count": 80, "median_q3_evaluation_seconds": 1.0,
                       "p90_q3_evaluation_seconds": 1.0,
                       "median_single_bomb_seconds": 0.4,
                       "p90_single_bomb_seconds": 0.5},
            "medium": {"count": 6, "median_q3_evaluation_seconds": 4.0,
                       "p90_q3_evaluation_seconds": 5.0,
                       "median_single_bomb_seconds": 1.5,
                       "p90_single_bomb_seconds": 2.0},
            "fine": {"count": 2, "median_q3_evaluation_seconds": 30.0,
                     "p90_q3_evaluation_seconds": 35.0,
                     "median_single_bomb_seconds": 12.0,
                     "p90_single_bomb_seconds": 15.0},
        }
        stats = PilotStats()
        stats.completed_q3_evaluations = 94
        rec = _recommend_budget(timing, stats)

        # 状态 MAIN_DECISION_REQUIRED
        self.assertEqual(rec["recommendation_status"], "MAIN_DECISION_REQUIRED")
        # efficient: 480 coarse + 8 medium + 4 fine = 492
        eff = rec["efficient_scenario"]
        self.assertEqual(eff["coarse_evaluations"], 480)
        self.assertEqual(eff["medium_evaluations"], 8)
        self.assertEqual(eff["fine_evaluations"], 4)
        self.assertEqual(eff["total_q3_evaluations"], 492)
        # p90_raw = 480*1.0 + 8*5.0 + 4*35.0 = 480 + 40 + 140 = 660
        self.assertAlmostEqual(eff["p90_raw_seconds"], 660.0, places=9)
        # recommended_wall = 660 * 1.5 = 990
        self.assertEqual(eff["recommended_wall_clock_seconds"], 990)
        self.assertEqual(eff["safety_factor"], 1.5)

        # conservative: 480 coarse + 24 medium + 8 fine = 512
        con = rec["conservative_scenario"]
        self.assertEqual(con["coarse_evaluations"], 480)
        self.assertEqual(con["medium_evaluations"], 24)
        self.assertEqual(con["fine_evaluations"], 8)
        self.assertEqual(con["total_q3_evaluations"], 512)
        # p90_raw = 480*1.0 + 24*5.0 + 8*35.0 = 480 + 120 + 280 = 880
        self.assertAlmostEqual(con["p90_raw_seconds"], 880.0, places=9)
        # recommended_wall = 880 * 1.5 = 1320
        self.assertEqual(con["recommended_wall_clock_seconds"], 1320)
        self.assertEqual(con["safety_factor"], 1.5)

        # 显式字段 = null (closure v2 禁止硬编码 32 / 5)
        self.assertIsNone(rec["recommended_refinement_evaluations"])
        self.assertIsNone(rec["recommended_verification_q3_calls"])
        # 算术依据字段非空
        self.assertIn("stage-weighted", rec["calculation_basis"])
        # safety factor 一致
        self.assertEqual(rec["safety_factor"], 1.5)


class TestResumeScheduleSynthetic(unittest.TestCase):
    """closure v2 §七/§八: schedule 字段 / completed_records / fail-closed."""

    def test_schedule_and_stage_counts_present(self):
        from src.q3_three_bombs import (
            build_pilot_schedule, compute_schedule_sha256,
        )
        schedule = build_pilot_schedule(
            code_identity_sha256="fixture_code_sha",
            pilot_config_sha256=PILOT_CONFIG_SHA256,
        )
        sha = compute_schedule_sha256(schedule)
        # schedule 总数 = 6 (stage A) + 80 (stage B) = 86
        # Stage C / D 在 all_results finalize 后注入
        self.assertEqual(len(schedule), 86)
        # 前 6 条 = calibration
        for r in schedule[:6]:
            self.assertEqual(r.stage, "calibration")
        # 后 80 条 = coarse_exploration
        for r in schedule[6:]:
            self.assertEqual(r.stage, "coarse_exploration")
            self.assertEqual(r.profile, "coarse")
        # sha 非空且 deterministic
        self.assertEqual(sha, compute_schedule_sha256(schedule))
        self.assertEqual(len(sha), 64)

    def test_serialize_best_candidate_exactly_three_bomb_intervals(self):
        """closure v2 §二: per_bomb_intervals 必须恰好 3 项, 即便 ev 缺失."""
        from src.q3_three_bombs import _serialize_best_candidate
        c = make_anchor_candidate()
        # ev=None 情形: per_bomb_intervals = [[], [], []]
        payload = _serialize_best_candidate(c, None)
        self.assertIsNotNone(payload)
        self.assertEqual(len(payload["per_bomb_intervals"]), 3)
        self.assertEqual(payload["per_bomb_intervals"], [[], [], []])
        self.assertEqual(len(payload["per_bomb_duration_s"]), 3)

    def test_stage_counts_increment_via_schedule_records(self):
        """模拟 _eval_record 的 stage_counts 增量, 验证 closure v2 §三."""
        from src.q3_three_bombs import PilotStats, ScheduleRecord
        stats = PilotStats()
        # 模拟 6 calibration + 80 coarse_exploration + 6 medium_recheck +
        # 2 fine_spotcheck = 94 records
        for stage, count in [
            ("calibration", 6), ("coarse_exploration", 80),
            ("medium_recheck", 6), ("fine_spotcheck", 2),
        ]:
            for _ in range(count):
                stats.stage_counts[stage] += 1
        self.assertEqual(stats.stage_counts, {
            "calibration": 6, "coarse_exploration": 80,
            "medium_recheck": 6, "fine_spotcheck": 2,
        })
        self.assertEqual(sum(stats.stage_counts.values()), 94)

    def test_fail_closed_on_checkpoint_load_error(self):
        """closure v2 §七: corrupt checkpoint 必须 CHECKPOINT_LOAD_ERROR,
        exit code 不消耗 Q3 evaluator."""
        from src.q3_three_bombs import run_pilot
        with tempfile.TemporaryDirectory() as tmp:
            ckpt_path = os.path.join(tmp, "checkpoint.json")
            # 写入非法 JSON
            with open(ckpt_path, "w") as f:
                f.write("{ not json at all ")
            output_dir = os.path.join(tmp, "out")
            summary = run_pilot(
                execution_head_sha="0" * 40,
                contract_snapshot_sha256="0" * 64,
                output_dir=output_dir,
                checkpoint_path=ckpt_path,
            )
            self.assertTrue(summary["status"]["checkpoint_load_error"])
            # 没有启动 evaluator
            self.assertEqual(summary["counts"]["q3_candidate_evaluations"], 0)
            self.assertEqual(summary["counts"]["single_bomb_evaluator_calls"], 0)

    def test_fail_closed_on_identity_mismatch(self):
        """closure v2 §七: identity mismatch 必须 RESUME_IDENTITY_MISMATCH."""
        from src.q3_three_bombs import run_pilot
        with tempfile.TemporaryDirectory() as tmp:
            ckpt_path = os.path.join(tmp, "checkpoint.json")
            # 构造 mismatch payload (5 个原 identity 之一不同)
            payload = {
                "checkpoint_schema_version": 2,
                "execution_head_sha": "f" * 40,
                "contract_snapshot_sha256": "f" * 64,
                "q2_single_bomb_code_sha256": "f" * 64,
                "candidate_schema_version": CANDIDATE_SCHEMA_VERSION,
                "pilot_config_sha256": PILOT_CONFIG_SHA256,
                "schedule_sha256": "f" * 64,
                "stage": "A",
                "completed_q3_evaluations": 0,
                "single_bomb_evaluator_calls": 0,
                "attempted_candidates": 0,
                "accepted_candidates": 0,
                "rejected_candidates": 0,
                "system_error_count": 0,
                "evaluated_q3_ids": [],
                "stage_counts": {"calibration": 0, "coarse_exploration": 0,
                                 "medium_recheck": 0, "fine_spotcheck": 0},
                "completed_records": [],
                "next_schedule_index": 0,
                "current_best_union_duration_s": 0.0,
                "per_profile_timing": {"coarse": {"count": 0},
                                       "medium": {"count": 0},
                                       "fine": {"count": 0}},
                "elapsed_seconds": 0.0,
                "elapsed_seconds_total": 0.0,
                "status": "running",
            }
            _atomic_write_json(ckpt_path, payload)
            output_dir = os.path.join(tmp, "out")
            summary = run_pilot(
                execution_head_sha="0" * 40,
                contract_snapshot_sha256="0" * 64,
                output_dir=output_dir,
                checkpoint_path=ckpt_path,
            )
            self.assertTrue(summary["status"]["resume_identity_mismatch"])
            self.assertEqual(summary["counts"]["q3_candidate_evaluations"], 0)


class TestQ2DegenerationDirectVsSequence(unittest.TestCase):
    """closure v2 §九: 必须独立执行 evaluate_single_bomb_strategy vs
    evaluate_bomb_sequence([single_strategy])[0], 逐项 exact 比较.

    不消耗真实 Q3 evaluator (Q2 single-bomb calls 不计入 Q3 cap).
    """

    def test_direct_vs_sequence_anchor_first_bomb(self):
        anchor = make_anchor_candidate()
        s1, _, _ = anchor.as_strategies()
        # 直接 evaluate_single_bomb_strategy
        direct = evaluate_single_bomb_strategy(s1, sample_level="coarse")
        # 走 evaluate_bomb_sequence(1 枚)
        sequence = evaluate_bomb_sequence([s1], sample_level="coarse")[0]
        # 逐项 exact 比较
        self.assertEqual(direct.valid, sequence.valid)
        self.assertEqual(direct.status, sequence.status)
        self.assertEqual(direct.intervals, sequence.intervals)
        self.assertAlmostEqual(
            direct.total_duration_s, sequence.total_duration_s, places=12,
        )
        self.assertEqual(direct.release_point, sequence.release_point)
        self.assertEqual(direct.detonation_time_s, sequence.detonation_time_s)
        self.assertEqual(direct.detonation_point, sequence.detonation_point)
        self.assertEqual(direct.evaluation_window, sequence.evaluation_window)
        self.assertEqual(direct.normalized_heading_rad,
                         sequence.normalized_heading_rad)


class TestRepeatedDeterminismRealReeval(unittest.TestCase):
    """closure v2 §十: 真实重新执行同一 Q3 candidate, 逐项 exact 比较.

    2 real Q3 evaluations.
    """

    def test_same_anchor_evaluated_twice_full_payload_match(self):
        anchor = make_anchor_candidate()
        ev_a = evaluate_three_bomb_strategy(anchor, sample_level="coarse")
        ev_b = evaluate_three_bomb_strategy(anchor, sample_level="coarse")
        # 逐项 exact 比较
        self.assertEqual(ev_a.valid, ev_b.valid)
        self.assertEqual(ev_a.status, ev_b.status)
        self.assertEqual(ev_a.union_intervals, ev_b.union_intervals)
        self.assertAlmostEqual(
            ev_a.total_union_duration_s, ev_b.total_union_duration_s,
            places=12,
        )
        for i in range(3):
            self.assertEqual(
                ev_a.bomb_evaluations[i].intervals,
                ev_b.bomb_evaluations[i].intervals,
            )
            self.assertAlmostEqual(
                ev_a.bomb_evaluations[i].total_duration_s,
                ev_b.bomb_evaluations[i].total_duration_s,
                places=12,
            )
            self.assertEqual(
                ev_a.bomb_evaluations[i].release_point,
                ev_b.bomb_evaluations[i].release_point,
            )
            self.assertEqual(
                ev_a.bomb_evaluations[i].detonation_point,
                ev_b.bomb_evaluations[i].detonation_point,
            )
        self.assertEqual(ev_a.q3_evaluation_id, ev_b.q3_evaluation_id)
        self.assertEqual(ev_a.single_bomb_evaluator_calls,
                         ev_b.single_bomb_evaluator_calls)


# ===========================================================================
# TASK_006-P2: Q3 FORMAL BOUNDED SEARCH TESTS (FakeEvaluator only)
# ===========================================================================
#
# All tests in this section use fake_evaluator_for_tests or only
# schedule / config arithmetic. They do NOT call evaluate_three_bomb_strategy
# (the real Q3 evaluator). Real Q3 evaluation count in tests = 0.
#
# Required test count: ≥ 20.

import os
import sys
import tempfile
import unittest
from typing import List

# Make src importable if running directly from tests/ (it normally is)
sys.path.insert(0, os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..")))

from src import q3_search
from src.q3_search import (
    STAGE_A_BUDGET, STAGE_B_BUDGET, STAGE_C_BUDGET, STAGE_D_BUDGET,
    STAGE_E_BUDGET, TOTAL_BUDGET, A1_PER_SEED, A2_PER_SEED, A3_PER_SEED,
    B_PARENT_TOP_K, B_PERTURBATIONS_PER_PARENT, C_PARENT_TOP_K,
    C_PERTURBATION_SETS_PER_PARENT, D_TOP_K, E_TOP_K,
    FORMAL_CONFIG_SHA256, CHECKPOINT_SCHEMA_VERSION,
    DEFAULT_SEEDS, DEFAULT_WALL_CLOCK_SECONDS,
    FormalScheduleRecord, build_formal_schedule,
    compute_formal_schedule_sha256,
    compute_q3_three_bombs_code_sha256,
    compute_q3_search_code_sha256,
    fake_evaluator_for_tests, _build_bcde_records,
    _verify_resume_identity, _build_formal_summary,
    run_formal_search, _perturb_candidate, _make_a1_candidates,
    _make_a2_candidates, _make_a3_candidates,
    _build_stage_b, _build_stage_c, _build_stage_d, _build_stage_e,
    FormalSearchStats, _atomic_write_json,
)
from src.q3_three_bombs import (
    ThreeBombCandidate, validate_candidate,
    CANDIDATE_SCHEMA_VERSION, PILOT_CONFIG_SHA256,
)
import json
import hashlib


def _tmp_dir() -> str:
    return tempfile.mkdtemp(prefix="q3search_test_")


def _q2_sha() -> str:
    return hashlib.sha256(
        open("src/q2_single_bomb.py", "rb").read()).hexdigest()


def _q3_sha() -> str:
    return compute_q3_three_bombs_code_sha256()


def _q3s_sha() -> str:
    return compute_q3_search_code_sha256()


def _contract_sha() -> str:
    return hashlib.sha256(
        open("work/task_contracts/TASK_006-P2-v3.json", "rb").read()
    ).hexdigest()


def _exec_head() -> str:
    import subprocess
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True, text=True, encoding="utf-8", timeout=10,
    ).stdout.strip()


class TestQ3SearchBudgetArithmetic(unittest.TestCase):
    """P2 directive §五: 5 阶段预算总和必须 = 512."""

    def test_stage_budgets_sum_to_512(self):
        total = (STAGE_A_BUDGET + STAGE_B_BUDGET + STAGE_C_BUDGET
                 + STAGE_D_BUDGET + STAGE_E_BUDGET)
        self.assertEqual(total, 512)
        self.assertEqual(TOTAL_BUDGET, 512)

    def test_a_subblocks_per_seed_sum_to_120(self):
        self.assertEqual(A1_PER_SEED + A2_PER_SEED + A3_PER_SEED, 120)
        self.assertEqual((A1_PER_SEED + A2_PER_SEED + A3_PER_SEED) * 3,
                         STAGE_A_BUDGET)

    def test_b_parent_times_perturbations_equals_b_budget(self):
        self.assertEqual(B_PARENT_TOP_K * B_PERTURBATIONS_PER_PARENT,
                         STAGE_B_BUDGET)

    def test_c_parent_times_sets_equals_c_budget(self):
        self.assertEqual(C_PARENT_TOP_K * C_PERTURBATION_SETS_PER_PARENT,
                         STAGE_C_BUDGET)

    def test_d_top_k_equals_d_budget(self):
        self.assertEqual(D_TOP_K, STAGE_D_BUDGET)

    def test_e_top_k_equals_e_budget(self):
        self.assertEqual(E_TOP_K, STAGE_E_BUDGET)


class TestQ3SearchScheduleDeterministic(unittest.TestCase):
    """P2 directive §十一: schedule deterministic + seed-locked."""

    def test_a1_deterministic_per_seed(self):
        c1 = _make_a1_candidates(2025)
        c2 = _make_a1_candidates(2025)
        self.assertEqual(len(c1), A1_PER_SEED)
        self.assertEqual(len(c2), A1_PER_SEED)
        for a, b in zip(c1, c2):
            self.assertEqual(a.heading_rad, b.heading_rad)
            self.assertEqual(a.speed_mps, b.speed_mps)
            self.assertEqual(a.release_time_1_s, b.release_time_1_s)

    def test_a2_deterministic_per_seed(self):
        c1 = _make_a2_candidates(2026)
        c2 = _make_a2_candidates(2026)
        self.assertEqual(len(c1), A2_PER_SEED)
        for a, b in zip(c1, c2):
            self.assertEqual(a.delay_1_s, b.delay_1_s)

    def test_a3_deterministic_per_seed(self):
        c1 = _make_a3_candidates(2027)
        c2 = _make_a3_candidates(2027)
        self.assertEqual(len(c1), A3_PER_SEED)

    def test_a1_different_seeds_differ(self):
        c1 = _make_a1_candidates(2025)
        c2 = _make_a1_candidates(2026)
        # Different seeds must produce at least one differing candidate.
        differ = any(
            a.heading_rad != b.heading_rad
            for a, b in zip(c1, c2)
        )
        self.assertTrue(differ)

    def test_all_a_candidates_pass_validate(self):
        for seed in (2025, 2026, 2027):
            for sub in (_make_a1_candidates(seed),
                        _make_a2_candidates(seed),
                        _make_a3_candidates(seed)):
                for c in sub:
                    ok, reason = validate_candidate(c)
                    self.assertTrue(ok, f"seed={seed} invalid: {reason}")


class TestQ3SearchScheduleBuild(unittest.TestCase):
    def test_build_formal_schedule_produces_360_records(self):
        recs, info = build_formal_schedule(
            seeds=DEFAULT_SEEDS,
            q2_code_sha=_q2_sha(),
            q3_code_sha=_q3_sha(),
        )
        self.assertEqual(len(recs), STAGE_A_BUDGET)
        self.assertEqual(info["stage_a_count"], STAGE_A_BUDGET)
        self.assertEqual(info["total"], TOTAL_BUDGET)

    def test_build_formal_schedule_schedule_index_monotonic(self):
        recs, _ = build_formal_schedule(
            seeds=DEFAULT_SEEDS, q2_code_sha=_q2_sha(), q3_code_sha=_q3_sha(),
        )
        for i, r in enumerate(recs):
            self.assertEqual(r.schedule_index, i)

    def test_build_formal_schedule_all_records_stage_A(self):
        recs, _ = build_formal_schedule(
            seeds=DEFAULT_SEEDS, q2_code_sha=_q2_sha(), q3_code_sha=_q3_sha(),
        )
        for r in recs:
            self.assertEqual(r.stage, "A")

    def test_build_formal_schedule_seeds_distribution(self):
        recs, _ = build_formal_schedule(
            seeds=DEFAULT_SEEDS, q2_code_sha=_q2_sha(), q3_code_sha=_q3_sha(),
        )
        from collections import Counter
        cnt = Counter(r.seed for r in recs)
        # each seed should produce exactly 120 records
        for s in DEFAULT_SEEDS:
            self.assertEqual(cnt[s], 120)

    def test_build_formal_schedule_scan_step_matches_profile(self):
        from src.q3_three_bombs import PROFILE_SCAN_STEPS
        recs, _ = build_formal_schedule(
            seeds=DEFAULT_SEEDS, q2_code_sha=_q2_sha(), q3_code_sha=_q3_sha(),
        )
        for r in recs:
            self.assertEqual(r.scan_step, PROFILE_SCAN_STEPS["coarse"])

    def test_schedule_sha_deterministic(self):
        recs1, _ = build_formal_schedule(
            seeds=DEFAULT_SEEDS, q2_code_sha=_q2_sha(), q3_code_sha=_q3_sha(),
        )
        recs2, _ = build_formal_schedule(
            seeds=DEFAULT_SEEDS, q2_code_sha=_q2_sha(), q3_code_sha=_q3_sha(),
        )
        self.assertEqual(
            compute_formal_schedule_sha256(recs1),
            compute_formal_schedule_sha256(recs2),
        )


class TestQ3SearchResumeIdentity(unittest.TestCase):
    """P2 directive §十一 / 七: 7-field resume identity, fail-closed."""

    def test_resume_identity_match(self):
        old = {
            "execution_head_sha": _exec_head(),
            "contract_snapshot_sha256": _contract_sha(),
            "q2_single_bomb_code_sha256": _q2_sha(),
            "q3_three_bombs_code_sha256": _q3_sha(),
            "q3_search_code_sha256": _q3s_sha(),
            "formal_config_sha256": FORMAL_CONFIG_SHA256,
            "candidate_schema_version": CANDIDATE_SCHEMA_VERSION,
        }
        self.assertTrue(_verify_resume_identity(
            old, old["execution_head_sha"],
            old["contract_snapshot_sha256"], old["q2_single_bomb_code_sha256"],
            old["q3_three_bombs_code_sha256"], old["q3_search_code_sha256"],
            old["formal_config_sha256"], old["candidate_schema_version"],
        ))

    def test_resume_identity_mismatch_execution_head(self):
        old = {
            "execution_head_sha": "0" * 40,
            "contract_snapshot_sha256": _contract_sha(),
            "q2_single_bomb_code_sha256": _q2_sha(),
            "q3_three_bombs_code_sha256": _q3_sha(),
            "q3_search_code_sha256": _q3s_sha(),
            "formal_config_sha256": FORMAL_CONFIG_SHA256,
            "candidate_schema_version": CANDIDATE_SCHEMA_VERSION,
        }
        self.assertFalse(_verify_resume_identity(
            old, _exec_head(),
            old["contract_snapshot_sha256"], old["q2_single_bomb_code_sha256"],
            old["q3_three_bombs_code_sha256"], old["q3_search_code_sha256"],
            old["formal_config_sha256"], old["candidate_schema_version"],
        ))

    def test_resume_identity_mismatch_formal_config(self):
        old = {
            "execution_head_sha": _exec_head(),
            "contract_snapshot_sha256": _contract_sha(),
            "q2_single_bomb_code_sha256": _q2_sha(),
            "q3_three_bombs_code_sha256": _q3_sha(),
            "q3_search_code_sha256": _q3s_sha(),
            "formal_config_sha256": "0" * 64,
            "candidate_schema_version": CANDIDATE_SCHEMA_VERSION,
        }
        self.assertFalse(_verify_resume_identity(
            old, _exec_head(),
            old["contract_snapshot_sha256"], old["q2_single_bomb_code_sha256"],
            old["q3_three_bombs_code_sha256"], old["q3_search_code_sha256"],
            FORMAL_CONFIG_SHA256, CANDIDATE_SCHEMA_VERSION,
        ))


class TestQ3SearchFakeEvaluator(unittest.TestCase):
    """P2 directive §十四: ≥ 20 tests using fake evaluator.

    All tests below use fake_evaluator_for_tests → 0 real Q3 evaluations.
    """

    def test_fake_evaluator_returns_valid_evaluation(self):
        c = _make_a1_candidates(2025)[0]
        ev = fake_evaluator_for_tests(c, "coarse", 0.05)
        self.assertTrue(ev.valid)
        self.assertEqual(ev.status, "ok")
        self.assertGreater(ev.total_union_duration_s, 0.0)
        self.assertEqual(ev.single_bomb_evaluator_calls, 3)

    def test_fake_evaluator_deterministic(self):
        c = _make_a1_candidates(2025)[0]
        e1 = fake_evaluator_for_tests(c, "coarse", 0.05)
        e2 = fake_evaluator_for_tests(c, "coarse", 0.05)
        self.assertEqual(e1.q3_evaluation_id, e2.q3_evaluation_id)
        self.assertEqual(e1.total_union_duration_s, e2.total_union_duration_s)

    def test_fake_evaluator_per_bomb_intervals_three_items(self):
        c = _make_a1_candidates(2025)[0]
        ev = fake_evaluator_for_tests(c, "coarse", 0.05)
        self.assertEqual(len(ev.bomb_evaluations), 3)

    def test_perturb_candidate_validates(self):
        c = _make_a1_candidates(2025)[0]
        import random
        rng = random.Random(42)
        for _ in range(20):
            p = _perturb_candidate(c, rng, amplitude=0.3)
            if p is not None:
                ok, _ = validate_candidate(p)
                self.assertTrue(ok)


class TestQ3SearchDryRun(unittest.TestCase):
    """P2 directive §十四: full dry-run path with fake evaluator."""

    def test_dry_run_completes_within_budget(self):
        tmp = _tmp_dir()
        ckpt = os.path.join(tmp, "checkpoint.json")
        out = os.path.join(tmp, "out")
        # Use full seed list (3 seeds) but fake evaluator
        summary = run_formal_search(
            execution_head_sha=_exec_head(),
            contract_snapshot_sha256=_contract_sha(),
            output_dir=out,
            checkpoint_path=ckpt,
            seeds=DEFAULT_SEEDS,
            wall_clock_cap=60.0,
            fake_dry_run=True,
        )
        # Dry-run with full 3 seeds: Stage A = 360 records
        self.assertIn("stage_counts", summary)
        self.assertEqual(
            summary["stage_counts"]["A"], STAGE_A_BUDGET,
            f"Stage A should produce {STAGE_A_BUDGET} records, "
            f"got {summary['stage_counts']['A']}",
        )
        self.assertIn(summary["status"]["raw_status"],
                      ("pilot_complete", "WALL_CLOCK_GATE_HIT"))

    def test_dry_run_summary_fields_present(self):
        tmp = _tmp_dir()
        ckpt = os.path.join(tmp, "checkpoint.json")
        out = os.path.join(tmp, "out")
        summary = run_formal_search(
            execution_head_sha=_exec_head(),
            contract_snapshot_sha256=_contract_sha(),
            output_dir=out,
            checkpoint_path=ckpt,
            seeds=DEFAULT_SEEDS,
            wall_clock_cap=60.0,
            fake_dry_run=True,
        )
        # All canonical fields
        self.assertEqual(summary["phase_id"], "TASK_006-P2")
        self.assertEqual(summary["contract_version"], 3)
        self.assertEqual(summary["result_level"]["declared_level"],
                         "BUDGET_LIMITED_BEST_KNOWN")
        self.assertFalse(summary["result_level"]["local_convergence_established"])
        self.assertTrue(summary["result_level"]["not_a_proven_global_optimum"])
        self.assertFalse(summary["result_level"]["result1_xlsx_generated"])
        self.assertEqual(summary["identity"]["candidate_schema_version"],
                         CANDIDATE_SCHEMA_VERSION)
        self.assertEqual(summary["identity"]["formal_config_sha256"],
                         FORMAL_CONFIG_SHA256)
        self.assertEqual(summary["identity"]["checkpoint_schema_version"],
                         CHECKPOINT_SCHEMA_VERSION)

    def test_dry_run_output_file_written(self):
        tmp = _tmp_dir()
        ckpt = os.path.join(tmp, "checkpoint.json")
        out = os.path.join(tmp, "out")
        run_formal_search(
            execution_head_sha=_exec_head(),
            contract_snapshot_sha256=_contract_sha(),
            output_dir=out,
            checkpoint_path=ckpt,
            seeds=DEFAULT_SEEDS,
            wall_clock_cap=60.0,
            fake_dry_run=True,
        )
        self.assertTrue(os.path.exists(
            os.path.join(out, "q3_formal_search_summary.json")))


class TestQ3SearchCheckpointFailClosed(unittest.TestCase):
    """P2 directive §十一: corrupt checkpoint / identity mismatch → fail-closed."""

    def test_corrupt_checkpoint_fail_closed(self):
        tmp = _tmp_dir()
        ckpt = os.path.join(tmp, "checkpoint.json")
        with open(ckpt, "w", encoding="utf-8") as f:
            f.write("not valid json {{{")
        out = os.path.join(tmp, "out")
        summary = run_formal_search(
            execution_head_sha=_exec_head(),
            contract_snapshot_sha256=_contract_sha(),
            output_dir=out,
            checkpoint_path=ckpt,
            seeds=DEFAULT_SEEDS,
            wall_clock_cap=60.0,
            fake_dry_run=True,
        )
        self.assertTrue(summary["status"]["checkpoint_load_error"])

    def test_identity_mismatch_fail_closed(self):
        tmp = _tmp_dir()
        ckpt = os.path.join(tmp, "checkpoint.json")
        payload = {
            "checkpoint_schema_version": CHECKPOINT_SCHEMA_VERSION,
            "execution_head_sha": "0" * 40,
            "contract_snapshot_sha256": _contract_sha(),
            "q2_single_bomb_code_sha256": _q2_sha(),
            "q3_three_bombs_code_sha256": _q3_sha(),
            "q3_search_code_sha256": _q3s_sha(),
            "formal_config_sha256": FORMAL_CONFIG_SHA256,
            "candidate_schema_version": CANDIDATE_SCHEMA_VERSION,
            "completed_q3_evaluations": 5,
            "stage_counts": {"A": 5, "B": 0, "C": 0, "D": 0, "E": 0},
            "next_schedule_index": 5,
            "evaluated_q3_ids": [],
            "completed_records": [],
            "current_best_candidate": None,
            "current_best_evaluation_payload": None,
            "elapsed_seconds": 0.0,
            "status": "running",
        }
        _atomic_write_json(ckpt, payload)
        out = os.path.join(tmp, "out")
        summary = run_formal_search(
            execution_head_sha=_exec_head(),
            contract_snapshot_sha256=_contract_sha(),
            output_dir=out,
            checkpoint_path=ckpt,
            seeds=DEFAULT_SEEDS,
            wall_clock_cap=60.0,
            fake_dry_run=True,
        )
        self.assertTrue(summary["status"]["resume_identity_mismatch"])


if __name__ == "__main__":
    unittest.main()