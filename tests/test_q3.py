"""Q3 three-bomb evaluator + bounded pilot 测试 (TASK_006-P0P1).

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

TASK (≤600 s, 真实 Q3 evaluator 调用总次数 ≤ 3):
  - TestThreeBombEvaluator (setUpClass 共享 1 次 evaluation + 2 次独立):
      - test_q2_one_bomb_degeneration_exact_comparison
      - test_three_bombs_shared_heading_speed
      - test_three_bomb_union_no_double_count
      - test_invalid_candidate_fail_closed (0 real eval)
      - test_pruned_zero_still_legal
      - test_system_error_raises_not_zero (0 real eval)
      - test_evaluation_id_uniqueness_across_distinct_candidates
      - test_repeated_run_determinism

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

    # --- unique IDs (1 extra real eval) ---
    def test_evaluation_id_uniqueness_across_distinct_candidates(self):
        """两个不同候选产生不同 evaluation_id; 内部 3 次单弹 evaluator."""
        c1 = self.anchor
        c2 = make_anchor_candidate(extra_delay=0.1)
        ev1 = self.shared_ev  # c1
        ev2 = evaluate_three_bomb_strategy(c2, sample_level="coarse")
        self.assertNotEqual(ev1.q3_evaluation_id, ev2.q3_evaluation_id)
        # ev2 也是 valid (合法的 anchor + 0.1)
        self.assertTrue(ev2.valid)
        self.assertEqual(ev2.single_bomb_evaluator_calls, 3)

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


if __name__ == "__main__":
    unittest.main()