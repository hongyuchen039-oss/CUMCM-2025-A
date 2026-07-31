"""Q4 三无人机评估器 controlled unit tests (TASK_007-P2A — HARDENING).

TASK_007-P2A scope: controlled tests only. Real Q1/Q2/Q3/Q4 evaluator calls = 0.

所有 single_bomb_evaluator 调用通过 dependency injection 替换为 StubRecorder;
默认生产 evaluator (src.q2_single_bomb.evaluate_single_bomb_strategy) 在本
测试套件中**绝不**被调用.

identity_context 必填 keyword-only; 0 stub calls 前完成严格校验.

只使用 Python 标准库 + unittest.
"""

from __future__ import annotations

import dataclasses
import hashlib
import inspect
import math
import os
import subprocess
import sys
import tempfile
import unittest
from typing import Callable, List, Optional, Tuple

# Allow `python -m unittest tests.test_q4` from repo root.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from src.q4_three_drones import (
    CANDIDATE_SCHEMA_VERSION,
    CYLINDER_SAMPLING_ALGORITHM_ID,
    DRONE_INITIAL_POSITIONS,
    DRONE_ORDER,
    EVALUATION_CALL_CONTRACT_VERSION,
    INTERVAL_EPSILON_S,
    OBJECTIVE_IDENTITY,
    Q4_MODEL_CONTRACT_SHA256,
    Q4_MODEL_CONTRACT_VERSION,
    Q4_VALID_STATUSES,
    RAW_HEADING_POLICY,
    REQUIRED_CODE_IDENTITY_KEYS,
    REQUIRED_CODE_IDENTITY_PATHS,
    GitBlobIdentity,
    GitBlobIdentityError,
    Q2ReturnContractError,
    Q4EvaluationIdentityContext,
    Q4EvaluationSystemError,
    ThreeDroneCandidate,
    ThreeDroneEvaluation,
    build_cylinder_sample_profile_identity_payload,
    build_q4_config_identity_payload,
    build_q4_evaluation_identity_context,
    build_q4_evaluation_identity_payload,
    canonical_json_bytes,
    canonicalize_json_value,
    compute_cylinder_sample_profile_sha256,
    compute_git_blob_identity,
    compute_q4_config_sha256,
    compute_q4_evaluation_id,
    evaluate_three_drone_strategy,
    iter_drone_strategies,
    validate_three_drone_candidate,
)
from src.q2_single_bomb import (
    SingleBombEvaluation,
    SingleBombStrategy,
    evaluate_single_bomb_strategy,
)


# =============================================================================
#  Helpers
# =============================================================================


def _all_zero_64_hex() -> str:
    return "0" * 64


def _fixture_sha(seed: int) -> str:
    """TEST_FIXTURE_ONLY — 64-hex lowercase derived from a seed; never used
    for formal identity evidence. Returns a deterministic 64 hex string."""
    h = hashlib.sha256(f"TEST_FIXTURE_ONLY:seed={seed}".encode("utf-8")).hexdigest()
    return h


def _fixture_40_hex(seed: int) -> str:
    """TEST_FIXTURE_ONLY — 40-hex lowercase derived from a seed (fake HEAD)."""
    return _fixture_sha(seed)[:40]


def _fixture_blob_identity(
    *,
    key: str,
    path: str,
    seed: int,
    execution_head_sha: str,
) -> GitBlobIdentity:
    """TEST_FIXTURE_ONLY — 构造一个严格满足 schema 的 GitBlobIdentity."""
    return GitBlobIdentity(
        path=path,
        execution_head_sha=execution_head_sha,
        git_blob_oid=_fixture_40_hex(seed * 10 + 1),
        blob_size=100 + seed,
        sha256=_fixture_sha(seed * 10 + 2),
    )


def _fixture_code_identity(
    *,
    execution_head_sha: Optional[str] = None,
) -> Dict[str, GitBlobIdentity]:
    """TEST_FIXTURE_ONLY — 严格 5 key GitBlobIdentity dict, 5 个 execution_head_sha
    一致."""
    if execution_head_sha is None:
        execution_head_sha = _fixture_40_hex(999)
    return {
        key: _fixture_blob_identity(
            key=key,
            path=REQUIRED_CODE_IDENTITY_PATHS[key],
            seed=hash(key) & 0xFFFF,
            execution_head_sha=execution_head_sha,
        )
        for key in REQUIRED_CODE_IDENTITY_KEYS
    }


def _fixture_identity_context(
    *,
    sample_level: str = "coarse",
    scan_step: float = 0.05,
    execution_head_sha: Optional[str] = None,
) -> Q4EvaluationIdentityContext:
    """TEST_FIXTURE_ONLY — 构造一个严格 Q4EvaluationIdentityContext."""
    return build_q4_evaluation_identity_context(
        code_identity=_fixture_code_identity(
            execution_head_sha=execution_head_sha,
        ),
        sample_level=sample_level,
        scan_step=scan_step,
    )


def _valid_candidate() -> ThreeDroneCandidate:
    return ThreeDroneCandidate(
        heading_rad_fy1=1.5,
        speed_mps_fy1=120.0,
        release_time_s_fy1=1.0,
        delay_s_fy1=3.6,
        heading_rad_fy2=3.0,
        speed_mps_fy2=100.0,
        release_time_s_fy2=2.0,
        delay_s_fy2=3.6,
        heading_rad_fy3=0.5,
        speed_mps_fy3=110.0,
        release_time_s_fy3=3.0,
        delay_s_fy3=3.6,
    )


def _strategy_for(c: ThreeDroneCandidate, drone_id: str) -> SingleBombStrategy:
    if drone_id == "FY1":
        return SingleBombStrategy(
            c.heading_rad_fy1, c.speed_mps_fy1, c.release_time_s_fy1, c.delay_s_fy1
        )
    if drone_id == "FY2":
        return SingleBombStrategy(
            c.heading_rad_fy2, c.speed_mps_fy2, c.release_time_s_fy2, c.delay_s_fy2
        )
    if drone_id == "FY3":
        return SingleBombStrategy(
            c.heading_rad_fy3, c.speed_mps_fy3, c.release_time_s_fy3, c.delay_s_fy3
        )
    raise ValueError(drone_id)


def _u0_of(drone_id: str) -> Tuple[float, float, float]:
    return DRONE_INITIAL_POSITIONS[drone_id]


def _make_eval(
    *,
    drone_id: str,
    valid: bool = True,
    status: str = "ok",
    intervals: Tuple[Tuple[float, float], ...] = (),
    total_duration_s: float = 0.0,
    normalized_heading_rad: Optional[float] = None,
    reason: str = "stub",
) -> SingleBombEvaluation:
    """Build a SingleBombEvaluation for stub injection."""
    return SingleBombEvaluation(
        strategy=SingleBombStrategy(0.0, 120.0, 1.0, 3.6),
        normalized_heading_rad=normalized_heading_rad
        if normalized_heading_rad is not None
        else 0.0,
        valid=valid,
        status=status,
        reason=reason,
        release_point=None,
        detonation_time_s=None,
        detonation_point=None,
        evaluation_window=None,
        intervals=intervals,
        total_duration_s=total_duration_s,
        sample_level="coarse",
        scan_step_s=0.05,
        elapsed_s=0.0,
    )


class StubRecorder:
    """Records (drone_id, strategy, u0, sample_level, scan_step) for each
    injected call. Returns a predetermined SingleBombEvaluation.

    `fail_on_call` (1-indexed) causes the n-th call to raise the given
    exception (1-indexed; set to 0 to disable).
    """

    def __init__(
        self,
        return_factory: Optional[
            Callable[[str, int], SingleBombEvaluation]
        ] = None,
        fail_on_call: int = 0,
        fail_exception: Optional[BaseException] = None,
    ) -> None:
        self.calls: List[dict] = []
        self._factory = return_factory or (
            lambda didx, idx: _make_eval(drone_id=didx)
        )
        self.fail_on_call = fail_on_call
        self.fail_exception = fail_exception or RuntimeError(
            f"stub forced failure on call"
        )

    def __call__(
        self,
        strategy: SingleBombStrategy,
        *,
        sample_level: str,
        scan_step: float,
        u0,
    ) -> SingleBombEvaluation:
        drone_id = None
        for did in DRONE_ORDER:
            if tuple(u0) == tuple(_u0_of(did)):
                drone_id = did
                break
        if drone_id is None:
            drone_id = f"UNKNOWN(u0={tuple(u0)})"

        idx_1based = len(self.calls) + 1
        self.calls.append(
            {
                "drone_id": drone_id,
                "strategy": strategy,
                "u0": tuple(u0),
                "sample_level": sample_level,
                "scan_step": float(scan_step),
            }
        )
        if self.fail_on_call and idx_1based == self.fail_on_call:
            raise self.fail_exception
        return self._factory(drone_id, idx_1based)


# =============================================================================
#  Candidate contract
# =============================================================================


class TestCandidateContract(unittest.TestCase):
    """ThreeDroneCandidate 12 字段 + 每架独立 + 边界条件."""

    def test_exactly_12_fields(self):
        fields = dataclasses.fields(ThreeDroneCandidate)
        self.assertEqual(len(fields), 12)
        names = [f.name for f in fields]
        expected = [
            "heading_rad_fy1", "speed_mps_fy1",
            "release_time_s_fy1", "delay_s_fy1",
            "heading_rad_fy2", "speed_mps_fy2",
            "release_time_s_fy2", "delay_s_fy2",
            "heading_rad_fy3", "speed_mps_fy3",
            "release_time_s_fy3", "delay_s_fy3",
        ]
        self.assertEqual(names, expected)

    def test_iter_drone_strategies_fixed_order(self):
        c = _valid_candidate()
        out = iter_drone_strategies(c)
        self.assertEqual(len(out), 3)
        self.assertEqual([t[0] for t in out], ["FY1", "FY2", "FY3"])
        for i, (did, u0, s) in enumerate(out):
            self.assertEqual(tuple(u0), tuple(DRONE_INITIAL_POSITIONS[did]))
            self.assertEqual(s, _strategy_for(c, did))

    def test_three_drones_independent(self):
        c1 = _valid_candidate()
        c2 = dataclasses.replace(c1, heading_rad_fy2=2.0)
        out1 = iter_drone_strategies(c1)
        out2 = iter_drone_strategies(c2)
        self.assertEqual(out1[0][2], out2[0][2])
        self.assertNotEqual(out1[1][2].heading_rad, out2[1][2].heading_rad)
        self.assertEqual(out1[1][2].heading_rad, c1.heading_rad_fy2)
        self.assertEqual(out2[1][2].heading_rad, c2.heading_rad_fy2)
        self.assertEqual(out1[2][2], out2[2][2])

    def test_heading_zero_accepted(self):
        c = dataclasses.replace(_valid_candidate(), heading_rad_fy1=0.0)
        ok, reason = validate_three_drone_candidate(c)
        self.assertTrue(ok, msg=reason)

    def test_heading_nextafter_two_pi_accepted(self):
        two_pi = 2.0 * math.pi
        next_below = math.nextafter(two_pi, 0.0)
        c = dataclasses.replace(_valid_candidate(), heading_rad_fy1=next_below)
        ok, reason = validate_three_drone_candidate(c)
        self.assertTrue(ok, msg=reason)

    def test_heading_neg_eps_rejected(self):
        c = dataclasses.replace(_valid_candidate(), heading_rad_fy1=-1e-12)
        ok, reason = validate_three_drone_candidate(c)
        self.assertFalse(ok)
        self.assertIn("FY1", reason)
        self.assertIn("heading_rad", reason)

    def test_heading_two_pi_rejected(self):
        two_pi = 2.0 * math.pi
        c = dataclasses.replace(_valid_candidate(), heading_rad_fy1=two_pi)
        ok, reason = validate_three_drone_candidate(c)
        self.assertFalse(ok)
        self.assertIn("FY1", reason)
        self.assertIn("heading_rad", reason)

    def test_heading_nan_rejected(self):
        for didx, attr in (
            ("FY1", "heading_rad_fy1"),
            ("FY2", "heading_rad_fy2"),
            ("FY3", "heading_rad_fy3"),
        ):
            with self.subTest(didx=didx):
                c = dataclasses.replace(_valid_candidate(), **{attr: float("nan")})
                ok, reason = validate_three_drone_candidate(c)
                self.assertFalse(ok)
                self.assertIn(didx, reason)
                self.assertIn("not_strict_real_finite_number", reason)

    def test_heading_pos_inf_rejected(self):
        c = dataclasses.replace(_valid_candidate(), heading_rad_fy2=float("inf"))
        ok, reason = validate_three_drone_candidate(c)
        self.assertFalse(ok)
        self.assertIn("FY2", reason)

    def test_heading_neg_inf_rejected(self):
        c = dataclasses.replace(_valid_candidate(), heading_rad_fy3=float("-inf"))
        ok, reason = validate_three_drone_candidate(c)
        self.assertFalse(ok)
        self.assertIn("FY3", reason)

    def test_speed_lower_bound_70_accepted(self):
        c = dataclasses.replace(_valid_candidate(), speed_mps_fy1=70.0)
        ok, reason = validate_three_drone_candidate(c)
        self.assertTrue(ok, msg=reason)

    def test_speed_upper_bound_140_accepted(self):
        c = dataclasses.replace(_valid_candidate(), speed_mps_fy2=140.0)
        ok, reason = validate_three_drone_candidate(c)
        self.assertTrue(ok, msg=reason)

    def test_speed_below_70_rejected(self):
        c = dataclasses.replace(_valid_candidate(), speed_mps_fy1=69.999)
        ok, reason = validate_three_drone_candidate(c)
        self.assertFalse(ok)
        self.assertIn("FY1", reason)
        self.assertIn("speed_mps", reason)

    def test_speed_above_140_rejected(self):
        c = dataclasses.replace(_valid_candidate(), speed_mps_fy3=140.001)
        ok, reason = validate_three_drone_candidate(c)
        self.assertFalse(ok)
        self.assertIn("FY3", reason)
        self.assertIn("speed_mps", reason)

    def test_release_negative_rejected(self):
        c = dataclasses.replace(_valid_candidate(), release_time_s_fy2=-0.001)
        ok, reason = validate_three_drone_candidate(c)
        self.assertFalse(ok)
        self.assertIn("FY2", reason)
        self.assertIn("release_time_s", reason)

    def test_delay_negative_rejected(self):
        c = dataclasses.replace(_valid_candidate(), delay_s_fy3=-1.0)
        ok, reason = validate_three_drone_candidate(c)
        self.assertFalse(ok)
        self.assertIn("FY3", reason)
        self.assertIn("delay_s", reason)

    def test_no_cross_drone_constraint(self):
        c = dataclasses.replace(_valid_candidate(), release_time_s_fy2=0.5)
        ok, reason = validate_three_drone_candidate(c)
        self.assertTrue(ok, msg=reason)

    def test_per_drone_u0_prevalidation_fy1(self):
        c = dataclasses.replace(_valid_candidate(), heading_rad_fy1=-1.0)
        ok, reason = validate_three_drone_candidate(c)
        self.assertFalse(ok)
        self.assertIn("FY1", reason)

    def test_per_drone_u0_prevalidation_fy2(self):
        c = dataclasses.replace(_valid_candidate(), speed_mps_fy2=200.0)
        ok, reason = validate_three_drone_candidate(c)
        self.assertFalse(ok)
        self.assertIn("FY2", reason)

    def test_per_drone_u0_prevalidation_fy3(self):
        c = dataclasses.replace(_valid_candidate(), delay_s_fy3=-0.5)
        ok, reason = validate_three_drone_candidate(c)
        self.assertFalse(ok)
        self.assertIn("FY3", reason)

    # --- B 五/七: strict numeric prevalidation (拒绝字符串 / None / bool) ---

    def test_candidate_numeric_string_invalid(self):
        c = dataclasses.replace(_valid_candidate(), heading_rad_fy1="1.5")
        ok, reason = validate_three_drone_candidate(c)
        self.assertFalse(ok)
        self.assertIn("FY1", reason)

    def test_candidate_none_invalid(self):
        c = dataclasses.replace(_valid_candidate(), speed_mps_fy2=None)
        ok, reason = validate_three_drone_candidate(c)
        self.assertFalse(ok)
        self.assertIn("FY2", reason)

    def test_candidate_bool_invalid(self):
        c = dataclasses.replace(_valid_candidate(), release_time_s_fy3=True)
        ok, reason = validate_three_drone_candidate(c)
        self.assertFalse(ok)
        self.assertIn("FY3", reason)

    def test_scan_step_true_rejected(self):
        recorder = StubRecorder()
        with self.assertRaises(ValueError):
            evaluate_three_drone_strategy(
                _valid_candidate(),
                scan_step=True,
                identity_context=_fixture_identity_context(),
                single_bomb_evaluator=recorder,
            )
        self.assertEqual(recorder.calls, [])


# =============================================================================
#  Prevalidation short-circuit
# =============================================================================


class TestPrevalidationShortCircuit(unittest.TestCase):
    """prevalidation invalid 必须 0 evaluator calls, 0 q4_evaluation_id."""

    def test_illegal_fy1_returns_invalid_short_circuit(self):
        recorder = StubRecorder()
        c = dataclasses.replace(_valid_candidate(), heading_rad_fy1=-1.0)
        result = evaluate_three_drone_strategy(
            c,
            sample_level="coarse",
            scan_step=0.05,
            identity_context=_fixture_identity_context(),
            single_bomb_evaluator=recorder,
        )
        self.assertFalse(result.valid)
        self.assertEqual(result.status, "invalid")
        self.assertEqual(result.drone_evaluations, ())
        self.assertEqual(result.union_intervals, ())
        self.assertEqual(result.total_union_duration_s, 0.0)
        self.assertEqual(result.attempted_single_bomb_calls, 0)
        self.assertEqual(result.completed_single_bomb_calls, 0)
        self.assertEqual(result.q4_evaluation_id, "")
        self.assertEqual(recorder.calls, [])

    def test_illegal_fy2_returns_invalid_short_circuit(self):
        recorder = StubRecorder()
        c = dataclasses.replace(_valid_candidate(), speed_mps_fy2=200.0)
        result = evaluate_three_drone_strategy(
            c, identity_context=_fixture_identity_context(),
            single_bomb_evaluator=recorder,
        )
        self.assertFalse(result.valid)
        self.assertEqual(result.status, "invalid")
        self.assertEqual(result.drone_evaluations, ())
        self.assertEqual(result.attempted_single_bomb_calls, 0)
        self.assertEqual(result.completed_single_bomb_calls, 0)
        self.assertEqual(result.q4_evaluation_id, "")
        self.assertEqual(recorder.calls, [])

    def test_illegal_fy3_returns_invalid_short_circuit(self):
        recorder = StubRecorder()
        c = dataclasses.replace(_valid_candidate(), release_time_s_fy3=-0.5)
        result = evaluate_three_drone_strategy(
            c, identity_context=_fixture_identity_context(),
            single_bomb_evaluator=recorder,
        )
        self.assertFalse(result.valid)
        self.assertEqual(result.status, "invalid")
        self.assertEqual(result.drone_evaluations, ())
        self.assertEqual(result.attempted_single_bomb_calls, 0)
        self.assertEqual(result.completed_single_bomb_calls, 0)
        self.assertEqual(result.q4_evaluation_id, "")
        self.assertEqual(recorder.calls, [])

    def test_q4_evaluation_id_is_empty_string_not_placeholder(self):
        recorder = StubRecorder()
        c = dataclasses.replace(_valid_candidate(), delay_s_fy1=-0.1)
        result = evaluate_three_drone_strategy(
            c, identity_context=_fixture_identity_context(),
            single_bomb_evaluator=recorder,
        )
        self.assertEqual(result.q4_evaluation_id, "")
        self.assertNotEqual(result.q4_evaluation_id, "pending")
        self.assertNotEqual(result.q4_evaluation_id, "placeholder")
        self.assertIsNot(result.q4_evaluation_id, None)


# =============================================================================
#  Normal path: 3 drone calls in FY1->FY2->FY3 order
# =============================================================================


class TestNormalPath(unittest.TestCase):
    """正常路径下 attempted=3, completed=3, call order strict FY1->FY2->FY3."""

    def _stub_normal(self, intervals_fy1, intervals_fy2, intervals_fy3):
        def factory(drone_id, idx):
            if drone_id == "FY1":
                ivs = intervals_fy1
            elif drone_id == "FY2":
                ivs = intervals_fy2
            else:
                ivs = intervals_fy3
            total = sum(b - a for a, b in ivs)
            return _make_eval(
                drone_id=drone_id, valid=True, status="ok",
                intervals=tuple(ivs), total_duration_s=total,
            )

        return StubRecorder(return_factory=factory)

    def test_call_order_strict_fy1_fy2_fy3(self):
        recorder = self._stub_normal((), (), ())
        c = _valid_candidate()
        result = evaluate_three_drone_strategy(
            c, identity_context=_fixture_identity_context(),
            single_bomb_evaluator=recorder,
        )
        order = [call["drone_id"] for call in recorder.calls]
        self.assertEqual(order, ["FY1", "FY2", "FY3"])

    def test_u0_mapping_exact(self):
        recorder = self._stub_normal((), (), ())
        c = _valid_candidate()
        evaluate_three_drone_strategy(
            c, identity_context=_fixture_identity_context(),
            single_bomb_evaluator=recorder,
        )
        for call, did in zip(recorder.calls, DRONE_ORDER):
            self.assertEqual(call["u0"], tuple(DRONE_INITIAL_POSITIONS[did]))
            self.assertEqual(call["u0"], tuple(_u0_of(did)))

    def test_attempted_completed_three_each(self):
        recorder = self._stub_normal((), (), ())
        c = _valid_candidate()
        result = evaluate_three_drone_strategy(
            c, identity_context=_fixture_identity_context(),
            single_bomb_evaluator=recorder,
        )
        self.assertEqual(result.attempted_single_bomb_calls, 3)
        self.assertEqual(result.completed_single_bomb_calls, 3)

    def test_three_real_stub_returns_preserved(self):
        sentinel = object()

        def factory(drone_id, idx):
            return _make_eval(
                drone_id=drone_id, valid=True, status="ok",
                intervals=((idx, idx + 0.5),),
                total_duration_s=0.5,
                reason=f"sentinel-{drone_id}-{idx}",
            )

        recorder = StubRecorder(return_factory=factory)
        c = _valid_candidate()
        result = evaluate_three_drone_strategy(
            c, identity_context=_fixture_identity_context(),
            single_bomb_evaluator=recorder,
        )
        self.assertEqual(len(result.drone_evaluations), 3)
        self.assertEqual(result.drone_evaluations[0].reason, "sentinel-FY1-1")
        self.assertEqual(result.drone_evaluations[1].reason, "sentinel-FY2-2")
        self.assertEqual(result.drone_evaluations[2].reason, "sentinel-FY3-3")

    def test_overlapping_intervals_no_double_count(self):
        recorder = self._stub_normal(
            [(0.0, 2.0)], [(1.0, 3.0)], [(2.0, 4.0)]
        )
        result = evaluate_three_drone_strategy(
            _valid_candidate(),
            identity_context=_fixture_identity_context(),
            single_bomb_evaluator=recorder,
        )
        self.assertTrue(result.valid)
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.union_intervals, ((0.0, 4.0),))
        self.assertAlmostEqual(result.total_union_duration_s, 4.0, places=12)

    def test_disjoint_intervals_summed(self):
        recorder = self._stub_normal(
            [(0.0, 1.0)], [(2.0, 3.0)], [(5.0, 7.0)]
        )
        result = evaluate_three_drone_strategy(
            _valid_candidate(),
            identity_context=_fixture_identity_context(),
            single_bomb_evaluator=recorder,
        )
        self.assertTrue(result.valid)
        self.assertEqual(result.status, "ok")
        self.assertEqual(
            sorted(result.union_intervals),
            sorted([(0.0, 1.0), (2.0, 3.0), (5.0, 7.0)]),
        )
        self.assertAlmostEqual(result.total_union_duration_s, 4.0, places=12)

    def test_nested_and_touching_correct(self):
        recorder = self._stub_normal(
            [(0.0, 10.0)],
            [(2.0, 4.0)],
            [(9.0 - INTERVAL_EPSILON_S / 2, 11.0)],
        )
        result = evaluate_three_drone_strategy(
            _valid_candidate(),
            identity_context=_fixture_identity_context(),
            single_bomb_evaluator=recorder,
        )
        self.assertTrue(result.valid)
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.union_intervals, ((0.0, 11.0),))
        self.assertAlmostEqual(result.total_union_duration_s, 11.0, places=12)

    def test_all_empty_zero_union_status(self):
        recorder = self._stub_normal((), (), ())
        result = evaluate_three_drone_strategy(
            _valid_candidate(),
            identity_context=_fixture_identity_context(),
            single_bomb_evaluator=recorder,
        )
        self.assertTrue(result.valid)
        self.assertEqual(result.status, "zero_union")
        self.assertEqual(result.total_union_duration_s, 0.0)
        self.assertEqual(result.union_intervals, ())

    def test_non_empty_ok_status(self):
        recorder = self._stub_normal(((1.0, 2.0),), (), ())
        result = evaluate_three_drone_strategy(
            _valid_candidate(),
            identity_context=_fixture_identity_context(),
            single_bomb_evaluator=recorder,
        )
        self.assertTrue(result.valid)
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.union_intervals, ((1.0, 2.0),))
        self.assertAlmostEqual(result.total_union_duration_s, 1.0, places=12)

    def test_real_q2_evaluator_never_called_default_path(self):
        recorder = self._stub_normal((), (), ())
        c = _valid_candidate()
        evaluate_three_drone_strategy(
            c, identity_context=_fixture_identity_context(),
            single_bomb_evaluator=recorder,
        )
        self.assertEqual(len(recorder.calls), 3)

    def test_sample_level_invalid_raises_before_prevalidation(self):
        recorder = StubRecorder()
        with self.assertRaises(ValueError):
            evaluate_three_drone_strategy(
                _valid_candidate(),
                sample_level="nonexistent",
                identity_context=_fixture_identity_context(),
                single_bomb_evaluator=recorder,
            )
        self.assertEqual(recorder.calls, [])

    def test_scan_step_zero_raises_before_prevalidation(self):
        recorder = StubRecorder()
        with self.assertRaises(ValueError):
            evaluate_three_drone_strategy(
                _valid_candidate(),
                scan_step=0.0,
                identity_context=_fixture_identity_context(),
                single_bomb_evaluator=recorder,
            )
        self.assertEqual(recorder.calls, [])


# =============================================================================
#  Q2 status aggregation
# =============================================================================


class TestQ2StatusMapping(unittest.TestCase):
    """pruned_zero / zero_window 合法; invalid 传播; status set 严格."""

    def _stub_with_statuses(self, status_fy1, status_fy2, status_fy3):
        statuses = {"FY1": status_fy1, "FY2": status_fy2, "FY3": status_fy3}

        def factory(drone_id, idx):
            st = statuses[drone_id]
            valid = st != "invalid"
            ivs = ((1.0, 2.0),) if st == "ok" else ()
            total = 1.0 if st == "ok" else 0.0
            return _make_eval(
                drone_id=drone_id, valid=valid, status=st,
                intervals=ivs, total_duration_s=total,
                reason=f"{drone_id}:{st}",
            )

        return StubRecorder(return_factory=factory)

    def test_pruned_zero_does_not_cause_q4_invalid(self):
        recorder = self._stub_with_statuses("pruned_zero", "pruned_zero", "pruned_zero")
        result = evaluate_three_drone_strategy(
            _valid_candidate(),
            identity_context=_fixture_identity_context(),
            single_bomb_evaluator=recorder,
        )
        self.assertTrue(result.valid)
        self.assertEqual(result.status, "zero_union")
        self.assertEqual(result.union_intervals, ())
        self.assertEqual(result.total_union_duration_s, 0.0)
        self.assertEqual(result.attempted_single_bomb_calls, 3)
        self.assertEqual(result.completed_single_bomb_calls, 3)

    def test_zero_window_does_not_cause_q4_invalid(self):
        recorder = self._stub_with_statuses("zero_window", "zero_window", "zero_window")
        result = evaluate_three_drone_strategy(
            _valid_candidate(),
            identity_context=_fixture_identity_context(),
            single_bomb_evaluator=recorder,
        )
        self.assertTrue(result.valid)
        self.assertEqual(result.status, "zero_union")

    def test_pruned_zero_plus_zero_window_plus_ok_legal_union(self):
        recorder = self._stub_with_statuses("pruned_zero", "zero_window", "ok")
        result = evaluate_three_drone_strategy(
            _valid_candidate(),
            identity_context=_fixture_identity_context(),
            single_bomb_evaluator=recorder,
        )
        self.assertTrue(result.valid)
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.union_intervals, ((1.0, 2.0),))
        self.assertAlmostEqual(result.total_union_duration_s, 1.0, places=12)

    def test_one_q2_invalid_propagates_q4_invalid_but_keeps_three_returns(self):
        recorder = self._stub_with_statuses("ok", "invalid", "ok")
        result = evaluate_three_drone_strategy(
            _valid_candidate(),
            identity_context=_fixture_identity_context(),
            single_bomb_evaluator=recorder,
        )
        self.assertFalse(result.valid)
        self.assertEqual(result.status, "invalid")
        self.assertEqual(len(result.drone_evaluations), 3)
        self.assertEqual(result.attempted_single_bomb_calls, 3)
        self.assertEqual(result.completed_single_bomb_calls, 3)
        self.assertEqual(result.union_intervals, ())
        self.assertEqual(result.total_union_duration_s, 0.0)
        self.assertIn("some_single_bomb_invalid", result.reason)
        self.assertIn("FY2", result.reason)
        # B1: Q2 normal invalid path q4_evaluation_id 仍为 lowercase 64 hex
        self.assertEqual(len(result.q4_evaluation_id), 64)
        self.assertEqual(result.q4_evaluation_id, result.q4_evaluation_id.lower())
        self.assertTrue(
            all(c in "0123456789abcdef" for c in result.q4_evaluation_id)
        )

    def test_q4_status_set_is_invalid_zero_union_ok_only(self):
        recorder = self._stub_with_statuses("pruned_zero", "ok", "ok")
        result = evaluate_three_drone_strategy(
            _valid_candidate(),
            identity_context=_fixture_identity_context(),
            single_bomb_evaluator=recorder,
        )
        self.assertIn(result.status, Q4_VALID_STATUSES)
        self.assertNotIn(result.status, {"pruned_zero", "zero_window", "system_error"})


# =============================================================================
#  Exception propagation (B4)
# =============================================================================


class TestExceptionPropagation(unittest.TestCase):
    """异常时 raise Q4EvaluationSystemError, 保留 __cause__."""

    def test_exception_at_call_1(self):
        exc = RuntimeError("FY1 fail")
        recorder = StubRecorder(fail_on_call=1, fail_exception=exc)
        with self.assertRaises(Q4EvaluationSystemError) as ctx:
            evaluate_three_drone_strategy(
                _valid_candidate(),
                identity_context=_fixture_identity_context(),
                single_bomb_evaluator=recorder,
            )
        err = ctx.exception
        self.assertEqual(err.failing_drone_id, "FY1")
        self.assertEqual(err.attempted_single_bomb_calls, 1)
        self.assertEqual(err.completed_single_bomb_calls, 0)
        self.assertEqual(err.completed_drone_ids, ())
        self.assertEqual(err.completed_evaluations, ())
        self.assertEqual(err.original_exception_type, "RuntimeError")
        self.assertEqual(err.original_exception_message, "FY1 fail")
        self.assertIs(err.__cause__, exc)
        self.assertEqual(len(recorder.calls), 1)

    def test_exception_at_call_2(self):
        exc = ValueError("FY2 boom")
        recorder = StubRecorder(fail_on_call=2, fail_exception=exc)
        recorder._factory = lambda didx, idx: _make_eval(
            drone_id=didx, valid=True, status="ok",
            intervals=((0.0, 1.0),), total_duration_s=1.0,
        )
        with self.assertRaises(Q4EvaluationSystemError) as ctx:
            evaluate_three_drone_strategy(
                _valid_candidate(),
                identity_context=_fixture_identity_context(),
                single_bomb_evaluator=recorder,
            )
        err = ctx.exception
        self.assertEqual(err.failing_drone_id, "FY2")
        self.assertEqual(err.attempted_single_bomb_calls, 2)
        self.assertEqual(err.completed_single_bomb_calls, 1)
        self.assertEqual(err.completed_drone_ids, ("FY1",))
        self.assertEqual(len(err.completed_evaluations), 1)
        self.assertEqual(err.original_exception_type, "ValueError")
        self.assertIs(err.__cause__, exc)
        self.assertEqual(len(recorder.calls), 2)

    def test_exception_at_call_3(self):
        exc = RuntimeError("FY3 kaboom")
        recorder = StubRecorder(fail_on_call=3, fail_exception=exc)
        recorder._factory = lambda didx, idx: _make_eval(
            drone_id=didx, valid=True, status="ok",
            intervals=((0.0, 1.0),), total_duration_s=1.0,
        )
        with self.assertRaises(Q4EvaluationSystemError) as ctx:
            evaluate_three_drone_strategy(
                _valid_candidate(),
                identity_context=_fixture_identity_context(),
                single_bomb_evaluator=recorder,
            )
        err = ctx.exception
        self.assertEqual(err.failing_drone_id, "FY3")
        self.assertEqual(err.attempted_single_bomb_calls, 3)
        self.assertEqual(err.completed_single_bomb_calls, 2)
        self.assertEqual(err.completed_drone_ids, ("FY1", "FY2"))
        self.assertEqual(len(err.completed_evaluations), 2)
        self.assertIs(err.__cause__, exc)
        self.assertEqual(len(recorder.calls), 3)

    def test_no_three_drone_evaluation_returned_on_exception(self):
        exc = RuntimeError("FY1 fail")
        recorder = StubRecorder(fail_on_call=1, fail_exception=exc)
        try:
            ev = evaluate_three_drone_strategy(
                _valid_candidate(),
                identity_context=_fixture_identity_context(),
                single_bomb_evaluator=recorder,
            )
            self.fail("expected Q4EvaluationSystemError, got evaluation")
        except Q4EvaluationSystemError:
            pass

    def test_q4evaluation_system_error_is_runtime_error_subclass(self):
        err = Q4EvaluationSystemError(
            failing_drone_id="FY1",
            attempted_single_bomb_calls=1,
            completed_single_bomb_calls=0,
            completed_drone_ids=(),
            completed_evaluations=(),
            original_exception_type="RuntimeError",
            original_exception_message="x",
        )
        self.assertIsInstance(err, RuntimeError)
        self.assertEqual(err.failing_drone_id, "FY1")

    # --- B4: KeyboardInterrupt / SystemExit 原样传播 ---

    def test_keyboard_interrupt_propagates_unchanged(self):
        recorder = StubRecorder(fail_on_call=1, fail_exception=KeyboardInterrupt())
        with self.assertRaises(KeyboardInterrupt):
            evaluate_three_drone_strategy(
                _valid_candidate(),
                identity_context=_fixture_identity_context(),
                single_bomb_evaluator=recorder,
            )

    def test_system_exit_propagates_unchanged(self):
        recorder = StubRecorder(fail_on_call=1, fail_exception=SystemExit(1))
        with self.assertRaises(SystemExit):
            evaluate_three_drone_strategy(
                _valid_candidate(),
                identity_context=_fixture_identity_context(),
                single_bomb_evaluator=recorder,
            )

    # --- B4: Q2 return contract 验证 ---

    def test_non_single_bomb_evaluation_return_fail_closed(self):
        def factory(drone_id, idx):
            if idx == 1:
                return "not a SingleBombEvaluation"  # type: ignore[return-value]
            return _make_eval(
                drone_id=drone_id, valid=True, status="ok",
                intervals=((0.0, 1.0),), total_duration_s=1.0,
            )
        recorder = StubRecorder(return_factory=factory)
        with self.assertRaises(Q4EvaluationSystemError) as ctx:
            evaluate_three_drone_strategy(
                _valid_candidate(),
                identity_context=_fixture_identity_context(),
                single_bomb_evaluator=recorder,
            )
        err = ctx.exception
        self.assertEqual(err.failing_drone_id, "FY1")
        self.assertEqual(err.attempted_single_bomb_calls, 1)
        self.assertEqual(err.completed_single_bomb_calls, 0)
        self.assertEqual(err.original_exception_type, "Q2ReturnContractError")
        self.assertIsInstance(err.__cause__, Q2ReturnContractError)

    def test_unknown_q2_status_fail_closed(self):
        def factory(drone_id, idx):
            if idx == 2:
                return _make_eval(
                    drone_id=drone_id, valid=True, status="bogus_status_xyz",
                    intervals=(), total_duration_s=0.0,
                )
            return _make_eval(
                drone_id=drone_id, valid=True, status="ok",
                intervals=((0.0, 1.0),), total_duration_s=1.0,
            )
        recorder = StubRecorder(return_factory=factory)
        with self.assertRaises(Q4EvaluationSystemError) as ctx:
            evaluate_three_drone_strategy(
                _valid_candidate(),
                identity_context=_fixture_identity_context(),
                single_bomb_evaluator=recorder,
            )
        err = ctx.exception
        self.assertEqual(err.failing_drone_id, "FY2")
        self.assertEqual(err.attempted_single_bomb_calls, 2)
        self.assertEqual(err.completed_single_bomb_calls, 1)
        self.assertEqual(err.completed_drone_ids, ("FY1",))
        self.assertEqual(err.original_exception_type, "Q2ReturnContractError")

    def test_valid_true_status_invalid_fail_closed(self):
        def factory(drone_id, idx):
            if idx == 1:
                return _make_eval(
                    drone_id=drone_id, valid=True, status="invalid",
                    intervals=(), total_duration_s=0.0,
                )
            return _make_eval(
                drone_id=drone_id, valid=True, status="ok",
                intervals=((0.0, 1.0),), total_duration_s=1.0,
            )
        recorder = StubRecorder(return_factory=factory)
        with self.assertRaises(Q4EvaluationSystemError) as ctx:
            evaluate_three_drone_strategy(
                _valid_candidate(),
                identity_context=_fixture_identity_context(),
                single_bomb_evaluator=recorder,
            )
        self.assertEqual(ctx.exception.original_exception_type, "Q2ReturnContractError")

    def test_valid_false_status_ok_fail_closed(self):
        def factory(drone_id, idx):
            if idx == 1:
                return _make_eval(
                    drone_id=drone_id, valid=False, status="ok",
                    intervals=((0.0, 1.0),), total_duration_s=1.0,
                )
            return _make_eval(
                drone_id=drone_id, valid=True, status="ok",
                intervals=((0.0, 1.0),), total_duration_s=1.0,
            )
        recorder = StubRecorder(return_factory=factory)
        with self.assertRaises(Q4EvaluationSystemError) as ctx:
            evaluate_three_drone_strategy(
                _valid_candidate(),
                identity_context=_fixture_identity_context(),
                single_bomb_evaluator=recorder,
            )
        self.assertEqual(ctx.exception.original_exception_type, "Q2ReturnContractError")


# =============================================================================
#  Identity / canonical JSON (B1/B2/B3)
# =============================================================================


class TestIdentity(unittest.TestCase):
    """8-category identity payload 严格; canonical JSON 稳定; raw heading."""

    def _identity(self, c=None, identity_context=None):
        c = c or _valid_candidate()
        return compute_q4_evaluation_id(
            c,
            sample_level="coarse",
            scan_step=0.05,
            identity_context=identity_context or _fixture_identity_context(),
        )

    def test_canonical_dict_insertion_order_does_not_affect_id(self):
        c = _valid_candidate()
        ctx = _fixture_identity_context()
        id_a = compute_q4_evaluation_id(
            c, sample_level="coarse", scan_step=0.05, identity_context=ctx,
        )
        # identical ctx -> same id
        id_b = compute_q4_evaluation_id(
            c, sample_level="coarse", scan_step=0.05, identity_context=ctx,
        )
        self.assertEqual(id_a, id_b)

    def test_tuple_and_list_normalization(self):
        # canonical JSON normalizes tuple -> list; build same content two ways
        # via the canonical builder (which already returns lists), so we
        # verify that two equivalent contexts produce same id.
        c = _valid_candidate()
        ctx1 = _fixture_identity_context()
        ctx2 = _fixture_identity_context()
        id1 = compute_q4_evaluation_id(
            c, sample_level="coarse", scan_step=0.05, identity_context=ctx1,
        )
        id2 = compute_q4_evaluation_id(
            c, sample_level="coarse", scan_step=0.05, identity_context=ctx2,
        )
        self.assertEqual(id1, id2)

    def test_negative_zero_equals_positive_zero_real(self):
        # B 九: 使用真实 -0.0 / 0.0 比较 (release_time_s_fy1)
        c_pos = dataclasses.replace(_valid_candidate(), release_time_s_fy1=0.0)
        c_neg = dataclasses.replace(_valid_candidate(), release_time_s_fy1=-0.0)
        self.assertEqual(c_pos.release_time_s_fy1, 0.0)
        # Verify -0.0 vs 0.0 are both strict real finite numbers
        self.assertEqual(c_neg.release_time_s_fy1, -0.0)
        # Both should pass prevalidation (release >= 0)
        ok_pos, _ = validate_three_drone_candidate(c_pos)
        ok_neg, _ = validate_three_drone_candidate(c_neg)
        self.assertTrue(ok_pos)
        self.assertTrue(ok_neg)
        # Both should produce identical canonical JSON (since -0.0 -> 0.0)
        id_pos = self._identity(c_pos)
        id_neg = self._identity(c_neg)
        self.assertEqual(id_pos, id_neg)

    def test_nan_in_payload_rejected(self):
        with self.assertRaises(ValueError):
            canonicalize_json_value(float("nan"))

    def test_inf_in_payload_rejected(self):
        with self.assertRaises(ValueError):
            canonicalize_json_value(float("inf"))
        with self.assertRaises(ValueError):
            canonicalize_json_value(float("-inf"))

    def test_missing_q4_code_identity_rejected(self):
        # Drop a code_identity entry -> build_q4_evaluation_identity_context fails
        code = _fixture_code_identity()
        del code["q4_evaluator"]
        with self.assertRaises(ValueError):
            build_q4_evaluation_identity_context(
                code_identity=code, sample_level="coarse", scan_step=0.05,
            )

    def test_non_hex_sha_rejected(self):
        c = _valid_candidate()
        code = _fixture_code_identity()
        code["q4_evaluator"] = GitBlobIdentity(
            path=REQUIRED_CODE_IDENTITY_PATHS["q4_evaluator"],
            execution_head_sha=code["q1_baseline"].execution_head_sha,
            git_blob_oid=code["q1_baseline"].git_blob_oid,
            blob_size=code["q1_baseline"].blob_size,
            sha256="z" * 64,
        )
        with self.assertRaises(ValueError):
            build_q4_evaluation_identity_context(
                code_identity=code, sample_level="coarse", scan_step=0.05,
            )

    def test_same_context_same_candidate_same_id(self):
        c = _valid_candidate()
        ctx = _fixture_identity_context()
        a = compute_q4_evaluation_id(
            c, sample_level="coarse", scan_step=0.05, identity_context=ctx,
        )
        b = compute_q4_evaluation_id(
            c, sample_level="coarse", scan_step=0.05, identity_context=ctx,
        )
        self.assertEqual(a, b)

    def test_modify_each_candidate_field_changes_id(self):
        ctx = _fixture_identity_context()
        base = compute_q4_evaluation_id(
            _valid_candidate(),
            sample_level="coarse", scan_step=0.05, identity_context=ctx,
        )
        perturbations = [
            ("heading_rad_fy1", 0.123),
            ("speed_mps_fy1", 121.0),
            ("release_time_s_fy1", 1.234),
            ("delay_s_fy1", 3.7),
            ("heading_rad_fy2", 0.234),
            ("speed_mps_fy2", 101.0),
            ("release_time_s_fy2", 2.234),
            ("delay_s_fy2", 3.7),
            ("heading_rad_fy3", 0.345),
            ("speed_mps_fy3", 111.0),
            ("release_time_s_fy3", 3.234),
            ("delay_s_fy3", 3.7),
        ]
        for field, value in perturbations:
            with self.subTest(field=field):
                c2 = dataclasses.replace(_valid_candidate(), **{field: value})
                other = compute_q4_evaluation_id(
                    c2, sample_level="coarse", scan_step=0.05, identity_context=ctx,
                )
                self.assertNotEqual(base, other)

    def test_fy2_u0_change_changes_id(self):
        c = _valid_candidate()
        ctx = _fixture_identity_context()
        payload_a = build_q4_evaluation_identity_payload(
            c, sample_level="coarse", scan_step=0.05, identity_context=ctx,
        )
        id_a = hashlib.sha256(canonical_json_bytes(payload_a)).hexdigest()
        payload_b = dict(payload_a)
        payload_b["per_drone_context"] = dict(payload_a["per_drone_context"])
        payload_b["per_drone_context"]["fy2_initial_position_m"] = [12000.0, 1401.0, 1400.0]
        id_b = hashlib.sha256(canonical_json_bytes(payload_b)).hexdigest()
        self.assertNotEqual(id_a, id_b)

    def test_sample_level_change_changes_id(self):
        c = _valid_candidate()
        ctx_c = _fixture_identity_context(sample_level="coarse")
        ctx_m = _fixture_identity_context(sample_level="medium")
        a = compute_q4_evaluation_id(
            c, sample_level="coarse", scan_step=0.05, identity_context=ctx_c,
        )
        b = compute_q4_evaluation_id(
            c, sample_level="medium", scan_step=0.05, identity_context=ctx_m,
        )
        self.assertNotEqual(a, b)

    def test_scan_step_change_changes_id(self):
        c = _valid_candidate()
        ctx_a = _fixture_identity_context(scan_step=0.05)
        ctx_b = _fixture_identity_context(scan_step=0.04)
        a = compute_q4_evaluation_id(
            c, sample_level="coarse", scan_step=0.05, identity_context=ctx_a,
        )
        b = compute_q4_evaluation_id(
            c, sample_level="coarse", scan_step=0.04, identity_context=ctx_b,
        )
        self.assertNotEqual(a, b)

    def test_profile_params_change_changes_id(self):
        c = _valid_candidate()
        ctx_a = _fixture_identity_context(sample_level="coarse")
        ctx_m = _fixture_identity_context(sample_level="medium")
        a = compute_q4_evaluation_id(
            c, sample_level="coarse", scan_step=0.05, identity_context=ctx_a,
        )
        b = compute_q4_evaluation_id(
            c, sample_level="medium", scan_step=0.05, identity_context=ctx_m,
        )
        self.assertNotEqual(a, b)

    def test_any_code_blob_sha_change_changes_id(self):
        c = _valid_candidate()
        ctx_a = _fixture_identity_context()
        # Mutate one blob's sha256 (a result-determining field per B2)
        code_b = dict(ctx_a.code_identity)
        for k in code_b:
            code_b[k] = GitBlobIdentity(
                path=code_b[k].path,
                execution_head_sha=code_b[k].execution_head_sha,
                git_blob_oid=code_b[k].git_blob_oid,
                blob_size=code_b[k].blob_size,
                sha256=_fixture_sha(99999),  # different from baseline
            )
            break  # only first
        ctx_b = Q4EvaluationIdentityContext(
            candidate_schema_version=ctx_a.candidate_schema_version,
            code_identity=code_b,
            q4_config_identity_payload=ctx_a.q4_config_identity_payload,
            cylinder_sample_profile_identity_payload=ctx_a.cylinder_sample_profile_identity_payload,
            missile_and_target_context=ctx_a.missile_and_target_context,
            physical_constants=ctx_a.physical_constants,
            contract_version=ctx_a.contract_version,
            contract_sha256=ctx_a.contract_sha256,
        )
        a = compute_q4_evaluation_id(
            c, sample_level="coarse", scan_step=0.05, identity_context=ctx_a,
        )
        b = compute_q4_evaluation_id(
            c, sample_level="coarse", scan_step=0.05, identity_context=ctx_b,
        )
        self.assertNotEqual(a, b)

    def test_config_change_changes_id(self):
        c = _valid_candidate()
        ctx_a = _fixture_identity_context(scan_step=0.05)
        ctx_b = _fixture_identity_context(scan_step=0.06)
        a = compute_q4_evaluation_id(
            c, sample_level="coarse", scan_step=0.05, identity_context=ctx_a,
        )
        b = compute_q4_evaluation_id(
            c, sample_level="coarse", scan_step=0.06, identity_context=ctx_b,
        )
        self.assertNotEqual(a, b)

    def test_physical_constant_change_changes_id(self):
        c = _valid_candidate()
        ctx = _fixture_identity_context()
        payload_a = build_q4_evaluation_identity_payload(
            c, sample_level="coarse", scan_step=0.05, identity_context=ctx,
        )
        id_a = hashlib.sha256(canonical_json_bytes(payload_a)).hexdigest()
        payload_b = dict(payload_a)
        payload_b["physical_constants"] = dict(payload_a["physical_constants"])
        payload_b["physical_constants"]["gravity_mps2"] = 9.81
        id_b = hashlib.sha256(canonical_json_bytes(payload_b)).hexdigest()
        self.assertNotEqual(id_a, id_b)

    def test_contract_hash_change_rejected(self):
        # B3: identity_context.contract_sha256 must be canonical, otherwise
        # builder rejects.
        c = _valid_candidate()
        code = _fixture_code_identity()
        ctx_dict = _fixture_identity_context()
        # Build a context with wrong contract_sha256
        bad = Q4EvaluationIdentityContext(
            candidate_schema_version=CANDIDATE_SCHEMA_VERSION,
            code_identity=code,
            q4_config_identity_payload=ctx_dict.q4_config_identity_payload,
            cylinder_sample_profile_identity_payload=ctx_dict.cylinder_sample_profile_identity_payload,
            missile_and_target_context=ctx_dict.missile_and_target_context,
            physical_constants=ctx_dict.physical_constants,
            contract_version=Q4_MODEL_CONTRACT_VERSION,
            contract_sha256="f" * 64,
        )
        with self.assertRaises(ValueError):
            compute_q4_evaluation_id(
                c, sample_level="coarse", scan_step=0.05, identity_context=bad,
            )

    def test_only_execution_head_change_preserves_id(self):
        # B2: 同 5 个 blob metadata (path/oid/size/sha256) 但 execution_head_sha
        # 单方面改变 -> ID 不变 (provenance only).
        c = _valid_candidate()
        head_a = _fixture_40_hex(100)
        head_b = _fixture_40_hex(200)
        ctx_a = _fixture_identity_context(execution_head_sha=head_a)
        # Build ctx_b by cloning ctx_a but rewriting execution_head_sha on every
        # blob.
        code_b = {}
        for k, v in ctx_a.code_identity.items():
            code_b[k] = GitBlobIdentity(
                path=v.path,
                execution_head_sha=head_b,
                git_blob_oid=v.git_blob_oid,
                blob_size=v.blob_size,
                sha256=v.sha256,
            )
        ctx_b = Q4EvaluationIdentityContext(
            candidate_schema_version=ctx_a.candidate_schema_version,
            code_identity=code_b,
            q4_config_identity_payload=ctx_a.q4_config_identity_payload,
            cylinder_sample_profile_identity_payload=ctx_a.cylinder_sample_profile_identity_payload,
            missile_and_target_context=ctx_a.missile_and_target_context,
            physical_constants=ctx_a.physical_constants,
            contract_version=ctx_a.contract_version,
            contract_sha256=ctx_a.contract_sha256,
        )
        id_a = compute_q4_evaluation_id(
            c, sample_level="coarse", scan_step=0.05, identity_context=ctx_a,
        )
        id_b = compute_q4_evaluation_id(
            c, sample_level="coarse", scan_step=0.05, identity_context=ctx_b,
        )
        self.assertEqual(id_a, id_b)

    def test_raw_heading_used_not_normalized(self):
        c0 = dataclasses.replace(_valid_candidate(), heading_rad_fy1=0.0)
        c2 = dataclasses.replace(
            _valid_candidate(),
            heading_rad_fy1=math.nextafter(2.0 * math.pi, 0.0),
        )
        id0 = self._identity(c0)
        id2 = self._identity(c2)
        self.assertNotEqual(id0, id2)

    def test_q4_evaluation_id_is_64_hex_lower(self):
        id_ = self._identity()
        self.assertEqual(len(id_), 64)
        self.assertEqual(id_, id_.lower())
        self.assertTrue(all(c in "0123456789abcdef" for c in id_))

    # --- B1: ok / zero_union / Q2 normal invalid 路径 ID 都是 64 hex ---

    def test_ok_path_id_is_64_lower_hex(self):
        recorder = StubRecorder(
            return_factory=lambda didx, idx: _make_eval(
                drone_id=didx, valid=True, status="ok",
                intervals=((0.0, 1.0),), total_duration_s=1.0,
            )
        )
        result = evaluate_three_drone_strategy(
            _valid_candidate(),
            identity_context=_fixture_identity_context(),
            single_bomb_evaluator=recorder,
        )
        self.assertEqual(result.status, "ok")
        self.assertEqual(len(result.q4_evaluation_id), 64)
        self.assertEqual(result.q4_evaluation_id, result.q4_evaluation_id.lower())
        self.assertTrue(
            all(c in "0123456789abcdef" for c in result.q4_evaluation_id)
        )

    def test_zero_union_path_id_is_64_lower_hex(self):
        recorder = StubRecorder(
            return_factory=lambda didx, idx: _make_eval(
                drone_id=didx, valid=True, status="pruned_zero",
                intervals=(), total_duration_s=0.0,
            )
        )
        result = evaluate_three_drone_strategy(
            _valid_candidate(),
            identity_context=_fixture_identity_context(),
            single_bomb_evaluator=recorder,
        )
        self.assertEqual(result.status, "zero_union")
        self.assertEqual(len(result.q4_evaluation_id), 64)
        self.assertEqual(result.q4_evaluation_id, result.q4_evaluation_id.lower())
        self.assertTrue(
            all(c in "0123456789abcdef" for c in result.q4_evaluation_id)
        )

    def test_q2_normal_invalid_path_id_is_64_lower_hex(self):
        statuses = {"FY1": "ok", "FY2": "invalid", "FY3": "ok"}

        def factory(drone_id, idx):
            st = statuses[drone_id]
            return _make_eval(
                drone_id=drone_id, valid=(st != "invalid"), status=st,
                intervals=((0.0, 1.0),) if st == "ok" else (),
                total_duration_s=1.0 if st == "ok" else 0.0,
            )
        recorder = StubRecorder(return_factory=factory)
        result = evaluate_three_drone_strategy(
            _valid_candidate(),
            identity_context=_fixture_identity_context(),
            single_bomb_evaluator=recorder,
        )
        self.assertEqual(result.status, "invalid")
        self.assertEqual(len(result.q4_evaluation_id), 64)
        self.assertEqual(result.q4_evaluation_id, result.q4_evaluation_id.lower())
        self.assertTrue(
            all(c in "0123456789abcdef" for c in result.q4_evaluation_id)
        )


# =============================================================================
#  B1 / B2 / B3 严格 identity_context schema 校验
# =============================================================================


class TestIdentityContextHardening(unittest.TestCase):
    """B1: identity_context keyword-only 必填.
    B2: GitBlobIdentity 严格 schema.
    B3: config/profile/missile/physical/contract 一致性.
    """

    def test_identity_context_keyword_only_required(self):
        # missing identity_context → TypeError
        recorder = StubRecorder()
        with self.assertRaises(TypeError):
            evaluate_three_drone_strategy(
                _valid_candidate(),
                single_bomb_evaluator=recorder,
            )

    def test_missing_identity_context_no_stub_calls(self):
        # No recorder object needed; we just expect TypeError before any setup
        try:
            evaluate_three_drone_strategy(
                _valid_candidate(),
            )
            self.fail("expected TypeError")
        except TypeError:
            pass

    def test_invalid_identity_context_zero_stub_calls(self):
        # Build a context with wrong contract_sha256
        ctx_dict = _fixture_identity_context()
        code = _fixture_code_identity()
        bad = Q4EvaluationIdentityContext(
            candidate_schema_version=CANDIDATE_SCHEMA_VERSION,
            code_identity=code,
            q4_config_identity_payload=ctx_dict.q4_config_identity_payload,
            cylinder_sample_profile_identity_payload=ctx_dict.cylinder_sample_profile_identity_payload,
            missile_and_target_context=ctx_dict.missile_and_target_context,
            physical_constants=ctx_dict.physical_constants,
            contract_version=Q4_MODEL_CONTRACT_VERSION,
            contract_sha256="f" * 64,
        )
        recorder = StubRecorder()
        with self.assertRaises(ValueError):
            evaluate_three_drone_strategy(
                _valid_candidate(),
                identity_context=bad,
                single_bomb_evaluator=recorder,
            )
        self.assertEqual(recorder.calls, [])

    # --- B2: GitBlobIdentity 严格 schema ---

    def test_git_blob_identity_missing_key_rejected(self):
        code = _fixture_code_identity()
        del code["q4_evaluator"]
        with self.assertRaises(ValueError):
            build_q4_evaluation_identity_context(
                code_identity=code, sample_level="coarse", scan_step=0.05,
            )

    def test_git_blob_identity_extra_key_rejected(self):
        code = _fixture_code_identity()
        # Add an extra key
        code["extra_key"] = _fixture_blob_identity(
            key="extra_key", path="src/extra.py", seed=999,
            execution_head_sha=code["q1_baseline"].execution_head_sha,
        )
        with self.assertRaises(ValueError):
            build_q4_evaluation_identity_context(
                code_identity=code, sample_level="coarse", scan_step=0.05,
            )

    def test_git_blob_identity_wrong_path_rejected(self):
        code = _fixture_code_identity()
        code["q4_evaluator"] = GitBlobIdentity(
            path="src/wrong_path.py",
            execution_head_sha=code["q4_evaluator"].execution_head_sha,
            git_blob_oid=code["q4_evaluator"].git_blob_oid,
            blob_size=code["q4_evaluator"].blob_size,
            sha256=code["q4_evaluator"].sha256,
        )
        with self.assertRaises(ValueError):
            build_q4_evaluation_identity_context(
                code_identity=code, sample_level="coarse", scan_step=0.05,
            )

    def test_git_blob_identity_wrong_blob_oid_rejected(self):
        code = _fixture_code_identity()
        code["q4_evaluator"] = GitBlobIdentity(
            path=code["q4_evaluator"].path,
            execution_head_sha=code["q4_evaluator"].execution_head_sha,
            git_blob_oid="not-40-hex",
            blob_size=code["q4_evaluator"].blob_size,
            sha256=code["q4_evaluator"].sha256,
        )
        with self.assertRaises(ValueError):
            build_q4_evaluation_identity_context(
                code_identity=code, sample_level="coarse", scan_step=0.05,
            )

    def test_git_blob_identity_wrong_blob_size_rejected(self):
        code = _fixture_code_identity()
        code["q4_evaluator"] = GitBlobIdentity(
            path=code["q4_evaluator"].path,
            execution_head_sha=code["q4_evaluator"].execution_head_sha,
            git_blob_oid=code["q4_evaluator"].git_blob_oid,
            blob_size=-1,  # invalid
            sha256=code["q4_evaluator"].sha256,
        )
        with self.assertRaises(ValueError):
            build_q4_evaluation_identity_context(
                code_identity=code, sample_level="coarse", scan_step=0.05,
            )

    def test_git_blob_identity_inconsistent_execution_head_rejected(self):
        code = _fixture_code_identity()
        # Replace one with a different execution_head_sha
        original = code["q4_evaluator"]
        code["q4_evaluator"] = GitBlobIdentity(
            path=original.path,
            execution_head_sha=_fixture_40_hex(777),  # different
            git_blob_oid=original.git_blob_oid,
            blob_size=original.blob_size,
            sha256=original.sha256,
        )
        with self.assertRaises(ValueError):
            build_q4_evaluation_identity_context(
                code_identity=code, sample_level="coarse", scan_step=0.05,
            )

    def test_modify_path_changes_id(self):
        c = _valid_candidate()
        ctx_a = _fixture_identity_context()
        # Build ctx_b with one path changed
        code_b = {}
        for k, v in ctx_a.code_identity.items():
            new_path = v.path
            if k == "q4_evaluator":
                new_path = "src/wrong_q4_path.py"
            code_b[k] = GitBlobIdentity(
                path=new_path,
                execution_head_sha=v.execution_head_sha,
                git_blob_oid=v.git_blob_oid,
                blob_size=v.blob_size,
                sha256=v.sha256,
            )
        ctx_b = Q4EvaluationIdentityContext(
            candidate_schema_version=ctx_a.candidate_schema_version,
            code_identity=code_b,
            q4_config_identity_payload=ctx_a.q4_config_identity_payload,
            cylinder_sample_profile_identity_payload=ctx_a.cylinder_sample_profile_identity_payload,
            missile_and_target_context=ctx_a.missile_and_target_context,
            physical_constants=ctx_a.physical_constants,
            contract_version=ctx_a.contract_version,
            contract_sha256=ctx_a.contract_sha256,
        )
        with self.assertRaises(ValueError):
            # Wrong path = builder rejects
            build_q4_evaluation_identity_context(
                code_identity=code_b,
                sample_level="coarse",
                scan_step=0.05,
            )

    def test_modify_blob_oid_changes_id(self):
        c = _valid_candidate()
        ctx_a = _fixture_identity_context()
        blob = ctx_a.code_identity["q4_evaluator"]
        code_b = dict(ctx_a.code_identity)
        code_b["q4_evaluator"] = GitBlobIdentity(
            path=blob.path,
            execution_head_sha=blob.execution_head_sha,
            git_blob_oid=_fixture_40_hex(1234),  # different OID
            blob_size=blob.blob_size,
            sha256=blob.sha256,
        )
        ctx_b = Q4EvaluationIdentityContext(
            candidate_schema_version=ctx_a.candidate_schema_version,
            code_identity=code_b,
            q4_config_identity_payload=ctx_a.q4_config_identity_payload,
            cylinder_sample_profile_identity_payload=ctx_a.cylinder_sample_profile_identity_payload,
            missile_and_target_context=ctx_a.missile_and_target_context,
            physical_constants=ctx_a.physical_constants,
            contract_version=ctx_a.contract_version,
            contract_sha256=ctx_a.contract_sha256,
        )
        id_a = compute_q4_evaluation_id(
            c, sample_level="coarse", scan_step=0.05, identity_context=ctx_a,
        )
        id_b = compute_q4_evaluation_id(
            c, sample_level="coarse", scan_step=0.05, identity_context=ctx_b,
        )
        self.assertNotEqual(id_a, id_b)

    def test_modify_blob_size_changes_id(self):
        c = _valid_candidate()
        ctx_a = _fixture_identity_context()
        blob = ctx_a.code_identity["q4_evaluator"]
        code_b = dict(ctx_a.code_identity)
        code_b["q4_evaluator"] = GitBlobIdentity(
            path=blob.path,
            execution_head_sha=blob.execution_head_sha,
            git_blob_oid=blob.git_blob_oid,
            blob_size=blob.blob_size + 1,
            sha256=blob.sha256,
        )
        ctx_b = Q4EvaluationIdentityContext(
            candidate_schema_version=ctx_a.candidate_schema_version,
            code_identity=code_b,
            q4_config_identity_payload=ctx_a.q4_config_identity_payload,
            cylinder_sample_profile_identity_payload=ctx_a.cylinder_sample_profile_identity_payload,
            missile_and_target_context=ctx_a.missile_and_target_context,
            physical_constants=ctx_a.physical_constants,
            contract_version=ctx_a.contract_version,
            contract_sha256=ctx_a.contract_sha256,
        )
        id_a = compute_q4_evaluation_id(
            c, sample_level="coarse", scan_step=0.05, identity_context=ctx_a,
        )
        id_b = compute_q4_evaluation_id(
            c, sample_level="coarse", scan_step=0.05, identity_context=ctx_b,
        )
        self.assertNotEqual(id_a, id_b)

    def test_modify_sha256_changes_id(self):
        c = _valid_candidate()
        ctx_a = _fixture_identity_context()
        blob = ctx_a.code_identity["q4_evaluator"]
        code_b = dict(ctx_a.code_identity)
        code_b["q4_evaluator"] = GitBlobIdentity(
            path=blob.path,
            execution_head_sha=blob.execution_head_sha,
            git_blob_oid=blob.git_blob_oid,
            blob_size=blob.blob_size,
            sha256=_fixture_sha(99999),  # different sha256
        )
        ctx_b = Q4EvaluationIdentityContext(
            candidate_schema_version=ctx_a.candidate_schema_version,
            code_identity=code_b,
            q4_config_identity_payload=ctx_a.q4_config_identity_payload,
            cylinder_sample_profile_identity_payload=ctx_a.cylinder_sample_profile_identity_payload,
            missile_and_target_context=ctx_a.missile_and_target_context,
            physical_constants=ctx_a.physical_constants,
            contract_version=ctx_a.contract_version,
            contract_sha256=ctx_a.contract_sha256,
        )
        id_a = compute_q4_evaluation_id(
            c, sample_level="coarse", scan_step=0.05, identity_context=ctx_a,
        )
        id_b = compute_q4_evaluation_id(
            c, sample_level="coarse", scan_step=0.05, identity_context=ctx_b,
        )
        self.assertNotEqual(id_a, id_b)

    # --- B3: config / profile / context 严格一致性 ---

    def test_config_with_timestamp_rejected(self):
        ctx = _fixture_identity_context()
        bad_cfg = dict(ctx.q4_config_identity_payload)
        bad_cfg["timestamp"] = "2026-08-01T00:00:00Z"
        bad_ctx = Q4EvaluationIdentityContext(
            candidate_schema_version=ctx.candidate_schema_version,
            code_identity=ctx.code_identity,
            q4_config_identity_payload=bad_cfg,
            cylinder_sample_profile_identity_payload=ctx.cylinder_sample_profile_identity_payload,
            missile_and_target_context=ctx.missile_and_target_context,
            physical_constants=ctx.physical_constants,
            contract_version=ctx.contract_version,
            contract_sha256=ctx.contract_sha256,
        )
        recorder = StubRecorder()
        with self.assertRaises(ValueError):
            evaluate_three_drone_strategy(
                _valid_candidate(),
                identity_context=bad_ctx,
                single_bomb_evaluator=recorder,
            )
        self.assertEqual(recorder.calls, [])

    def test_config_missing_field_rejected(self):
        ctx = _fixture_identity_context()
        bad_cfg = dict(ctx.q4_config_identity_payload)
        del bad_cfg["sample_level"]
        bad_ctx = Q4EvaluationIdentityContext(
            candidate_schema_version=ctx.candidate_schema_version,
            code_identity=ctx.code_identity,
            q4_config_identity_payload=bad_cfg,
            cylinder_sample_profile_identity_payload=ctx.cylinder_sample_profile_identity_payload,
            missile_and_target_context=ctx.missile_and_target_context,
            physical_constants=ctx.physical_constants,
            contract_version=ctx.contract_version,
            contract_sha256=ctx.contract_sha256,
        )
        recorder = StubRecorder()
        with self.assertRaises(ValueError):
            evaluate_three_drone_strategy(
                _valid_candidate(),
                identity_context=bad_ctx,
                single_bomb_evaluator=recorder,
            )
        self.assertEqual(recorder.calls, [])

    def test_config_sample_level_mismatch_rejected(self):
        # evaluate with sample_level="coarse" but identity_context was built
        # with sample_level="medium" → mismatch.
        c = _valid_candidate()
        recorder = StubRecorder()
        ctx = _fixture_identity_context(sample_level="medium")
        with self.assertRaises(ValueError):
            evaluate_three_drone_strategy(
                c,
                sample_level="coarse",
                scan_step=0.05,
                identity_context=ctx,
                single_bomb_evaluator=recorder,
            )
        self.assertEqual(recorder.calls, [])

    def test_config_scan_step_mismatch_rejected(self):
        c = _valid_candidate()
        recorder = StubRecorder()
        ctx = _fixture_identity_context(scan_step=0.05)
        with self.assertRaises(ValueError):
            evaluate_three_drone_strategy(
                c,
                sample_level="coarse",
                scan_step=0.07,
                identity_context=ctx,
                single_bomb_evaluator=recorder,
            )
        self.assertEqual(recorder.calls, [])

    def test_profile_payload_mismatch_with_sample_grades_rejected(self):
        ctx = _fixture_identity_context()
        # Build a profile that disagrees with the canonical one
        bad_profile = dict(ctx.cylinder_sample_profile_identity_payload)
        bad_profile["effective_profile_parameters"] = dict(
            bad_profile["effective_profile_parameters"]
        )
        bad_profile["effective_profile_parameters"]["side_theta"] = 999
        bad_ctx = Q4EvaluationIdentityContext(
            candidate_schema_version=ctx.candidate_schema_version,
            code_identity=ctx.code_identity,
            q4_config_identity_payload=ctx.q4_config_identity_payload,
            cylinder_sample_profile_identity_payload=bad_profile,
            missile_and_target_context=ctx.missile_and_target_context,
            physical_constants=ctx.physical_constants,
            contract_version=ctx.contract_version,
            contract_sha256=ctx.contract_sha256,
        )
        recorder = StubRecorder()
        with self.assertRaises(ValueError):
            evaluate_three_drone_strategy(
                _valid_candidate(),
                identity_context=bad_ctx,
                single_bomb_evaluator=recorder,
            )
        self.assertEqual(recorder.calls, [])


# =============================================================================
#  Git blob identity helper
# =============================================================================


class TestGitBlobHelper(unittest.TestCase):
    """git rev-parse + cat-file blob; tempfile-only; fail-closed."""

    def test_temp_git_repo_blob_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["git", "init", "-q"], cwd=tmp, check=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"], cwd=tmp, check=True
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"], cwd=tmp, check=True
            )
            target = os.path.join(tmp, "blob_target.txt")
            with open(target, "wb") as f:
                f.write(b"hello blob identity\n\x00\x01\x02")
            subprocess.run(["git", "add", "blob_target.txt"], cwd=tmp, check=True)
            subprocess.run(
                ["git", "commit", "-q", "-m", "init"], cwd=tmp, check=True
            )
            head_sha_proc = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=tmp,
                check=True, stdout=subprocess.PIPE,
            )
            head_sha = head_sha_proc.stdout.decode("ascii").strip()
            identity = compute_git_blob_identity(tmp, head_sha, "blob_target.txt")
            blob_oid_proc = subprocess.run(
                ["git", "rev-parse", f"{head_sha}:blob_target.txt"],
                cwd=tmp, check=True, stdout=subprocess.PIPE,
            )
            blob_oid = blob_oid_proc.stdout.decode("ascii").strip()
            cat_proc = subprocess.run(
                ["git", "cat-file", "blob", blob_oid],
                cwd=tmp, check=True, stdout=subprocess.PIPE,
            )
            expected_sha = hashlib.sha256(cat_proc.stdout).hexdigest()
            self.assertEqual(identity.sha256, expected_sha)
            self.assertEqual(identity.git_blob_oid, blob_oid)
            self.assertEqual(identity.blob_size, len(cat_proc.stdout))
            self.assertEqual(identity.execution_head_sha, head_sha)
            self.assertEqual(identity.path, "blob_target.txt")

    def test_worktree_modification_does_not_change_blob_sha(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["git", "init", "-q"], cwd=tmp, check=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=tmp, check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"], cwd=tmp, check=True
            )
            target = os.path.join(tmp, "stable.txt")
            with open(target, "wb") as f:
                f.write(b"original content\n")
            subprocess.run(["git", "add", "stable.txt"], cwd=tmp, check=True)
            subprocess.run(
                ["git", "commit", "-q", "-m", "init"], cwd=tmp, check=True
            )
            head_sha_proc = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=tmp,
                check=True, stdout=subprocess.PIPE,
            )
            head_sha = head_sha_proc.stdout.decode("ascii").strip()
            identity_before = compute_git_blob_identity(tmp, head_sha, "stable.txt")
            with open(target, "wb") as f:
                f.write(b"modified content\n")
            identity_after = compute_git_blob_identity(tmp, head_sha, "stable.txt")
            self.assertEqual(identity_before.sha256, identity_after.sha256)
            self.assertEqual(identity_before.git_blob_oid, identity_after.git_blob_oid)

    def test_nonexistent_path_git_blob_identity_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["git", "init", "-q"], cwd=tmp, check=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"], cwd=tmp, check=True
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"], cwd=tmp, check=True
            )
            with open(os.path.join(tmp, "exists.txt"), "wb") as f:
                f.write(b"x")
            subprocess.run(["git", "add", "exists.txt"], cwd=tmp, check=True)
            subprocess.run(
                ["git", "commit", "-q", "-m", "init"], cwd=tmp, check=True
            )
            head_sha_proc = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=tmp,
                check=True, stdout=subprocess.PIPE,
            )
            head_sha = head_sha_proc.stdout.decode("ascii").strip()
            with self.assertRaises(GitBlobIdentityError) as ctx:
                compute_git_blob_identity(tmp, head_sha, "does_not_exist.py")
            err = ctx.exception
            self.assertEqual(err.execution_head_sha, head_sha)
            self.assertEqual(err.path, "does_not_exist.py")
            self.assertIn("original=", str(err))

    def test_invalid_execution_head_sha_raises_value_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                compute_git_blob_identity(tmp, "not-a-valid-sha", "x")

    def test_temp_dir_cleanup_after_with_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["git", "init", "-q"], cwd=tmp, check=True)
            self.assertTrue(os.path.isdir(tmp))
        self.assertFalse(os.path.isdir(tmp))


# =============================================================================
#  Production evaluator default NOT invoked under injection
# =============================================================================


class TestProductionEvaluatorNotInvoked(unittest.TestCase):
    """默认 evaluate_single_bomb_strategy 在测试期间不被任何调用路径触发."""

    def test_default_evaluator_not_invoked_when_recorder_injected(self):
        recorder = StubRecorder(
            return_factory=lambda didx, idx: _make_eval(
                drone_id=didx, valid=True, status="ok",
                intervals=((0.0, 1.0),), total_duration_s=1.0,
            )
        )
        evaluate_three_drone_strategy(
            _valid_candidate(),
            identity_context=_fixture_identity_context(),
            single_bomb_evaluator=recorder,
        )
        self.assertEqual(len(recorder.calls), 3)

    def test_module_attribute_default_is_production(self):
        import src.q4_three_drones as q4
        sig = inspect.signature(q4.evaluate_three_drone_strategy)
        self.assertIs(
            sig.parameters["single_bomb_evaluator"].default,
            evaluate_single_bomb_strategy,
        )

    def test_identity_context_is_keyword_only(self):
        # B1: identity_context must be keyword-only and required
        import src.q4_three_drones as q4
        sig = inspect.signature(q4.evaluate_three_drone_strategy)
        param = sig.parameters["identity_context"]
        self.assertEqual(param.kind, inspect.Parameter.KEYWORD_ONLY)
        self.assertEqual(param.default, inspect.Parameter.empty)


if __name__ == "__main__":
    unittest.main()
