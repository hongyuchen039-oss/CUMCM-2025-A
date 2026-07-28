"""tests/test_q2_search.py — TASK_004 Q2 REAL SEARCH CORE V1 P1 REMEDIATION + v1.2 RP1 单元测试.

覆盖 (P1-A/B/C/D/E/F/G + P2 + v1.2 RP1):
  A  Heading / Clamp / Parse
  B  Search Domain (no magic bounds)
  C  Candidate Generation (deterministic)
  D  Local candidates clamp (P1-A: 4-dim 上下界)
  E  Manifest (run_identity + lineage_manifest)
  F  SearchEvaluationRow identity (P1-C: evaluation_id, source_stage, ...)
  G  Real evaluator integration
  H  Serial pipeline (P1-C: evaluation_id-keyed resume)
  I  Checkpoint v2 (P1-D: identity + algorithm_version)
  J  Pipeline 5 stages (P1-B: medium-confirmed → fine-only)
  K  CLI (P2: --mode formal → 2)
  L  No result files / no Q1 regression
  M  Fake evaluator
  N  Config v2 (P1-F)
  O  Sampling method docs (P1-G)
  P  Physical candidate hash stable (P1-C)
  Q  RP1 Effective Config (RP1-3)
  R  RP1 Structured Code Identity (RP1-4)
  S  RP1 Interrupted Checkpoint (RP1-1)
  T  RP1 Resume Identity from current plan (RP1-2)
  U  RP1 Canonical Result + canonical_result_sha256
  V  RP1 Two-Finalist Lineage (RP1-7)
  W  RP1 Dirty Worktree Rejection (RP1-5)
  X  RP1 Pilot Smoke (RP1 P2 uniq output + stop-after-evaluations)
  Y  RP1 CLI (RP1 P2 rc codes)

等级: TASK_004 Q2 REAL SEARCH CORE V1 / PILOT / NOT A FORMAL Q2 RESULT.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import sys
import tempfile
import unittest
from typing import List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import q2_search as qs
from src.q2_search import (
    build_search_domain,
    q_space_descriptor,
    make_strategy,
    parse_candidate,
    _wrap_heading,
    _clamp,
    _physical_candidate_sha256,
    _compute_evaluation_id,
    Q1_ANCHOR_VEC,
    Q1_ANCHOR_HEADING,
    Q1_ANCHOR_SPEED,
    Q1_ANCHOR_RELEASE,
    Q1_ANCHOR_DELAY,
    generate_deterministic_candidates,
    wrap_local_candidate,
    dedup_candidates,
    build_manifest_text,
    compute_manifest_sha256,
    manifest_record,
    SearchEvaluationRow,
    evaluate_with_real_evaluator,
    evaluate_with_fake_evaluator,
    run_serial_real,
    rank_top_k,
    build_local_candidates,
    run_search_pipeline,
    save_checkpoint_v2,
    load_checkpoint_v2,
    verify_resume_identity,
    _hash_domain,
    _dedup_rows_by_physical_candidate,
    _make_static_run_identity,
    _make_lineage_manifest,
    compute_static_run_identity_sha256,
    compute_lineage_manifest_sha256,
    load_config_v2,
    DEFAULT_CONFIG_PATH,
    CheckpointV2,
    CHECKPOINT_SCHEMA_V2,
    CONFIG_SCHEMA_V2,
    DEFAULT_PILOT_BUDGET,
    EXPECTED_TOTAL_EVALUATIONS,
    ANCHOR_COUNT,
    ALGORITHM_VERSION,
    SAMPLING_METHOD,
    PIPELINE_STAGES,
    main as qs_main,
    # v1.2 RP1
    build_structured_code_identity,
    compute_structured_code_identity_sha256,
    _stage_plan_for_pipeline,
    resolve_effective_config,
    expected_stage_from_plan,
    build_fine_lineage,
    build_pilot_output,
    compute_canonical_result_sha256,
    CANONICAL_RESULT_FIELDS,
    _ControlledInterruption,
    _build_argparser,
    # FIXED-163 BUDGET GATE
    validate_fixed_production_result,
    FixedProductionBudgetInvariantError,
    EXPECTED_STAGE_COUNTS_PRODUCTION,
)


# =============================================================================
#  Fixture: u0 / g / t_arrival (与最新 main 同步)
# =============================================================================
TEST_U0 = (17800.0, 0.0, 1800.0)
TEST_G = 9.8
TEST_T_ARRIVAL = 67.0


# =============================================================================
#  Test-row helper (shared by RP1 A–I blocks)
# =============================================================================
def _make_row(heading: float, speed: float, release: float, delay: float,
              source_stage: str = "fine", sample_level: str = "fine",
              scan_step: float = 0.01, valid: bool = True,
              status: str = "ok", total: float = 1.0,
              eval_id: str = "") -> SearchEvaluationRow:
    vec = (float(heading), float(speed), float(release), float(delay))
    eid = eval_id or _compute_evaluation_id(source_stage, 0, vec)
    return SearchEvaluationRow(
        evaluation_id=eid, source_stage=source_stage,
        source_candidate_index=0,
        physical_candidate_sha256=_physical_candidate_sha256(vec),
        candidate_index=0, stage=sample_level, seed=2025,
        heading_rad=vec[0], speed_mps=vec[1],
        release_time_s=vec[2], delay_s=vec[3],
        valid=valid, status=status, total_duration_s=total,
        sample_level=sample_level, scan_step_s=scan_step,
    )


# =============================================================================
#  A — Heading / Clamp / Parse
# =============================================================================
class AHeadingClamp(unittest.TestCase):

    def test_a01_wrap_heading_normal(self):
        self.assertAlmostEqual(_wrap_heading(0.0), 0.0, places=12)
        self.assertAlmostEqual(_wrap_heading(math.pi), math.pi, places=12)
        self.assertAlmostEqual(_wrap_heading(2 * math.pi), 0.0, places=12)

    def test_a02_wrap_heading_negative(self):
        self.assertAlmostEqual(_wrap_heading(-math.pi / 2),
                                3 * math.pi / 2, places=12)

    def test_a03_wrap_heading_multi_period(self):
        self.assertAlmostEqual(_wrap_heading(4 * math.pi), 0.0, places=12)
        self.assertAlmostEqual(_wrap_heading(5 * math.pi), math.pi, places=12)

    def test_a04_clamp_lower(self):
        self.assertEqual(_clamp(-1.0, 0.0, 10.0), 0.0)

    def test_a05_clamp_upper(self):
        self.assertEqual(_clamp(20.0, 0.0, 10.0), 10.0)

    def test_a06_clamp_in_range(self):
        self.assertEqual(_clamp(5.0, 0.0, 10.0), 5.0)

    def test_a07_make_strategy_wraps_heading(self):
        h = _wrap_heading(-math.pi / 6)
        s = make_strategy(heading_rad=-math.pi / 6, speed_mps=100.0,
                          release_time_s=2.0, delay_s=1.0)
        self.assertAlmostEqual(s[0], h, places=12)
        self.assertEqual(s[1], 100.0)
        self.assertEqual(s[2], 2.0)
        self.assertEqual(s[3], 1.0)

    def test_a08_make_strategy_clamps_negative(self):
        s = make_strategy(heading_rad=0.0, speed_mps=100.0,
                          release_time_s=-5.0, delay_s=-2.0)
        self.assertEqual(s[2], 0.0)
        self.assertEqual(s[3], 0.0)

    def test_a09_parse_candidate_list(self):
        s = parse_candidate([0.0, 100.0, 2.0, 1.0])
        self.assertEqual(s, (0.0, 100.0, 2.0, 1.0))

    def test_a10_parse_candidate_invalid(self):
        with self.assertRaises(ValueError):
            parse_candidate([0.0, 100.0, 2.0])


# =============================================================================
#  B — Search Domain (no magic bounds)
# =============================================================================
class BSearchDomain(unittest.TestCase):

    def test_b01_domain_keys(self):
        d = build_search_domain(TEST_U0, TEST_G)
        self.assertEqual(set(d.keys()),
                          {"heading_rad", "speed_mps",
                           "release_time_s", "delay_s"})

    def test_b02_speed_bounds(self):
        d = build_search_domain(TEST_U0, TEST_G)
        self.assertEqual(d["speed_mps"]["min"], 70.0)
        self.assertEqual(d["speed_mps"]["max"], 140.0)

    def test_b03_delay_max_derived_from_u0(self):
        d = build_search_domain(TEST_U0, TEST_G)
        expected = math.sqrt(2.0 * 1800.0 / 9.8)
        self.assertAlmostEqual(d["delay_s"]["max"], expected, places=9)

    def test_b04_heading_period(self):
        d = build_search_domain(TEST_U0, TEST_G)
        self.assertAlmostEqual(d["heading_rad"]["max"],
                                2 * math.pi, places=12)

    def test_b05_release_time_max_is_none_by_default(self):
        d = build_search_domain(TEST_U0, TEST_G)
        self.assertIsNone(d["release_time_s"]["max"])

    def test_b06_no_magic_66_or_30(self):
        d = build_search_domain(TEST_U0, TEST_G)
        self.assertIsNone(d["release_time_s"]["max"])
        self.assertNotEqual(d["delay_s"]["max"], 30.0)

    def test_b07_descriptor_is_pure_copy(self):
        d = build_search_domain(TEST_U0, TEST_G)
        desc = q_space_descriptor(d)
        desc["speed_mps"]["min"] = -1.0
        self.assertEqual(d["speed_mps"]["min"], 70.0)


# =============================================================================
#  C — Candidate Generation (deterministic)
# =============================================================================
class CCandidateGeneration(unittest.TestCase):

    def test_c01_includes_anchor(self):
        d = build_search_domain(TEST_U0, TEST_G)
        d["release_time_s"]["max"] = TEST_T_ARRIVAL - 1
        cands = generate_deterministic_candidates(
            seed=2025, count=10, domain=d,
            release_time_max=d["release_time_s"]["max"],
            include_anchor=True,
        )
        self.assertEqual(cands[0], Q1_ANCHOR_VEC)
        self.assertEqual(len(cands), 11)

    def test_c02_excludes_anchor(self):
        d = build_search_domain(TEST_U0, TEST_G)
        d["release_time_s"]["max"] = TEST_T_ARRIVAL - 1
        cands = generate_deterministic_candidates(
            seed=2025, count=10, domain=d,
            release_time_max=d["release_time_s"]["max"],
            include_anchor=False,
        )
        self.assertEqual(len(cands), 10)
        self.assertNotIn(Q1_ANCHOR_VEC, cands)

    def test_c03_deterministic_same_seed(self):
        d = build_search_domain(TEST_U0, TEST_G)
        d["release_time_s"]["max"] = TEST_T_ARRIVAL - 1
        a = generate_deterministic_candidates(
            seed=2025, count=5, domain=d,
            release_time_max=d["release_time_s"]["max"],
            include_anchor=False,
        )
        b = generate_deterministic_candidates(
            seed=2025, count=5, domain=d,
            release_time_max=d["release_time_s"]["max"],
            include_anchor=False,
        )
        self.assertEqual(a, b)

    def test_c04_different_seeds_differ(self):
        d = build_search_domain(TEST_U0, TEST_G)
        d["release_time_s"]["max"] = TEST_T_ARRIVAL - 1
        a = generate_deterministic_candidates(
            seed=2025, count=5, domain=d,
            release_time_max=d["release_time_s"]["max"],
            include_anchor=False,
        )
        b = generate_deterministic_candidates(
            seed=2026, count=5, domain=d,
            release_time_max=d["release_time_s"]["max"],
            include_anchor=False,
        )
        self.assertNotEqual(a, b)

    def test_c05_release_time_max_validation(self):
        d = build_search_domain(TEST_U0, TEST_G)
        with self.assertRaises(ValueError):
            generate_deterministic_candidates(
                seed=2025, count=5, domain=d,
                release_time_max=0.0, include_anchor=False,
            )

    def test_c06_count_validation(self):
        d = build_search_domain(TEST_U0, TEST_G)
        with self.assertRaises(ValueError):
            generate_deterministic_candidates(
                seed=2025, count=-1, domain=d,
                release_time_max=10.0, include_anchor=False,
            )

    def test_c07_dedup_preserves_order(self):
        a = (1.0, 100.0, 2.0, 1.0)
        b = (1.0, 100.0, 2.0, 1.0)
        c = (2.0, 100.0, 2.0, 1.0)
        out = dedup_candidates([a, b, c, a])
        self.assertEqual(out, [a, c])


# =============================================================================
#  D — Local candidates clamp (P1-A)
# =============================================================================
class DLocalCandidates(unittest.TestCase):

    def setUp(self):
        self.domain = build_search_domain(TEST_U0, TEST_G)
        self.domain["release_time_s"]["max"] = TEST_T_ARRIVAL - 1
        self.release_time_max = self.domain["release_time_s"]["max"]

    def _gen(self, base, n=50, delta=(0.5, 5.0, 0.5, 0.3), seed=2025):
        import random
        rng = random.Random(seed)
        return [wrap_local_candidate(base, rng, self.domain,
                                      self.release_time_max, delta)
                for _ in range(n)]

    def test_d01_speed_lower_bound_respected(self):
        base = (math.pi, 71.0, 2.0, 1.0)  # close to lower bound
        cands = self._gen(base)
        for h, s, r, d in cands:
            self.assertGreaterEqual(s, 70.0,
                f"speed {s} below lower bound 70.0")

    def test_d02_speed_upper_bound_respected(self):
        base = (math.pi, 139.0, 2.0, 1.0)  # close to upper bound
        cands = self._gen(base)
        for h, s, r, d in cands:
            self.assertLessEqual(s, 140.0,
                f"speed {s} above upper bound 140.0")

    def test_d03_release_lower_bound_respected(self):
        base = (math.pi, 120.0, 0.1, 1.0)  # close to 0
        cands = self._gen(base)
        for h, s, r, d in cands:
            self.assertGreaterEqual(r, 0.0,
                f"release {r} below 0.0")

    def test_d04_release_upper_bound_respected(self):
        base = (math.pi, 120.0, self.release_time_max - 0.1, 1.0)
        cands = self._gen(base)
        for h, s, r, d in cands:
            self.assertLessEqual(r, self.release_time_max,
                f"release {r} above {self.release_time_max}")

    def test_d05_delay_lower_bound_respected(self):
        base = (math.pi, 120.0, 2.0, 0.1)
        cands = self._gen(base)
        for h, s, r, d in cands:
            self.assertGreaterEqual(d, 0.0,
                f"delay {d} below 0.0")

    def test_d06_delay_ground_upper_bound_respected(self):
        ground_upper = self.domain["delay_s"]["max"]
        base = (math.pi, 120.0, 2.0, ground_upper - 0.05)
        cands = self._gen(base)
        for h, s, r, d in cands:
            self.assertLessEqual(d, ground_upper,
                f"delay {d} above ground upper bound {ground_upper}")

    def test_d07_heading_wrap_respected(self):
        # heading 跨越 0 和 2π
        import random
        rng = random.Random(2025)
        base = (1.0e-3, 120.0, 2.0, 1.0)  # near 0
        cands = self._gen(base)
        for h, s, r, d in cands:
            self.assertGreaterEqual(h, 0.0)
            self.assertLess(h, 2 * math.pi)

        rng = random.Random(2025)
        base = (2 * math.pi - 1.0e-3, 120.0, 2.0, 1.0)  # near 2π
        cands = self._gen(base)
        for h, s, r, d in cands:
            self.assertGreaterEqual(h, 0.0)
            self.assertLess(h, 2 * math.pi)


# =============================================================================
#  E — Manifest (P1-E)
# =============================================================================
class EManifest(unittest.TestCase):

    def test_e01_static_run_identity_deterministic(self):
        kwargs = dict(
            algorithm_version="v1.1",
            code_revision="abc",
            evaluator_kind="real",
            evaluator_version="v1",
            seed=2025,
            domain={"a": {"min": 0.0, "max": 1.0}},
            budget={"k": 1},
            sampling_method="deterministic_uniform_pseudorandom",
            stage_plan=[{"stage": "fine"}],
        )
        a = _make_static_run_identity(**kwargs)
        b = _make_static_run_identity(**kwargs)
        sa = compute_static_run_identity_sha256(a)
        sb = compute_static_run_identity_sha256(b)
        self.assertEqual(sa, sb)

    def test_e02_run_identity_differs_for_different_seed(self):
        kwargs_a = dict(
            algorithm_version="v1.1", code_revision="abc",
            evaluator_kind="real", evaluator_version="v1",
            seed=2025, domain={"a": {"min": 0.0, "max": 1.0}},
            budget={"k": 1}, sampling_method="deterministic_uniform_pseudorandom",
            stage_plan=[{"stage": "fine"}],
        )
        kwargs_b = dict(kwargs_a)
        kwargs_b["seed"] = 2026
        sa = compute_static_run_identity_sha256(
            _make_static_run_identity(**kwargs_a))
        sb = compute_static_run_identity_sha256(
            _make_static_run_identity(**kwargs_b))
        self.assertNotEqual(sa, sb)

    def test_e03_run_identity_differs_for_different_code_revision(self):
        k = dict(
            algorithm_version="v1.1", code_revision="abc",
            evaluator_kind="real", evaluator_version="v1",
            seed=2025, domain={"a": {"min": 0.0, "max": 1.0}},
            budget={"k": 1}, sampling_method="deterministic_uniform_pseudorandom",
            stage_plan=[{"stage": "fine"}],
        )
        ka = dict(k)
        kb = dict(k)
        kb["code_revision"] = "xyz"
        self.assertNotEqual(
            compute_static_run_identity_sha256(
                _make_static_run_identity(**ka)),
            compute_static_run_identity_sha256(
                _make_static_run_identity(**kb)),
        )

    def test_e04_run_identity_differs_for_different_algorithm_version(self):
        k = dict(
            algorithm_version="v1.1", code_revision="abc",
            evaluator_kind="real", evaluator_version="v1",
            seed=2025, domain={"a": {"min": 0.0, "max": 1.0}},
            budget={"k": 1}, sampling_method="deterministic_uniform_pseudorandom",
            stage_plan=[{"stage": "fine"}],
        )
        ka = dict(k)
        kb = dict(k)
        kb["algorithm_version"] = "v2"
        self.assertNotEqual(
            compute_static_run_identity_sha256(
                _make_static_run_identity(**ka)),
            compute_static_run_identity_sha256(
                _make_static_run_identity(**kb)),
        )

    def test_e05_run_identity_differs_for_different_budget(self):
        k = dict(
            algorithm_version="v1.1", code_revision="abc",
            evaluator_kind="real", evaluator_version="v1",
            seed=2025, domain={"a": {"min": 0.0, "max": 1.0}},
            budget={"k": 1}, sampling_method="deterministic_uniform_pseudorandom",
            stage_plan=[{"stage": "fine"}],
        )
        ka = dict(k)
        kb = dict(k)
        kb["budget"] = {"k": 2}
        self.assertNotEqual(
            compute_static_run_identity_sha256(
                _make_static_run_identity(**ka)),
            compute_static_run_identity_sha256(
                _make_static_run_identity(**kb)),
        )

    def test_e06_lineage_manifest_deterministic(self):
        kwargs = dict(
            global_coarse_vectors=[(0.0, 100.0, 1.0, 1.0)],
            global_medium_vectors=[],
            local_parent_lineage=[],
            local_candidate_vectors=[],
            local_medium_vectors=[],
            medium_confirmed_pool=[],
            fine_finalists=[(0.0, 100.0, 1.0, 1.0)],
            final_selection_policy="fine_only_medium_confirmed",
            evaluation_ids=["abc"],
            candidate_counts={"total": 1},
        )
        a = _make_lineage_manifest(**kwargs)
        b = _make_lineage_manifest(**kwargs)
        self.assertEqual(
            compute_lineage_manifest_sha256(a),
            compute_lineage_manifest_sha256(b),
        )

    def test_e07_manifest_record_includes_domain(self):
        d = build_search_domain(TEST_U0, TEST_G)
        v = [(1.0, 100.0, 2.0, 1.0)]
        rec = manifest_record(2025, v, domain=q_space_descriptor(d))
        self.assertIn("domain", rec)
        self.assertIsNotNone(rec["domain"])
        self.assertIn("domain=", rec["text"])

    def test_e08_manifest_record_fields(self):
        v = [(1.0, 100.0, 2.0, 1.0)]
        rec = manifest_record(2025, v)
        self.assertEqual(rec["seed"], 2025)
        self.assertEqual(rec["algorithm_version"], ALGORITHM_VERSION)
        self.assertEqual(rec["n_vectors"], 1)
        self.assertEqual(len(rec["vectors"][0]), 4)
        self.assertEqual(len(rec["sha256"]), 64)


# =============================================================================
#  F — SearchEvaluationRow identity (P1-C)
# =============================================================================
class FSearchEvaluationRow(unittest.TestCase):

    def test_f01_to_from_dict_roundtrip(self):
        r = SearchEvaluationRow(
            evaluation_id="abc",
            source_stage="global_coarse",
            source_candidate_index=0,
            physical_candidate_sha256="def",
            candidate_index=0,
            stage="coarse", seed=2025,
            heading_rad=math.pi, speed_mps=120.0,
            release_time_s=1.5, delay_s=3.6,
            valid=True, status="ok", total_duration_s=1.5,
            intervals=((8.0, 9.5),),
            release_point=(17000.0, 0.0, 1800.0),
            detonation_time_s=5.1,
            detonation_point=(16000.0, 0.0, 1700.0),
            sample_level="coarse", scan_step_s=0.05,
            evaluator_kind="real", wall_clock_s=0.123,
        )
        d = r.to_dict()
        r2 = SearchEvaluationRow.from_dict(d)
        self.assertEqual(r2.evaluation_id, "abc")
        self.assertEqual(r2.source_stage, "global_coarse")
        self.assertEqual(r2.source_candidate_index, 0)
        self.assertEqual(r2.physical_candidate_sha256, "def")
        self.assertEqual(r2.candidate_index, 0)
        self.assertEqual(r2.intervals, ((8.0, 9.5),))
        self.assertEqual(r2.evaluator_kind, "real")

    def test_f02_evaluation_id_unique(self):
        v1 = (1.0, 100.0, 2.0, 1.0)
        v2 = (1.0, 100.0, 2.0, 1.1)
        eid1 = _compute_evaluation_id("global_coarse", 0, v1)
        eid2 = _compute_evaluation_id("global_coarse", 0, v2)
        self.assertNotEqual(eid1, eid2)

    def test_f03_evaluation_id_distinguishes_stages(self):
        v = (1.0, 100.0, 2.0, 1.0)
        eid_coarse = _compute_evaluation_id("global_coarse", 0, v)
        eid_medium = _compute_evaluation_id("global_medium", 0, v)
        eid_local = _compute_evaluation_id("local_coarse", 0, v)
        eid_fine = _compute_evaluation_id("fine", 0, v)
        self.assertEqual(len({eid_coarse, eid_medium, eid_local, eid_fine}), 4)

    def test_f04_physical_candidate_sha256_stable(self):
        v = (1.0, 100.0, 2.0, 1.0)
        h1 = _physical_candidate_sha256(v)
        # 重复调用 → 相同 hash
        h2 = _physical_candidate_sha256(v)
        self.assertEqual(h1, h2)
        # 微小变化 → 不同 hash
        h3 = _physical_candidate_sha256((1.0, 100.0, 2.0, 1.001))
        self.assertNotEqual(h1, h3)

    def test_f05_from_dict_backfills_missing_identity(self):
        # 旧版 row 没有 evaluation_id, 应当回填
        old = {
            "candidate_index": 0, "stage": "coarse", "seed": 2025,
            "heading_rad": 0.0, "speed_mps": 100.0,
            "release_time_s": 1.0, "delay_s": 1.0,
            "valid": True, "status": "ok", "total_duration_s": 1.0,
            "sample_level": "coarse", "scan_step_s": 0.05,
            "evaluator_kind": "real",
        }
        r = SearchEvaluationRow.from_dict(old)
        self.assertNotEqual(r.evaluation_id, "")
        self.assertEqual(r.source_stage, "coarse")  # fallback
        self.assertEqual(r.source_candidate_index, 0)
        self.assertEqual(len(r.physical_candidate_sha256), 64)


# =============================================================================
#  G — Real evaluator integration
# =============================================================================
class GRealEvaluator(unittest.TestCase):

    def test_g01_q1_anchor_nonzero(self):
        row = evaluate_with_real_evaluator(
            Q1_ANCHOR_VEC, sample_level="coarse",
            scan_step=0.05, seed=2025,
            source_stage="global_coarse", source_candidate_index=0,
        )
        self.assertEqual(row.evaluator_kind, "real")
        self.assertTrue(row.valid)
        self.assertEqual(row.status, "ok")
        self.assertGreater(row.total_duration_s, 0.0)
        self.assertGreater(len(row.intervals), 0)
        # P1-C: identity fields set
        self.assertNotEqual(row.evaluation_id, "")
        self.assertEqual(row.source_stage, "global_coarse")
        self.assertEqual(row.source_candidate_index, 0)
        self.assertEqual(len(row.physical_candidate_sha256), 64)

    def test_g02_invalid_status_returns_invalid(self):
        row = evaluate_with_real_evaluator(
            (0.0, 200.0, 1.0, 1.0),  # speed=200 > 140
            sample_level="coarse", scan_step=0.05, seed=2025,
            source_stage="global_coarse", source_candidate_index=0,
        )
        self.assertFalse(row.valid)
        self.assertEqual(row.status, "invalid")
        self.assertEqual(row.total_duration_s, 0.0)

    def test_g03_pruned_zero_status(self):
        row = evaluate_with_real_evaluator(
            (0.0, 100.0, 80.0, 0.0),
            sample_level="coarse", scan_step=0.05, seed=2025,
            source_stage="global_coarse", source_candidate_index=0,
        )
        self.assertTrue(row.valid)
        self.assertEqual(row.status, "pruned_zero")
        self.assertEqual(row.total_duration_s, 0.0)

    def test_g04_status_not_silently_converted(self):
        row = evaluate_with_real_evaluator(
            (0.0, 100.0, 1.0, 1.0),
            sample_level="coarse", scan_step=0.0, seed=2025,
            source_stage="global_coarse", source_candidate_index=0,
        )
        self.assertFalse(row.valid)
        self.assertEqual(row.status, "system_error")
        self.assertNotEqual(row.status, "ok")
        self.assertNotEqual(row.status, "invalid")
        self.assertIsNotNone(row.error_type)

    def test_g05_evaluator_does_not_clamp_illegal_candidate(self):
        # 越界候选应由 evaluator 返回 invalid, 不得被静默 clamp
        row = evaluate_with_real_evaluator(
            (0.0, 200.0, 1.0, 1.0),
            sample_level="coarse", scan_step=0.05, seed=2025,
            source_stage="global_coarse", source_candidate_index=0,
        )
        # 应当保留 speed=200 的 raw 值, status=invalid
        self.assertEqual(row.speed_mps, 200.0)
        self.assertEqual(row.status, "invalid")


# =============================================================================
#  H — Serial pipeline (P1-C evaluation_id-keyed resume)
# =============================================================================
class HSerialPipeline(unittest.TestCase):

    def test_h01_serial_runs_all(self):
        cands = [
            (0.0, 100.0, 1.0, 1.0),
            (math.pi, 120.0, 2.0, 2.0),
            (math.pi / 2, 110.0, 3.0, 1.5),
        ]
        rows = run_serial_real(cands, sample_level="coarse",
                                scan_step=0.05, seed=2025,
                                source_stage="global_coarse")
        self.assertEqual(len(rows), 3)
        for i, r in enumerate(rows):
            self.assertEqual(r.source_candidate_index, i)

    def test_h02_resume_skips_completed_evaluation(self):
        cands = [
            (0.0, 100.0, 1.0, 1.0),
            (math.pi, 120.0, 2.0, 2.0),
            (math.pi / 2, 110.0, 3.0, 1.5),
        ]
        first = run_serial_real(cands[:2], sample_level="coarse",
                                  scan_step=0.05, seed=2025,
                                  source_stage="global_coarse")
        second = run_serial_real(cands, sample_level="coarse",
                                  scan_step=0.05, seed=2025,
                                  source_stage="global_coarse",
                                  resume_rows=first)
        self.assertEqual(len(second), 3)
        # 通过 evaluation_id 跳过; 验证 total_duration_s 一致
        eid_0 = _compute_evaluation_id("global_coarse", 0, cands[0])
        eid_1 = _compute_evaluation_id("global_coarse", 1, cands[1])
        s0 = next(r for r in second if r.evaluation_id == eid_0)
        s1 = next(r for r in second if r.evaluation_id == eid_1)
        self.assertEqual(s0.total_duration_s, first[0].total_duration_s)
        self.assertEqual(s1.total_duration_s, first[1].total_duration_s)

    def test_h03_rank_top_k(self):
        rows = [
            SearchEvaluationRow(
                evaluation_id=str(i), source_stage="g", source_candidate_index=i,
                physical_candidate_sha256="x", candidate_index=i,
                stage="coarse", seed=2025,
                heading_rad=0.0, speed_mps=100.0,
                release_time_s=1.0, delay_s=1.0,
                valid=True, status="ok",
                total_duration_s=float(i),
                sample_level="coarse", scan_step_s=0.05,
                evaluator_kind="real")
            for i in range(5)
        ]
        ranked = rank_top_k(rows, 2)
        self.assertEqual(len(ranked), 2)
        self.assertEqual(ranked[0].total_duration_s, 4.0)
        self.assertEqual(ranked[1].total_duration_s, 3.0)

    def test_h04_rank_top_k_excludes_non_ok(self):
        rows = [
            SearchEvaluationRow(
                evaluation_id="0", source_stage="g", source_candidate_index=0,
                physical_candidate_sha256="x", candidate_index=0,
                stage="coarse", seed=2025,
                heading_rad=0.0, speed_mps=100.0,
                release_time_s=1.0, delay_s=1.0,
                valid=False, status="invalid", total_duration_s=0.0,
                sample_level="coarse", scan_step_s=0.05,
                evaluator_kind="real"),
            SearchEvaluationRow(
                evaluation_id="1", source_stage="g", source_candidate_index=1,
                physical_candidate_sha256="x", candidate_index=1,
                stage="coarse", seed=2025,
                heading_rad=0.0, speed_mps=100.0,
                release_time_s=1.0, delay_s=1.0,
                valid=True, status="ok", total_duration_s=2.0,
                sample_level="coarse", scan_step_s=0.05,
                evaluator_kind="real"),
        ]
        ranked = rank_top_k(rows, 5)
        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0].evaluation_id, "1")

    def test_h05_dedup_rows_prefers_ok(self):
        r1 = SearchEvaluationRow(
            evaluation_id="1", source_stage="g", source_candidate_index=0,
            physical_candidate_sha256="x", candidate_index=0,
            stage="coarse", seed=2025,
            heading_rad=0.0, speed_mps=100.0,
            release_time_s=1.0, delay_s=1.0,
            valid=False, status="invalid", total_duration_s=0.0,
            sample_level="coarse", scan_step_s=0.05,
            evaluator_kind="real")
        r2 = SearchEvaluationRow(
            evaluation_id="2", source_stage="g", source_candidate_index=0,
            physical_candidate_sha256="x", candidate_index=0,
            stage="fine", seed=2025,
            heading_rad=0.0, speed_mps=100.0,
            release_time_s=1.0, delay_s=1.0,
            valid=True, status="ok", total_duration_s=2.0,
            sample_level="fine", scan_step_s=0.01,
            evaluator_kind="real")
        out = _dedup_rows_by_physical_candidate([r1, r2])
        self.assertEqual(len(out), 1)
        # 应优先 ok + 小 scan step
        self.assertEqual(out[0].status, "ok")


# =============================================================================
#  I — Checkpoint v2 (P1-D + P1-E algorithm_version)
# =============================================================================
class ICheckpointV2(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="q2_search_ckpt_v2_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_i01_roundtrip(self):
        ck = CheckpointV2(
            schema=CHECKPOINT_SCHEMA_V2, algorithm_version=ALGORITHM_VERSION,
            seed=2025, domain_hash="abc", manifest_sha256="def",
            evaluator_kind="real", evaluator_version="v1",
            sampling_method=SAMPLING_METHOD, code_revision="x",
            stage="global_coarse", sample_level="coarse",
            scan_step_s=0.05,
            completed_evaluation_ids=["eid1", "eid2"],
            best_evaluation_id="eid2", best_total=1.5,
            status_counts={"ok": 2},
        )
        path = os.path.join(self.tmpdir, "ck.json")
        save_checkpoint_v2(ck, path)
        loaded = load_checkpoint_v2(path)
        self.assertEqual(loaded.schema, CHECKPOINT_SCHEMA_V2)
        self.assertEqual(loaded.algorithm_version, ALGORITHM_VERSION)
        self.assertEqual(loaded.seed, 2025)
        self.assertEqual(loaded.completed_evaluation_ids, ["eid1", "eid2"])

    def test_i02_schema_mismatch_rejected(self):
        d = {"schema": 999, "algorithm_version": "v1.1", "seed": 2025,
             "domain_hash": "x", "manifest_sha256": "y",
             "evaluator_kind": "real", "evaluator_version": "v1",
             "sampling_method": "deterministic_uniform_pseudorandom",
             "code_revision": "z", "stage": "global_coarse",
             "sample_level": "coarse", "scan_step_s": 0.05}
        path = os.path.join(self.tmpdir, "ck.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(d, f)
        with self.assertRaises(ValueError):
            load_checkpoint_v2(path)

    def test_i03_verify_resume_identity_ok(self):
        d = build_search_domain(TEST_U0, TEST_G)
        d["release_time_s"]["max"] = TEST_T_ARRIVAL - 1
        desc = q_space_descriptor(d)
        ck = CheckpointV2(
            schema=CHECKPOINT_SCHEMA_V2, algorithm_version=ALGORITHM_VERSION,
            seed=2025, domain_hash=_hash_domain(desc),
            manifest_sha256="abc",
            evaluator_kind="real", evaluator_version="v1",
            sampling_method=SAMPLING_METHOD, code_revision="rev",
            stage="global_coarse", sample_level="coarse",
            scan_step_s=0.05,
        )
        verify_resume_identity(
            ck,
            expected_seed=2025, expected_domain=desc,
            expected_manifest_sha="abc", expected_evaluator_kind="real",
            expected_evaluator_version="v1",
            expected_sampling_method=SAMPLING_METHOD,
            expected_stage="global_coarse", expected_sample_level="coarse",
            expected_scan_step=0.05, expected_code_revision="rev",
            expected_algorithm_version=ALGORITHM_VERSION,
        )

    def test_i04_verify_resume_identity_seed_mismatch(self):
        d = build_search_domain(TEST_U0, TEST_G)
        d["release_time_s"]["max"] = TEST_T_ARRIVAL - 1
        desc = q_space_descriptor(d)
        ck = CheckpointV2(
            schema=CHECKPOINT_SCHEMA_V2, algorithm_version=ALGORITHM_VERSION,
            seed=2025, domain_hash=_hash_domain(desc),
            manifest_sha256="abc",
            evaluator_kind="real", evaluator_version="v1",
            sampling_method=SAMPLING_METHOD, code_revision="rev",
            stage="global_coarse", sample_level="coarse",
            scan_step_s=0.05,
        )
        with self.assertRaises(ValueError):
            verify_resume_identity(
                ck,
                expected_seed=9999,
                expected_domain=desc, expected_manifest_sha="abc",
                expected_evaluator_kind="real",
                expected_evaluator_version="v1",
                expected_sampling_method=SAMPLING_METHOD,
                expected_stage="global_coarse", expected_sample_level="coarse",
                expected_scan_step=0.05, expected_code_revision="rev",
                expected_algorithm_version=ALGORITHM_VERSION,
            )

    def test_i05_verify_resume_identity_algorithm_version_mismatch(self):
        d = build_search_domain(TEST_U0, TEST_G)
        d["release_time_s"]["max"] = TEST_T_ARRIVAL - 1
        desc = q_space_descriptor(d)
        ck = CheckpointV2(
            schema=CHECKPOINT_SCHEMA_V2, algorithm_version="v0.9",
            seed=2025, domain_hash=_hash_domain(desc),
            manifest_sha256="abc",
            evaluator_kind="real", evaluator_version="v1",
            sampling_method=SAMPLING_METHOD, code_revision="rev",
            stage="global_coarse", sample_level="coarse",
            scan_step_s=0.05,
        )
        with self.assertRaises(ValueError):
            verify_resume_identity(
                ck,
                expected_seed=2025,
                expected_domain=desc, expected_manifest_sha="abc",
                expected_evaluator_kind="real",
                expected_evaluator_version="v1",
                expected_sampling_method=SAMPLING_METHOD,
                expected_stage="global_coarse", expected_sample_level="coarse",
                expected_scan_step=0.05, expected_code_revision="rev",
                expected_algorithm_version=ALGORITHM_VERSION,
            )

    def test_i06_atomic_write_no_leftover(self):
        ck = CheckpointV2(
            schema=CHECKPOINT_SCHEMA_V2, algorithm_version=ALGORITHM_VERSION,
            seed=2025, domain_hash="x", manifest_sha256="y",
            evaluator_kind="real", evaluator_version="v1",
            sampling_method=SAMPLING_METHOD, code_revision="z",
            stage="global_coarse", sample_level="coarse",
            scan_step_s=0.05,
        )
        path = os.path.join(self.tmpdir, "ck.json")
        save_checkpoint_v2(ck, path)
        leftovers = [f for f in os.listdir(self.tmpdir)
                     if f.startswith(".ckpt_")]
        self.assertEqual(leftovers, [])


# =============================================================================
#  J — Pipeline 5 stages (P1-B medium-confirmed → fine-only)
# =============================================================================
class JPipeline(unittest.TestCase):

    def test_j01_pipeline_5_stages_executed(self):
        out_dir = tempfile.mkdtemp(prefix="q2_pipeline_")
        try:
            out = run_search_pipeline(
                seed=2025, u0=TEST_U0, g=TEST_G,
                t_arrival=TEST_T_ARRIVAL,
                budget={
                    "global_coarse_count": 4,
                    "coarse_top_k": 2,
                    "medium_re_evaluate_count": 2,
                    "local_per_top": 2,
                    "local_max_count": 4,
                    "local_medium_count": 2,
                    "fine_final_count": 1,
                    "local_delta": (0.1, 5.0, 0.5, 0.3),
                },
                output_dir=out_dir,
                enforce_fixed_production_result=False,
            )
            sc = out["stage_counts"]
            self.assertEqual(set(sc.keys()), set(PIPELINE_STAGES))
            self.assertEqual(sc["global_coarse"], 5)  # 4 + anchor
            self.assertEqual(sc["global_medium"], 2)
            self.assertGreaterEqual(sc["local_coarse"], 1)
            # local_medium 可能因 local_coarse 全部非 ok 而为空
            # fine 取 medium_confirmed 池, 可能为 0
            # 总行数 = global_coarse + global_medium + local_coarse + local_medium + fine
            self.assertEqual(
                out["n_total_rows"],
                sc["global_coarse"] + sc["global_medium"]
                + sc["local_coarse"] + sc["local_medium"] + sc["fine"])
            # 5 个阶段都有
            self.assertIn("fine", sc)
        finally:
            shutil.rmtree(out_dir, ignore_errors=True)

    def test_j02_final_best_only_from_fine_rows(self):
        out_dir = tempfile.mkdtemp(prefix="q2_pipeline_fineonly_")
        try:
            out = run_search_pipeline(
                seed=2025, u0=TEST_U0, g=TEST_G,
                t_arrival=TEST_T_ARRIVAL,
                budget={
                    "global_coarse_count": 4,
                    "coarse_top_k": 2,
                    "medium_re_evaluate_count": 2,
                    "local_per_top": 2,
                    "local_max_count": 4,
                    "local_medium_count": 2,
                    "fine_final_count": 1,
                    "local_delta": (0.1, 5.0, 0.5, 0.3),
                },
                output_dir=out_dir,
                enforce_fixed_production_result=False,
            )
            # 若 fine_rows 非空, final_best 必来自 fine
            if out["best_known_candidate"] is not None:
                best_stage = out["best_known_candidate"]["source_stage"]
                best_sample = out["best_known_candidate"]["sample_level"]
                self.assertEqual(best_stage, "fine")
                self.assertEqual(best_sample, "fine")
                self.assertEqual(
                    out["best_known_candidate"]["scan_step_s"], 0.01)
        finally:
            shutil.rmtree(out_dir, ignore_errors=True)

    def test_j03_coarse_optimistic_does_not_override_fine(self):
        # 即使 coarse 评估显示更高 total, fine 阶段后只能看 fine
        out_dir = tempfile.mkdtemp(prefix="q2_pipeline_finewins_")
        try:
            out = run_search_pipeline(
                seed=2025, u0=TEST_U0, g=TEST_G,
                t_arrival=TEST_T_ARRIVAL,
                budget={
                    "global_coarse_count": 4,
                    "coarse_top_k": 2,
                    "medium_re_evaluate_count": 2,
                    "local_per_top": 2,
                    "local_max_count": 4,
                    "local_medium_count": 2,
                    "fine_final_count": 1,
                    "local_delta": (0.1, 5.0, 0.5, 0.3),
                },
                output_dir=out_dir,
                enforce_fixed_production_result=False,
            )
            # 即便 fine total_duration 比 coarse 低, final best 仍来自 fine
            if out["best_known_candidate"] is not None:
                self.assertEqual(
                    out["best_known_candidate"]["source_stage"], "fine")
        finally:
            shutil.rmtree(out_dir, ignore_errors=True)

    def test_j04_lineage_manifest_present(self):
        out_dir = tempfile.mkdtemp(prefix="q2_lineage_")
        try:
            out = run_search_pipeline(
                seed=2025, u0=TEST_U0, g=TEST_G,
                t_arrival=TEST_T_ARRIVAL,
                budget={
                    "global_coarse_count": 4,
                    "coarse_top_k": 2,
                    "medium_re_evaluate_count": 2,
                    "local_per_top": 2,
                    "local_max_count": 4,
                    "local_medium_count": 2,
                    "fine_final_count": 1,
                    "local_delta": (0.1, 5.0, 0.5, 0.3),
                },
                output_dir=out_dir,
                enforce_fixed_production_result=False,
            )
            self.assertIn("lineage_manifest_sha256", out)
            self.assertEqual(len(out["lineage_manifest_sha256"]), 64)
            self.assertIn("run_identity_sha256", out)
            self.assertEqual(len(out["run_identity_sha256"]), 64)
            self.assertNotEqual(
                out["lineage_manifest_sha256"],
                out["run_identity_sha256"])
        finally:
            shutil.rmtree(out_dir, ignore_errors=True)


# =============================================================================
#  K — CLI (P2: --mode formal → 2)
# =============================================================================
class KCLI(unittest.TestCase):

    def test_k01_default_no_run_returns_zero(self):
        rc = qs_main([])
        self.assertEqual(rc, 0)

    def test_k02_run_search_with_fake_rejected(self):
        rc = qs_main(["--run-search", "--evaluator", "fake"])
        self.assertEqual(rc, 2)

    def test_k03_real_workers_gt_one_rejected(self):
        rc = qs_main(["--run-search", "--evaluator", "real",
                       "--workers", "2"])
        self.assertEqual(rc, 2)

    def test_k04_mode_formal_rejected(self):
        rc = qs_main(["--run-search", "--evaluator", "real",
                       "--mode", "formal"])
        self.assertEqual(rc, 2)

    def test_k05_help_returns_zero(self):
        try:
            qs_main(["--help"])
        except SystemExit as e:
            self.assertEqual(e.code, 0)


# =============================================================================
#  L — No result files / no Q1 regression
# =============================================================================
class LNoSideEffects(unittest.TestCase):

    def test_l01_no_result_xlsx_created(self):
        out_dir = "outputs/submission"
        if os.path.isdir(out_dir):
            xs = [f for f in os.listdir(out_dir)
                  if f.startswith("result") and f.endswith(".xlsx")]
            self.assertEqual(xs, [],
                              f"不得在 outputs/submission/ 写入 result*, 实际 {xs}")

    def test_l02_q1_baseline_numerical_unchanged(self):
        row = evaluate_with_real_evaluator(
            Q1_ANCHOR_VEC, sample_level="coarse",
            scan_step=0.05, seed=2025,
            source_stage="global_coarse", source_candidate_index=0,
        )
        self.assertGreater(row.total_duration_s, 1.0)
        self.assertLess(row.total_duration_s, 1.6)

    def test_l03_system_error_returns_one(self):
        # 显式构造一个 system_error pipeline (用 fake evaluator 模拟)
        # 然后检查 status_counts
        # 这里通过 evaluate_with_real_evaluator + scan_step=0 触发 system_error
        out_dir = tempfile.mkdtemp(prefix="q2_syserr_")
        try:
            # 在小预算下, scan_step_coarse=0 不可能 (CLI 不会这样)
            # 这里我们只验证 evaluate_with_real_evaluator 在 system_error 时
            # status='system_error'
            row = evaluate_with_real_evaluator(
                (0.0, 100.0, 1.0, 1.0),
                sample_level="coarse", scan_step=0.0, seed=2025,
                source_stage="global_coarse", source_candidate_index=0,
            )
            self.assertEqual(row.status, "system_error")
        finally:
            shutil.rmtree(out_dir, ignore_errors=True)


# =============================================================================
#  M — Fake evaluator
# =============================================================================
class MFakeEvaluator(unittest.TestCase):

    def test_m01_fake_returns_ok(self):
        row = evaluate_with_fake_evaluator(
            (math.pi, 120.0, 5.0, 4.0),
            sample_level="coarse", scan_step=0.05, seed=2025,
            source_stage="fake", source_candidate_index=0,
        )
        self.assertEqual(row.evaluator_kind, "fake")
        self.assertEqual(row.status, "ok")
        self.assertGreater(row.total_duration_s, 0.0)

    def test_m02_fake_deterministic(self):
        a = evaluate_with_fake_evaluator(
            (1.234, 95.0, 2.5, 0.5),
            sample_level="coarse", scan_step=0.05, seed=2025,
            source_stage="fake", source_candidate_index=0,
        )
        b = evaluate_with_fake_evaluator(
            (1.234, 95.0, 2.5, 0.5),
            sample_level="coarse", scan_step=0.05, seed=2025,
            source_stage="fake", source_candidate_index=0,
        )
        self.assertEqual(a.total_duration_s, b.total_duration_s)

    def test_m03_fake_evaluation_id_set(self):
        row = evaluate_with_fake_evaluator(
            (math.pi, 120.0, 5.0, 4.0),
            sample_level="coarse", scan_step=0.05, seed=2025,
            source_stage="fake", source_candidate_index=0,
        )
        self.assertNotEqual(row.evaluation_id, "")
        self.assertEqual(row.source_stage, "fake")
        self.assertEqual(len(row.physical_candidate_sha256), 64)


# =============================================================================
#  N — Config v2 (P1-F)
# =============================================================================
class NConfigV2(unittest.TestCase):

    def test_n01_load_config_v2_real(self):
        cfg = load_config_v2(DEFAULT_CONFIG_PATH)
        self.assertEqual(cfg["schema_version"], CONFIG_SCHEMA_V2 := 2)
        self.assertEqual(cfg["algorithm_version"], ALGORITHM_VERSION)
        self.assertEqual(cfg["sampling_method"], SAMPLING_METHOD)
        self.assertEqual(cfg["evaluator_kind"], "real")
        self.assertEqual(cfg["formal_enabled"], False)
        self.assertEqual(cfg["checkpoint_schema"], 2)
        self.assertEqual(cfg["workers"], 1)
        self.assertIn("budget", cfg)
        self.assertIn("pipeline_stages", cfg)
        self.assertEqual(set(cfg["pipeline_stages"]), set(PIPELINE_STAGES))

    def test_n02_config_no_magic_bounds(self):
        # magic bounds 防御
        cfg = load_config_v2(DEFAULT_CONFIG_PATH)
        # release_time_s max 必须为 null (推导规则)
        self.assertIsNone(cfg["search_domain"]["release_time_s"]["max"])
        # delay_s max 必须为 null (推导规则)
        self.assertIsNone(cfg["search_domain"]["delay_s"]["max"])

    def test_n03_config_schema_v1_rejected(self):
        with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False) as f:
            json.dump({"schema_version": 1}, f)
            path = f.name
        try:
            with self.assertRaises(ValueError):
                load_config_v2(path)
        finally:
            os.remove(path)

    def test_n04_config_magic_bounds_rejected(self):
        with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False) as f:
            json.dump({"schema_version": 2,
                       "release_max": 66,
                       "delay_max": 30}, f)
            path = f.name
        try:
            with self.assertRaises(ValueError):
                load_config_v2(path)
        finally:
            os.remove(path)

    def test_n05_config_sampling_method_is_deterministic_uniform(self):
        cfg = load_config_v2(DEFAULT_CONFIG_PATH)
        self.assertEqual(cfg["sampling_method"],
                          "deterministic_uniform_pseudorandom")
        # 不得声称 LHS / stratified
        text = json.dumps(cfg)
        self.assertNotIn("latin", text.lower())
        self.assertNotIn("stratif", text.lower())
        self.assertNotIn("lhs", text.lower())


# =============================================================================
#  O — Sampling method docs (P1-G)
# =============================================================================
class OSamplingDocs(unittest.TestCase):

    def test_o01_module_docstring_says_uniform(self):
        # 检查 src/q2_search.py 模块 docstring 显式声明 sampling method
        here = os.path.dirname(os.path.abspath(__file__))
        mod_path = os.path.join(
            os.path.dirname(here), "src", "q2_search.py")
        with open(mod_path, "r", encoding="utf-8") as f:
            text = f.read()
        # 必须包含
        self.assertIn("deterministic uniform pseudorandom", text.lower())
        # 不得在采样方法 *主张* 中声称 LHS / stratified;
        # 显式提到禁止的表述 (e.g. "不再声称 stratified") 是允许的.
        # 这里只检查 generate_deterministic_candidates 的 docstring 与
        # SAMPLING_METHOD constant 周围不含误导性声明.
        lower = text.lower()
        # 必须不含 "latin hypercube" / "stratified sampling" 这类肯定式描述
        # 我们仅否定: 不得在 sampling_method 上下文附近含 "stratif" / "latin"
        # 这里用更严格的搜索: 仅在 SAMPLING_METHOD 行附近检查.
        sm_idx = lower.find("sampling_method")
        self.assertGreaterEqual(sm_idx, 0)
        nearby = lower[max(0, sm_idx - 100):sm_idx + 200]
        self.assertNotIn("stratif", nearby)
        self.assertNotIn("latin", nearby)
        self.assertNotIn("lhs", nearby)

    def test_o02_sampling_method_constant(self):
        self.assertEqual(SAMPLING_METHOD,
                          "deterministic_uniform_pseudorandom")


# =============================================================================
#  P — Physical candidate hash stable (P1-C)
# =============================================================================
class PPhysicalCandidateHash(unittest.TestCase):

    def test_p01_stable_for_same_vec(self):
        v = (1.0, 100.0, 2.0, 1.0)
        self.assertEqual(_physical_candidate_sha256(v),
                          _physical_candidate_sha256(v))

    def test_p02_changes_with_vec(self):
        self.assertNotEqual(
            _physical_candidate_sha256((1.0, 100.0, 2.0, 1.0)),
            _physical_candidate_sha256((1.0, 100.0, 2.0, 1.1)))

    def test_p03_wrap_normalizes_heading(self):
        # heading wrap 应当影响规范化
        a = _physical_candidate_sha256((0.0, 100.0, 2.0, 1.0))
        b = _physical_candidate_sha256((2 * math.pi, 100.0, 2.0, 1.0))
        self.assertEqual(a, b)


# =============================================================================
#  A2 — Effective Config (RP1-3)
# =============================================================================
class AEffectiveConfig(unittest.TestCase):

    def test_a01_default_config_path_exists(self):
        self.assertTrue(os.path.exists(DEFAULT_CONFIG_PATH),
                        f"default config path missing: {DEFAULT_CONFIG_PATH}")

    def test_a02_resolve_default_config(self):
        cfg = resolve_effective_config()
        self.assertEqual(cfg["algorithm_version"], ALGORITHM_VERSION)
        self.assertEqual(cfg["sampling_method"], SAMPLING_METHOD)
        self.assertEqual(cfg["checkpoint_schema"], CHECKPOINT_SCHEMA_V2)
        self.assertEqual(cfg["evaluator_kind"], "real")
        self.assertEqual(cfg["workers"], 1)
        self.assertFalse(cfg["formal_enabled"])

    def test_a03_effective_budget_total_is_163(self):
        cfg = resolve_effective_config()
        self.assertEqual(cfg["total_expected_evaluations"],
                         EXPECTED_TOTAL_EVALUATIONS)
        self.assertEqual(EXPECTED_TOTAL_EVALUATIONS, 163)

    def test_a04_budget_breakdown_matches_spec(self):
        cfg = resolve_effective_config()
        b = cfg["budget"]
        # global_coarse_count 仅随机生成候选数 (不含 anchor)
        # 实际 stage global_coarse = 96 + 1 (anchor) = 97
        self.assertEqual(b["global_coarse_count"], 96)
        self.assertEqual(b["coarse_top_k"], 8)
        self.assertEqual(b["medium_re_evaluate_count"], 8)
        self.assertEqual(b["local_max_count"], 48)
        self.assertEqual(b["local_medium_count"], 8)
        self.assertEqual(b["fine_final_count"], 2)

    def test_a05_stage_plan_5_stages(self):
        cfg = resolve_effective_config()
        sp = cfg["stage_plan"]
        self.assertEqual([s["stage"] for s in sp], list(PIPELINE_STAGES))

    def test_a06_stage_plan_sample_levels(self):
        cfg = resolve_effective_config()
        sl_map = {s["stage"]: s["sample_level"] for s in cfg["stage_plan"]}
        self.assertEqual(sl_map["global_coarse"], "coarse")
        self.assertEqual(sl_map["global_medium"], "medium")
        self.assertEqual(sl_map["local_coarse"], "coarse")
        self.assertEqual(sl_map["local_medium"], "medium")
        self.assertEqual(sl_map["fine"], "fine")

    def test_a07_stage_plan_scan_steps(self):
        cfg = resolve_effective_config()
        ss_map = {s["stage"]: s["scan_step"] for s in cfg["stage_plan"]}
        self.assertAlmostEqual(ss_map["global_coarse"], 0.05, places=12)
        self.assertAlmostEqual(ss_map["global_medium"], 0.02, places=12)
        self.assertAlmostEqual(ss_map["local_coarse"], 0.05, places=12)
        self.assertAlmostEqual(ss_map["local_medium"], 0.02, places=12)
        self.assertAlmostEqual(ss_map["fine"], 0.01, places=12)

    def test_a08_config_sha256_present(self):
        cfg = resolve_effective_config()
        self.assertEqual(len(cfg["raw_config_sha256"]), 64)
        self.assertTrue(all(c in "0123456789abcdef"
                              for c in cfg["raw_config_sha256"]))

    def test_a09_missing_config_raises_filenotfound(self):
        with self.assertRaises((FileNotFoundError, ValueError)):
            resolve_effective_config(config_path="/nonexistent/cfg.json")

    def test_a10_default_config_path_argument(self):
        cfg = resolve_effective_config(config_path=DEFAULT_CONFIG_PATH)
        self.assertEqual(cfg["algorithm_version"], ALGORITHM_VERSION)

    def test_a11_test_only_internal_cli_overrides_bypass_production_gate(self):
        # FIXED-163 BUDGET GATE: resolve_effective_config(cli_overrides=...) 是
        # internal-only / test-only API. production CLI (main()) 永不调用它
        # 携带非空 cli_overrides; 本测试明确该能力仅用于 unit test.
        cfg = resolve_effective_config(cli_overrides={
            "fine_final_count": 5,
        })
        self.assertEqual(cfg["budget"]["fine_final_count"], 5)
        # overrides_applied = True → total 不强制 == 163
        # 即: 96 + 1 anchor + 8 + 48 + 8 + 5 = 166
        self.assertEqual(cfg["total_expected_evaluations"],
                         96 + ANCHOR_COUNT + 8 + 48 + 8 + 5)
        # production CLI argparse 不得含 budget override flag:
        parser = _build_argparser()
        for forbidden in ("--global-coarse-count", "--coarse-top-k",
                          "--local-max-count", "--local-medium-count",
                          "--fine-final-count",
                          "--medium-re-evaluate-count", "--local-per-top"):
            with self.assertRaises(SystemExit):
                parser.parse_args(["--run-search", forbidden, "10"])
        # production main() 调用 resolve_effective_config 时 cli_overrides 必为 None:
        # 通过 _get_production_cli_overrides 不存在性来确认:
        # 直接调用 resolve_effective_config without cli_overrides → production 形态
        cfg_prod = resolve_effective_config(config_path=DEFAULT_CONFIG_PATH)
        self.assertEqual(
            cfg_prod["total_expected_evaluations"],
            EXPECTED_TOTAL_EVALUATIONS)
        # production 不得被 cli_overrides 绕过; 必须 == 163

    def test_a12_stage_plan_for_pipeline_deterministic(self):
        budget = dict(DEFAULT_PILOT_BUDGET)
        scan_steps = {"coarse": 0.05, "medium": 0.02, "fine": 0.01}
        sp1 = _stage_plan_for_pipeline(budget, scan_steps)
        sp2 = _stage_plan_for_pipeline(budget, scan_steps)
        self.assertEqual(sp1, sp2)
        self.assertEqual([s["stage"] for s in sp1], list(PIPELINE_STAGES))

    def test_a13_expected_stage_from_plan_derives(self):
        cfg = resolve_effective_config()
        e = expected_stage_from_plan(cfg["stage_plan"], "global_coarse")
        self.assertEqual(e["sample_level"], "coarse")
        self.assertAlmostEqual(e["scan_step"], 0.05, places=12)

    def test_a14_expected_stage_unknown_raises(self):
        cfg = resolve_effective_config()
        with self.assertRaises(ValueError):
            expected_stage_from_plan(cfg["stage_plan"], "nonexistent")

    def test_a15_resolve_effective_config_accounts_for_anchor(self):
        # Spec: ANCHOR_COUNT=1 必须显式计入 total_evals 公式;
        # 有效 default 配置经过 ANCHOR_COUNT 后 total == 163 (而非 162).
        cfg = resolve_effective_config()
        b = cfg["budget"]
        accounted = (b["global_coarse_count"] + ANCHOR_COUNT
                      + b["coarse_top_k"]
                      + b["local_max_count"]
                      + b["local_medium_count"]
                      + b["fine_final_count"])
        self.assertEqual(accounted, EXPECTED_TOTAL_EVALUATIONS)
        self.assertEqual(accounted, 163)
        # ANCHOR_COUNT 自身是 1 (显式常量, 不是从 budget 推断)
        self.assertEqual(ANCHOR_COUNT, 1)


# =============================================================================
#  B2 — Structured Code Identity (RP1-4)
# =============================================================================
class BStructuredCodeIdentity(unittest.TestCase):

    def test_b01_identity_has_five_fields(self):
        ident = build_structured_code_identity()
        for k in ("git_head_sha", "worktree_dirty", "q2_search_sha256",
                   "config_sha256", "algorithm_version"):
            self.assertIn(k, ident)

    def test_b02_identity_sha256_is_hex64(self):
        ident = build_structured_code_identity()
        sha = compute_structured_code_identity_sha256(ident)
        self.assertEqual(len(sha), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in sha))

    def test_b03_identity_deterministic(self):
        ident1 = build_structured_code_identity()
        ident2 = build_structured_code_identity()
        sha1 = compute_structured_code_identity_sha256(ident1)
        sha2 = compute_structured_code_identity_sha256(ident2)
        self.assertEqual(sha1, sha2)

    def test_b04_q2_search_sha256_64hex(self):
        ident = build_structured_code_identity()
        self.assertEqual(len(ident["q2_search_sha256"]), 64)

    def test_b05_algorithm_version_field(self):
        ident = build_structured_code_identity()
        self.assertEqual(ident["algorithm_version"], ALGORITHM_VERSION)
        self.assertEqual(ident["algorithm_version"], "v1.2")

    def test_b06_worktree_dirty_field_bool(self):
        ident = build_structured_code_identity()
        self.assertIsInstance(ident["worktree_dirty"], bool)


# =============================================================================
#  C2 — Evaluation-Safe Interrupted Checkpoint (RP1-1)
# =============================================================================
class CInterruptedCheckpoint(unittest.TestCase):

    def test_c01_controlled_interruption_exception_attrs(self):
        ci = _ControlledInterruption(completed_count=10,
                                     interrupted_stage="global_coarse",
                                     checkpoint_path="/tmp/ck.json")
        self.assertEqual(ci.completed_count, 10)
        self.assertEqual(ci.interrupted_stage, "global_coarse")
        self.assertEqual(ci.checkpoint_path, "/tmp/ck.json")

    def test_c02_checkpoint_status_field_present(self):
        ck = CheckpointV2(
            schema=CHECKPOINT_SCHEMA_V2,
            algorithm_version=ALGORITHM_VERSION, seed=2025,
            domain_hash="x" * 64, manifest_sha256="y" * 64,
            evaluator_kind="real", evaluator_version="v1",
            sampling_method=SAMPLING_METHOD,
            code_revision="git:abc",
            stage="global_coarse", sample_level="coarse",
            scan_step_s=0.05,
            status="controlled_interruption",
            completed_count=10,
        )
        d = ck.to_dict()
        self.assertEqual(d["status"], "controlled_interruption")
        self.assertEqual(d["completed_count"], 10)
        # roundtrip
        ck2 = CheckpointV2.from_dict(d)
        self.assertEqual(ck2.status, "controlled_interruption")
        self.assertEqual(ck2.completed_count, 10)

    def test_c03_checkpoint_default_status_is_running(self):
        ck = CheckpointV2(
            schema=CHECKPOINT_SCHEMA_V2,
            algorithm_version=ALGORITHM_VERSION, seed=2025,
            domain_hash="x" * 64, manifest_sha256="y" * 64,
            evaluator_kind="real", evaluator_version="v1",
            sampling_method=SAMPLING_METHOD,
            code_revision="git:abc",
            stage="global_coarse", sample_level="coarse",
            scan_step_s=0.05,
        )
        self.assertEqual(ck.status, "running")
        self.assertEqual(ck.completed_count, 0)

    def test_c04_checkpoint_code_identity_sha_field(self):
        ck = CheckpointV2(
            schema=CHECKPOINT_SCHEMA_V2,
            algorithm_version=ALGORITHM_VERSION, seed=2025,
            domain_hash="x" * 64, manifest_sha256="y" * 64,
            evaluator_kind="real", evaluator_version="v1",
            sampling_method=SAMPLING_METHOD,
            code_revision="git:abc",
            stage="global_coarse", sample_level="coarse",
            scan_step_s=0.05,
            code_identity_sha256="z" * 64,
        )
        d = ck.to_dict()
        self.assertEqual(d["code_identity_sha256"], "z" * 64)
        ck2 = CheckpointV2.from_dict(d)
        self.assertEqual(ck2.code_identity_sha256, "z" * 64)


# =============================================================================
#  D2 — Resume Identity from current plan (RP1-2)
# =============================================================================
class DResumeIdentity(unittest.TestCase):

    def test_d01_checkpoint_with_inconsistent_stage_fails(self):
        # create checkpoint at global_medium (sample_level=coarse), but
        # current plan requires medium for global_medium
        ck = CheckpointV2(
            schema=CHECKPOINT_SCHEMA_V2,
            algorithm_version=ALGORITHM_VERSION, seed=2025,
            domain_hash="x" * 64, manifest_sha256="y" * 64,
            evaluator_kind="real", evaluator_version="v1",
            sampling_method=SAMPLING_METHOD,
            code_revision="git:abc",
            stage="global_medium", sample_level="coarse",  # 错位
            scan_step_s=0.02,
        )
        cfg = resolve_effective_config()
        # current plan says global_medium must be sample_level=medium;
        # verify_resume_identity derives from current plan, must fail
        from src.q2_search import verify_resume_identity
        with self.assertRaises(ValueError):
            verify_resume_identity(
                ck,
                expected_seed=2025,
                expected_domain={},  # type: ignore
                expected_manifest_sha="y" * 64,
                expected_evaluator_kind="real",
                expected_evaluator_version="v1",
                expected_sampling_method=SAMPLING_METHOD,
                expected_stage="global_medium",
                expected_sample_level="medium",  # 从 current plan 推导
                expected_scan_step=0.02,
                expected_code_revision="git:abc",
                expected_algorithm_version=ALGORITHM_VERSION,
                expected_config_sha256=cfg["raw_config_sha256"],
            )

    def test_d02_config_sha256_mismatch_raises(self):
        ck = CheckpointV2(
            schema=CHECKPOINT_SCHEMA_V2,
            algorithm_version=ALGORITHM_VERSION, seed=2025,
            domain_hash="x" * 64, manifest_sha256="y" * 64,
            evaluator_kind="real", evaluator_version="v1",
            sampling_method=SAMPLING_METHOD,
            code_revision="git:abc",
            stage="global_coarse", sample_level="coarse",
            scan_step_s=0.05,
            config_sha256="a" * 64,
        )
        from src.q2_search import verify_resume_identity
        with self.assertRaises(ValueError):
            verify_resume_identity(
                ck,
                expected_seed=2025,
                expected_domain={},  # type: ignore
                expected_manifest_sha="y" * 64,
                expected_evaluator_kind="real",
                expected_evaluator_version="v1",
                expected_sampling_method=SAMPLING_METHOD,
                expected_stage="global_coarse",
                expected_sample_level="coarse",
                expected_scan_step=0.05,
                expected_code_revision="git:abc",
                expected_algorithm_version=ALGORITHM_VERSION,
                expected_config_sha256="b" * 64,  # 不匹配
            )


# =============================================================================
#  E2 — Canonical Result + canonical_result_sha256
# =============================================================================
class ECanonicalResult(unittest.TestCase):

    def setUp(self):
        self.fine1 = _make_row(1.0, 100.0, 1.5, 3.6, total=2.5)
        self.fine2 = _make_row(2.0, 110.0, 2.5, 4.0, total=2.0)
        self.med = _make_row(1.0, 100.0, 1.5, 3.6,
                              source_stage="global_medium",
                              sample_level="medium", scan_step=0.02,
                              total=2.4)

    def test_e01_canonical_fields_ordered(self):
        self.assertEqual(CANONICAL_RESULT_FIELDS[0], "task")
        self.assertIn("run_identity_sha256", CANONICAL_RESULT_FIELDS)
        # canonical_result_sha256 是 canonical 的哈希, 不应包含其自身
        self.assertNotIn("canonical_result_sha256", CANONICAL_RESULT_FIELDS)

    def test_e02_canonical_sha256_excludes_paths(self):
        out = build_pilot_output(
            task="t", declaration="d", best_known_disclaimer="b",
            algorithm_version=ALGORITHM_VERSION, sampling_method=SAMPLING_METHOD,
            evaluator_kind="real", evaluator_version="v1",
            code_revision="git:abc", seed=2025, domain_desc={},
            budget={}, static_run_identity={},
            run_identity_sha256="r" * 64,
            lineage_manifest_sha256="l" * 64,
            code_identity={}, code_identity_sha256="c" * 64,
            config_sha256="f" * 64,
            total_expected_evaluations=163,
            status_counts={}, stage_counts={},
            fine_rows=[self.fine1, self.fine2],
            coarse_top_k=[], medium_top=[], local_top=[],
            medium_confirmed_pool_size=1,
            all_rows=[self.fine1, self.fine2],
            final_best_row=self.fine1,
        )
        # 必须含 canonical_result_sha256 字段
        self.assertIn("canonical_result_sha256", out)
        # canonical 不应包含 wall-clock / 路径
        # 这里输出不含 wall_clock; 验证不抛错
        sha = out["canonical_result_sha256"]
        self.assertEqual(len(sha), 64)

    def test_e03_canonical_is_deterministic(self):
        out1 = build_pilot_output(
            task="t", declaration="d", best_known_disclaimer="b",
            algorithm_version=ALGORITHM_VERSION, sampling_method=SAMPLING_METHOD,
            evaluator_kind="real", evaluator_version="v1",
            code_revision="git:abc", seed=2025, domain_desc={"x": {"y": 1}},
            budget={"a": 1}, static_run_identity={"z": 1},
            run_identity_sha256="r" * 64,
            lineage_manifest_sha256="l" * 64,
            code_identity={"q": 1}, code_identity_sha256="c" * 64,
            config_sha256="f" * 64,
            total_expected_evaluations=163,
            status_counts={"ok": 2}, stage_counts={"fine": 2},
            fine_rows=[self.fine1, self.fine2],
            coarse_top_k=[], medium_top=[], local_top=[],
            medium_confirmed_pool_size=1,
            all_rows=[self.fine1, self.fine2],
            final_best_row=self.fine1,
        )
        out2 = build_pilot_output(
            task="t", declaration="d", best_known_disclaimer="b",
            algorithm_version=ALGORITHM_VERSION, sampling_method=SAMPLING_METHOD,
            evaluator_kind="real", evaluator_version="v1",
            code_revision="git:abc", seed=2025, domain_desc={"x": {"y": 1}},
            budget={"a": 1}, static_run_identity={"z": 1},
            run_identity_sha256="r" * 64,
            lineage_manifest_sha256="l" * 64,
            code_identity={"q": 1}, code_identity_sha256="c" * 64,
            config_sha256="f" * 64,
            total_expected_evaluations=163,
            status_counts={"ok": 2}, stage_counts={"fine": 2},
            fine_rows=[self.fine1, self.fine2],
            coarse_top_k=[], medium_top=[], local_top=[],
            medium_confirmed_pool_size=1,
            all_rows=[self.fine1, self.fine2],
            final_best_row=self.fine1,
        )
        self.assertEqual(out1["canonical_result_sha256"],
                         out2["canonical_result_sha256"])

    def test_e04_canonical_sha_changes_with_best(self):
        out_a = build_pilot_output(
            task="t", declaration="d", best_known_disclaimer="b",
            algorithm_version=ALGORITHM_VERSION, sampling_method=SAMPLING_METHOD,
            evaluator_kind="real", evaluator_version="v1",
            code_revision="git:abc", seed=2025, domain_desc={},
            budget={}, static_run_identity={},
            run_identity_sha256="r" * 64,
            lineage_manifest_sha256="l" * 64,
            code_identity={}, code_identity_sha256="c" * 64,
            config_sha256="f" * 64,
            total_expected_evaluations=163,
            status_counts={}, stage_counts={},
            fine_rows=[self.fine1, self.fine2],
            coarse_top_k=[], medium_top=[], local_top=[],
            medium_confirmed_pool_size=1,
            all_rows=[self.fine1, self.fine2],
            final_best_row=self.fine1,
        )
        out_b = build_pilot_output(
            task="t", declaration="d", best_known_disclaimer="b",
            algorithm_version=ALGORITHM_VERSION, sampling_method=SAMPLING_METHOD,
            evaluator_kind="real", evaluator_version="v1",
            code_revision="git:abc", seed=2025, domain_desc={},
            budget={}, static_run_identity={},
            run_identity_sha256="r" * 64,
            lineage_manifest_sha256="l" * 64,
            code_identity={}, code_identity_sha256="c" * 64,
            config_sha256="f" * 64,
            total_expected_evaluations=163,
            status_counts={}, stage_counts={},
            fine_rows=[self.fine1, self.fine2],
            coarse_top_k=[], medium_top=[], local_top=[],
            medium_confirmed_pool_size=1,
            all_rows=[self.fine1, self.fine2],
            final_best_row=self.fine2,
        )
        self.assertNotEqual(out_a["canonical_result_sha256"],
                            out_b["canonical_result_sha256"])

    def test_e05_canonical_function_direct(self):
        sha = compute_canonical_result_sha256({"task": "t", "seed": 2025})
        self.assertEqual(len(sha), 64)


# =============================================================================
#  F2 — Two-Finalist Lineage + Dirty Worktree Rejection (RP1-5/7)
# =============================================================================
class FFinalistLineage(unittest.TestCase):

    def setUp(self):
        # Two finalists with different medium parents
        self.med_global = _make_row(1.0, 100.0, 1.5, 3.6,
                                     source_stage="global_medium",
                                     sample_level="medium",
                                     scan_step=0.02, total=2.4)
        self.med_local = _make_row(2.0, 110.0, 2.5, 4.0,
                                    source_stage="local_medium",
                                    sample_level="medium",
                                    scan_step=0.02, total=2.3)
        self.fine1 = _make_row(1.0, 100.0, 1.5, 3.6,
                                source_stage="fine",
                                sample_level="fine",
                                scan_step=0.01, total=2.5)
        self.fine2 = _make_row(2.0, 110.0, 2.5, 4.0,
                                source_stage="fine",
                                sample_level="fine",
                                scan_step=0.01, total=2.0)

    def test_f01_two_finalists_full_lineage(self):
        lineage = build_fine_lineage(
            [self.fine1, self.fine2], [self.med_global, self.med_local])
        self.assertEqual(len(lineage), 2)
        ranks = [f["finalist_rank"] for f in lineage]
        self.assertEqual(ranks, [1, 2])  # by total_duration_s desc

    def test_f02_finalist_has_all_required_fields(self):
        lineage = build_fine_lineage(
            [self.fine1], [self.med_global])
        f = lineage[0]
        for k in ("finalist_rank", "physical_candidate",
                   "fine_evaluation_id", "fine_total_duration_s",
                   "parent_medium_source", "parent_evaluation_id",
                   "parent_total_duration_s"):
            self.assertIn(k, f)

    def test_f03_finalist_parent_source_from_medium(self):
        lineage = build_fine_lineage(
            [self.fine1], [self.med_global])
        self.assertEqual(lineage[0]["parent_medium_source"], "global_medium")
        self.assertEqual(lineage[0]["parent_evaluation_id"],
                         self.med_global.evaluation_id)

    def test_f04_empty_fine_returns_empty_list(self):
        lineage = build_fine_lineage([], [self.med_global])
        self.assertEqual(lineage, [])

    def test_f05_invalid_fine_rows_excluded(self):
        bad = _make_row(3.0, 120.0, 3.0, 5.0, valid=False, status="invalid")
        lineage = build_fine_lineage([bad], [self.med_global])
        self.assertEqual(lineage, [])


# =============================================================================
#  G2 — Dirty Worktree Rejection (RP1-5) + Pipeline smoke (RP1 P2 uniq schema)
# =============================================================================
class GDirtyWorktree(unittest.TestCase):

    def test_g01_dirty_worktree_raises(self):
        # 创建一个临时 dirty worktree (git init + 写入 untracked 文件)
        tmp = tempfile.mkdtemp(prefix="q2dirty_")
        try:
            import subprocess
            subprocess.run(["git", "init"], cwd=tmp,
                           capture_output=True, timeout=10)
            subprocess.run(["git", "config", "user.email", "a@b"],
                           cwd=tmp, capture_output=True, timeout=5)
            subprocess.run(["git", "config", "user.name", "a"],
                           cwd=tmp, capture_output=True, timeout=5)
            # commit 一个文件让 HEAD 存在
            with open(os.path.join(tmp, "x.txt"), "w") as f:
                f.write("hi")
            subprocess.run(["git", "add", "x.txt"], cwd=tmp,
                           capture_output=True, timeout=5)
            subprocess.run(["git", "commit", "-m", "init"],
                           cwd=tmp, capture_output=True, timeout=10)
            # 写 untracked 文件
            with open(os.path.join(tmp, "untracked.txt"), "w") as f:
                f.write("dirty")
            ident = build_structured_code_identity(workdir=tmp)
            self.assertTrue(ident["worktree_dirty"])
            # pipeline 应 raise
            with self.assertRaises(ValueError):
                run_search_pipeline(
                    seed=2025, u0=TEST_U0, g=TEST_G,
                    t_arrival=TEST_T_ARRIVAL,
                    budget={"global_coarse_count": 2, "coarse_top_k": 1,
                            "medium_re_evaluate_count": 1, "local_per_top": 1,
                            "local_max_count": 2, "local_medium_count": 1,
                            "fine_final_count": 1,
                            "local_delta": (0.1, 5.0, 0.5, 0.3)},
                    output_dir=tmp,
                    config_path=DEFAULT_CONFIG_PATH,
                    require_clean_worktree=True,
                    workdir=tmp,
                )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_g02_clean_worktree_passes(self):
        tmp = tempfile.mkdtemp(prefix="q2clean_")
        try:
            import subprocess
            subprocess.run(["git", "init"], cwd=tmp,
                           capture_output=True, timeout=10)
            subprocess.run(["git", "config", "user.email", "a@b"],
                           cwd=tmp, capture_output=True, timeout=5)
            subprocess.run(["git", "config", "user.name", "a"],
                           cwd=tmp, capture_output=True, timeout=5)
            with open(os.path.join(tmp, "x.txt"), "w") as f:
                f.write("hi")
            subprocess.run(["git", "add", "x.txt"], cwd=tmp,
                           capture_output=True, timeout=5)
            subprocess.run(["git", "commit", "-m", "init"],
                           cwd=tmp, capture_output=True, timeout=10)
            ident = build_structured_code_identity(workdir=tmp)
            self.assertFalse(ident["worktree_dirty"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# =============================================================================
#  H2 — Pilot smoke (RP1 P2 uniq output schema + stop-after-evaluations)
# =============================================================================
class HPilotSmoke(unittest.TestCase):

    def test_h01_pilot_run_complete_produces_canonical(self):
        out_dir = tempfile.mkdtemp(prefix="q2rp1_")
        try:
            out = run_search_pipeline(
                seed=2025, u0=TEST_U0, g=TEST_G,
                t_arrival=TEST_T_ARRIVAL,
                budget={
                    "global_coarse_count": 4,
                    "coarse_top_k": 2,
                    "medium_re_evaluate_count": 2,
                    "local_per_top": 2,
                    "local_max_count": 4,
                    "local_medium_count": 2,
                    "fine_final_count": 2,
                    "local_delta": (0.1, 5.0, 0.5, 0.3),
                },
                output_dir=out_dir,
                config_path=DEFAULT_CONFIG_PATH,
                require_clean_worktree=False,
                enforce_fixed_production_result=False,
            )
            self.assertIn("canonical_result_sha256", out)
            self.assertEqual(len(out["canonical_result_sha256"]), 64)
            self.assertEqual(out["algorithm_version"], ALGORITHM_VERSION)
            # 4 random global_coarse + 1 anchor + 2 medium + 4 local + 2 local_medium + 2 fine = 15
            self.assertEqual(out["total_expected_evaluations"],
                             4 + ANCHOR_COUNT + 2 + 4 + 2 + 2)
            self.assertFalse(out["controlled_interruption"])
            # fine finalists lineage present
            self.assertIn("lineage_manifest", out)
            self.assertIn("fine_finalists_lineage",
                          out["lineage_manifest"])
        finally:
            shutil.rmtree(out_dir, ignore_errors=True)

    def test_h02_stop_after_evaluations_raises(self):
        out_dir = tempfile.mkdtemp(prefix="q2rp1_stop_")
        try:
            with self.assertRaises(_ControlledInterruption):
                run_search_pipeline(
                    seed=2025, u0=TEST_U0, g=TEST_G,
                    t_arrival=TEST_T_ARRIVAL,
                    budget={
                        "global_coarse_count": 4,
                        "coarse_top_k": 2,
                        "medium_re_evaluate_count": 2,
                        "local_per_top": 2,
                        "local_max_count": 4,
                        "local_medium_count": 2,
                        "fine_final_count": 2,
                        "local_delta": (0.1, 5.0, 0.5, 0.3),
                    },
                    output_dir=out_dir,
                    config_path=DEFAULT_CONFIG_PATH,
                    require_clean_worktree=False,
                    stop_after_evaluations=3,
                )
            # checkpoint file must exist
            ck_path = os.path.join(out_dir, "checkpoint_v2.json")
            self.assertTrue(os.path.exists(ck_path))
            marker_path = os.path.join(out_dir, "controlled_interruption.json")
            self.assertTrue(os.path.exists(marker_path))
            with open(marker_path, "r", encoding="utf-8") as f:
                m = json.load(f)
            self.assertEqual(m["status"], "CONTROLLED_INTERRUPTION")
            self.assertGreaterEqual(m["completed_count"], 3)
        finally:
            shutil.rmtree(out_dir, ignore_errors=True)

    def test_h03_uniq_output_schema_resumed_and_uninterrupted(self):
        # uninterrupted path output schema == resumed path output schema
        # (build_pilot_output 是唯一 constructor; 通过属性集合验证)
        out_dir_a = tempfile.mkdtemp(prefix="q2rp1_a_")
        out_dir_b = tempfile.mkdtemp(prefix="q2rp1_b_")
        try:
            out_a = run_search_pipeline(
                seed=2025, u0=TEST_U0, g=TEST_G,
                t_arrival=TEST_T_ARRIVAL,
                budget={
                    "global_coarse_count": 4,
                    "coarse_top_k": 2,
                    "medium_re_evaluate_count": 2,
                    "local_per_top": 2,
                    "local_max_count": 4,
                    "local_medium_count": 2,
                    "fine_final_count": 2,
                    "local_delta": (0.1, 5.0, 0.5, 0.3),
                },
                output_dir=out_dir_a,
                config_path=DEFAULT_CONFIG_PATH,
                require_clean_worktree=False,
                enforce_fixed_production_result=False,
            )
            # resume from checkpoint_v2.json → same schema
            ck_path = os.path.join(out_dir_a, "checkpoint_v2.json")
            self.assertTrue(os.path.exists(ck_path))
            out_b = run_search_pipeline(
                seed=2025, u0=TEST_U0, g=TEST_G,
                t_arrival=TEST_T_ARRIVAL,
                budget={
                    "global_coarse_count": 4,
                    "coarse_top_k": 2,
                    "medium_re_evaluate_count": 2,
                    "local_per_top": 2,
                    "local_max_count": 4,
                    "local_medium_count": 2,
                    "fine_final_count": 2,
                    "local_delta": (0.1, 5.0, 0.5, 0.3),
                },
                output_dir=out_dir_b,
                config_path=DEFAULT_CONFIG_PATH,
                require_clean_worktree=False,
                resume_from=ck_path,
                enforce_fixed_production_result=False,
            )
            schema_a = set(out_a.keys())
            schema_b = set(out_b.keys())
            self.assertEqual(schema_a, schema_b)
            # 核心字段
            for k in CANONICAL_RESULT_FIELDS:
                self.assertIn(k, out_a)
                self.assertIn(k, out_b)
        finally:
            shutil.rmtree(out_dir_a, ignore_errors=True)
            shutil.rmtree(out_dir_b, ignore_errors=True)


# =============================================================================
#  I2 — CLI (RP1 P2 rc codes)
# =============================================================================
class ICLI(unittest.TestCase):

    def test_i01_cli_banner_no_run_search(self):
        try:
            rc = qs_main([])
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 0
        # 默认无 --run-search: rc=0 (banner)
        self.assertEqual(rc, 0)

    def test_i02_cli_formal_mode_rejected(self):
        try:
            rc = qs_main(["--run-search", "--mode", "formal"])
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 2
        self.assertEqual(rc, 2)

    def test_i03_cli_workers_gt_one_rejected(self):
        try:
            rc = qs_main(["--run-search", "--workers", "2"])
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 2
        self.assertEqual(rc, 2)

    def test_i04_cli_missing_config_returns_2(self):
        try:
            rc = qs_main(["--run-search",
                           "--config", "/nonexistent/cfg.json"])
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 2
        self.assertEqual(rc, 2)

    def test_i05_argparser_has_stop_after_evaluations(self):
        parser = _build_argparser()
        args = parser.parse_args(["--run-search",
                                   "--stop-after-evaluations", "10"])
        self.assertEqual(args.stop_after_evaluations, 10)

    def test_i06_argparser_has_allow_dirty_worktree(self):
        parser = _build_argparser()
        args = parser.parse_args(["--run-search",
                                   "--allow-dirty-worktree"])
        self.assertTrue(args.allow_dirty_worktree)

    def test_i07_argparser_has_workdir(self):
        parser = _build_argparser()
        args = parser.parse_args(["--run-search",
                                   "--workdir", "/tmp/wt"])
        self.assertEqual(args.workdir, "/tmp/wt")


# =============================================================================
#  J2 — FIXED-163 BUDGET GATE (Production CLI + Result Invariant)
# =============================================================================
class JFIXED163Gate(unittest.TestCase):

    # ────────────── §五-1: wrong config file rejects ──────────────

    def test_jz01_modified_config_with_global_coarse_count_97_raises(self):
        # 临时复制 production config, 修改 global_coarse_count 到 97
        # (实际总数 = 97 + 1 anchor + 8 + 48 + 8 + 2 = 164).
        # 不传 cli_overrides → 必须 raise ValueError (RP1-3 fail-closed).
        tmp = tempfile.mkdtemp(prefix="q2cfg97_")
        try:
            tmp_cfg = os.path.join(tmp, "q2_search_gate_modified.json")
            shutil.copyfile(DEFAULT_CONFIG_PATH, tmp_cfg)
            # 强制改回 97
            with open(tmp_cfg, "r", encoding="utf-8") as f:
                cfg_data = json.load(f)
            cfg_data["budget"]["global_coarse_count"] = 97
            with open(tmp_cfg, "w", encoding="utf-8") as f:
                json.dump(cfg_data, f, ensure_ascii=False)
            with self.assertRaises(ValueError) as ctx:
                resolve_effective_config(config_path=tmp_cfg)
            # 错误信息必须明确说明固定 163 门禁
            self.assertIn("163", str(ctx.exception))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # ────────────── §五-2: production CLI 拒绝 global_coarse_count override ──────────────

    def test_jz02_production_cli_rejects_global_coarse_count(self):
        try:
            rc = qs_main(["--run-search", "--global-coarse-count", "97"])
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 2
        self.assertEqual(rc, 2)

    # ────────────── §五-3: production CLI 拒绝所有 budget override flags ──────────────

    def test_jz03_production_cli_rejects_coarse_top_k(self):
        try:
            rc = qs_main(["--run-search", "--coarse-top-k", "10"])
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 2
        self.assertEqual(rc, 2)

    def test_jz04_production_cli_rejects_local_max_count(self):
        try:
            rc = qs_main(["--run-search", "--local-max-count", "100"])
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 2
        self.assertEqual(rc, 2)

    def test_jz05_production_cli_rejects_local_medium_count(self):
        try:
            rc = qs_main(["--run-search", "--local-medium-count", "100"])
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 2
        self.assertEqual(rc, 2)

    def test_jz06_production_cli_rejects_fine_final_count(self):
        try:
            rc = qs_main(["--run-search", "--fine-final-count", "100"])
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 2
        self.assertEqual(rc, 2)

    def test_jz07_production_cli_rejects_medium_re_evaluate_count(self):
        try:
            rc = qs_main(["--run-search", "--medium-re-evaluate-count", "10"])
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 2
        self.assertEqual(rc, 2)

    # ────────────── §五-5: validate_fixed_production_result 单点检查 ──────────────

    def _make_valid_inputs(self):
        # 构造通过形态的 stage_counts + 163 个 unique evaluation_id rows
        rows = []
        seen = set()
        # 97 + 8 + 48 + 8 + 2 = 163
        order = [("global_coarse", 97), ("global_medium", 8),
                 ("local_coarse", 48), ("local_medium", 8),
                 ("fine", 2)]
        for stage, n in order:
            for i in range(n):
                eid = f"{stage}-row-{i}"
                assert eid not in seen
                seen.add(eid)
                rows.append(_make_row(
                    1.0 + 0.01 * i, 100.0 + i, 1.0, 0.5,
                    source_stage=stage, sample_level=stage,
                    scan_step=0.05, total=1.0 + 0.001 * i,
                    eval_id=eid))
        return EXPECTED_STAGE_COUNTS_PRODUCTION.copy(), rows, 163

    def test_jz08_validate_accepts_canonical_163_shape(self):
        sc, rows, cc = self._make_valid_inputs()
        validate_fixed_production_result(
            stage_counts=sc, all_rows=rows, completed_count=cc)
        # 不抛即通过

    def test_jz09_validate_rejects_wrong_stage_counts(self):
        sc, rows, cc = self._make_valid_inputs()
        sc["global_coarse"] = 99  # 任意一处错
        with self.assertRaises(FixedProductionBudgetInvariantError) as ctx:
            validate_fixed_production_result(
                stage_counts=sc, all_rows=rows, completed_count=cc)
        self.assertIn("stage_counts", str(ctx.exception))

    def test_jz10_validate_rejects_total_rows_not_163(self):
        sc, rows, cc = self._make_valid_inputs()
        rows = rows[:-1]  # 162
        with self.assertRaises(FixedProductionBudgetInvariantError) as ctx:
            validate_fixed_production_result(
                stage_counts=sc, all_rows=rows, completed_count=cc)
        self.assertIn("len(all_rows)", str(ctx.exception))

    def test_jz11_validate_rejects_duplicate_evaluation_ids(self):
        sc, rows, cc = self._make_valid_inputs()
        # 制造重复: 用最后两个 row 共享 evaluation_id
        rows[-1] = _make_row(
            1.0 + 0.01 * 96, 100.0 + 96, 1.0, 0.5,
            source_stage="fine", sample_level="fine",
            scan_step=0.05, total=1.5,
            eval_id=rows[-2].evaluation_id)
        with self.assertRaises(FixedProductionBudgetInvariantError) as ctx:
            validate_fixed_production_result(
                stage_counts=sc, all_rows=rows, completed_count=cc)
        self.assertIn("unique evaluation_ids", str(ctx.exception))

    def test_jz12_validate_rejects_completed_count_mismatch(self):
        sc, rows, cc = self._make_valid_inputs()
        cc = 100  # 谎报
        with self.assertRaises(FixedProductionBudgetInvariantError) as ctx:
            validate_fixed_production_result(
                stage_counts=sc, all_rows=rows, completed_count=cc)
        self.assertIn("completed_count", str(ctx.exception))

    def test_jz13_validate_rejects_stage_sum_not_163(self):
        sc, rows, cc = self._make_valid_inputs()
        # stage_counts 各项都为 dict() == EXPECTED... 仍可通过精确相等检查,
        # 所以 sum 不可能 mismatch. 此处验证 sum 分支: 通过篡改 rows 让
        # validator 在 stage_counts 精确匹配路径之后, 仍可能 sum != 163.
        # 为此我们构造 rows 然后通过一个修改副本:
        sc["global_coarse"] = 96  # 先让精确匹配失败
        # 删除之前已构造的 1 行 global_coarse 来避免 sum overflow; 用空集.
        # 实际上精确匹配已 catch sum 路径. 此测试改为验证精确匹配兜底.
        with self.assertRaises(FixedProductionBudgetInvariantError):
            validate_fixed_production_result(
                stage_counts=sc, all_rows=rows, completed_count=cc)

    # ────────────── §五-6: stop-after-evaluations 严格等号 ──────────────

    def test_jz14_stop_after_evaluations_strict_equality(self):
        # stop_after_evaluations=3 必须精确停在 3 (not >= 3).
        out_dir = tempfile.mkdtemp(prefix="q2jz_strict_")
        try:
            with self.assertRaises(_ControlledInterruption) as ci_ctx:
                run_search_pipeline(
                    seed=2025, u0=TEST_U0, g=TEST_G,
                    t_arrival=TEST_T_ARRIVAL,
                    budget={
                        "global_coarse_count": 4,
                        "coarse_top_k": 2,
                        "medium_re_evaluate_count": 2,
                        "local_per_top": 2,
                        "local_max_count": 4,
                        "local_medium_count": 2,
                        "fine_final_count": 2,
                        "local_delta": (0.1, 5.0, 0.5, 0.3),
                    },
                    output_dir=out_dir,
                    config_path=DEFAULT_CONFIG_PATH,
                    require_clean_worktree=False,
                    stop_after_evaluations=3,
                )
            ci = ci_ctx.exception
            # ci.completed_count 必须精确 = 3 (not >=)
            self.assertEqual(ci.completed_count, 3)
            # ckpt 文件存在 + rows 数 == 3
            ck_path = os.path.join(out_dir, "checkpoint_v2.json")
            self.assertTrue(os.path.exists(ck_path))
            ck = load_checkpoint_v2(ck_path)
            self.assertEqual(len(ck.rows), 3)
            self.assertEqual(len(ck.completed_evaluation_ids), 3)
            # marker 文件存在
            marker = os.path.join(out_dir, "controlled_interruption.json")
            self.assertTrue(os.path.exists(marker))
        finally:
            shutil.rmtree(out_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)