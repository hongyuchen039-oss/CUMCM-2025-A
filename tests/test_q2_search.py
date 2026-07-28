"""tests/test_q2_search.py — TASK_004 Q2 REAL SEARCH CORE V1 P1 REMEDIATION 单元测试.

覆盖 (P1-A/B/C/D/E/F/G + P2):
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
    DEFAULT_PILOT_BUDGET,
    ALGORITHM_VERSION,
    SAMPLING_METHOD,
    PIPELINE_STAGES,
    main as qs_main,
)


# =============================================================================
#  Fixture: u0 / g / t_arrival (与最新 main 同步)
# =============================================================================
TEST_U0 = (17800.0, 0.0, 1800.0)
TEST_G = 9.8
TEST_T_ARRIVAL = 67.0


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


if __name__ == "__main__":
    unittest.main(verbosity=2)