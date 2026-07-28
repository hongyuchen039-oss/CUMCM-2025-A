"""tests/test_q2_search.py — TASK_004 Q2 REAL SEARCH CORE V1 单元测试.

覆盖:
  - 搜索域描述符 (无魔法上界)
  - manifest 文本与 SHA-256 (锁定)
  - candidate generation (deterministic, anchor included)
  - heading wrap / local clamp
  - SearchEvaluationRow 序列化
  - 五类 status 分类 (invalid / pruned_zero / zero_window / ok / system_error)
  - real evaluator integration (Q1 anchor 非零)
  - checkpoint v2 identity mismatch 拒绝
  - coarse → medium → local → fine pipeline 顺序
  - CLI: --run-search --evaluator fake 拒绝
  - CLI: real 模式 workers > 1 拒绝
  - 不生成 result1/2/3.xlsx
  - 不修改 Q1 / Q2 Foundation 数值

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
    CheckpointV2,
    CHECKPOINT_SCHEMA_V2,
    DEFAULT_PILOT_BUDGET,
    main as qs_main,
)


# =============================================================================
#  Fixture: u0 / g / t_arrival (与最新 main 同步)
# =============================================================================
TEST_U0 = (17800.0, 0.0, 1800.0)
TEST_G = 9.8
TEST_T_ARRIVAL = 67.0  # 简化的合成上界 (用于纯 search 单测, 避免真实耗时)


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
            parse_candidate([0.0, 100.0, 2.0])  # len != 4


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

    def test_b05_release_time_max_is_none(self):
        # 默认构造不含上界; 调用方注入 t_arrival 后才设置
        d = build_search_domain(TEST_U0, TEST_G)
        self.assertIsNone(d["release_time_s"]["max"])

    def test_b06_no_magic_66_or_30(self):
        # 显式断言: 域中不得出现 66 / 30 这类未经说明的硬上界
        d = build_search_domain(TEST_U0, TEST_G)
        # release_time_s max 仍为 None
        self.assertIsNone(d["release_time_s"]["max"])
        # delay_s max 由公式推导, 不等于 30
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
        d_in = [a, b, c, a]
        out = dedup_candidates(d_in)
        self.assertEqual(out, [a, c])


# =============================================================================
#  D — Local candidates
# =============================================================================
class DLocalCandidates(unittest.TestCase):

    def test_d01_local_wraps_heading(self):
        d = build_search_domain(TEST_U0, TEST_G)
        d["release_time_s"]["max"] = TEST_T_ARRIVAL - 1
        import random
        rng = random.Random(2025)
        base = (math.pi * 1.95, 120.0, 2.0, 1.0)
        # delta = 0.5 rad; 1.95 * pi + 0.5 may exceed 2π
        cands = [
            wrap_local_candidate(base, rng, d, d["release_time_s"]["max"],
                                  (0.5, 5.0, 0.5, 0.3))
            for _ in range(20)
        ]
        for h, s, r, dl in cands:
            self.assertGreaterEqual(h, 0.0)
            self.assertLess(h, 2 * math.pi)
            self.assertGreaterEqual(s, 70.0)
            self.assertLessEqual(s, 140.0)


# =============================================================================
#  E — Manifest
# =============================================================================
class EManifest(unittest.TestCase):

    def test_e01_manifest_text_deterministic(self):
        v = [(1.0, 100.0, 2.0, 1.0), (math.pi, 120.0, 1.5, 3.6)]
        a = build_manifest_text(2025, v)
        b = build_manifest_text(2025, v)
        self.assertEqual(a, b)

    def test_e02_manifest_changes_with_seed(self):
        v = [(1.0, 100.0, 2.0, 1.0)]
        a = build_manifest_text(2025, v)
        b = build_manifest_text(2026, v)
        self.assertNotEqual(a, b)

    def test_e03_manifest_record_fields(self):
        v = [(1.0, 100.0, 2.0, 1.0)]
        rec = manifest_record(2025, v)
        self.assertEqual(rec["seed"], 2025)
        self.assertEqual(rec["algorithm_version"], "v1")
        self.assertEqual(rec["n_vectors"], 1)
        self.assertEqual(len(rec["vectors"][0]), 4)
        self.assertEqual(len(rec["sha256"]), 64)  # SHA-256 hex

    def test_e04_manifest_record_with_domain(self):
        d = build_search_domain(TEST_U0, TEST_G)
        v = [(1.0, 100.0, 2.0, 1.0)]
        rec = manifest_record(2025, v, domain=q_space_descriptor(d))
        self.assertIn("domain=", rec["text"])


# =============================================================================
#  F — SearchEvaluationRow serialization
# =============================================================================
class FSearchEvaluationRow(unittest.TestCase):

    def test_f01_to_from_dict(self):
        r = SearchEvaluationRow(
            candidate_index=0, stage="coarse", seed=2025,
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
        self.assertEqual(r2.candidate_index, 0)
        self.assertEqual(r2.intervals, ((8.0, 9.5),))
        self.assertEqual(r2.release_point, (17000.0, 0.0, 1800.0))
        self.assertEqual(r2.evaluator_kind, "real")

    def test_f02_optional_fields_in_dict(self):
        r = SearchEvaluationRow(
            candidate_index=0, stage="coarse", seed=2025,
            heading_rad=0.0, speed_mps=100.0,
            release_time_s=2.0, delay_s=1.0,
            valid=False, status="invalid", total_duration_s=0.0,
        )
        d = r.to_dict()
        self.assertIsNone(d["release_point"])
        self.assertIsNone(d["detonation_time_s"])
        self.assertIsNone(d["detonation_point"])
        self.assertIsNone(d["error_type"])


# =============================================================================
#  G — Real evaluator integration
# =============================================================================
class GRealEvaluator(unittest.TestCase):

    def test_g01_q1_anchor_nonzero(self):
        row = evaluate_with_real_evaluator(
            Q1_ANCHOR_VEC, sample_level="coarse",
            scan_step=0.05, seed=2025,
        )
        self.assertEqual(row.evaluator_kind, "real")
        self.assertTrue(row.valid)
        self.assertEqual(row.status, "ok")
        self.assertGreater(row.total_duration_s, 0.0)
        self.assertGreater(len(row.intervals), 0)

    def test_g02_invalid_status_returns_invalid(self):
        # speed out of range → invalid
        row = evaluate_with_real_evaluator(
            (0.0, 200.0, 1.0, 1.0),  # speed=200 > 140
            sample_level="coarse", scan_step=0.05, seed=2025,
        )
        self.assertFalse(row.valid)
        self.assertEqual(row.status, "invalid")
        self.assertEqual(row.total_duration_s, 0.0)

    def test_g03_pruned_zero_status(self):
        # t_detonate > t_arrival (release_time + delay >> arrival)
        # Choose: release=80, delay=0; t_d=80 > ~67 (real arrival)
        row = evaluate_with_real_evaluator(
            (0.0, 100.0, 80.0, 0.0),
            sample_level="coarse", scan_step=0.05, seed=2025,
        )
        self.assertTrue(row.valid)
        self.assertEqual(row.status, "pruned_zero")
        self.assertEqual(row.total_duration_s, 0.0)

    def test_g04_status_not_silently_converted(self):
        # scan_step=0 → Foundation 抛 ValueError → system_error
        # (Foundation 自身在 scan_step<=0 时抛 ValueError, 不得静默转为 0)
        row = evaluate_with_real_evaluator(
            (0.0, 100.0, 1.0, 1.0),
            sample_level="coarse", scan_step=0.0, seed=2025,
        )
        self.assertFalse(row.valid)
        self.assertEqual(row.status, "system_error")
        # 不得静默转为 0/ok
        self.assertNotEqual(row.status, "ok")
        self.assertNotEqual(row.status, "invalid")
        self.assertIsNotNone(row.error_type)


# =============================================================================
#  H — Serial pipeline
# =============================================================================
class HSerialPipeline(unittest.TestCase):

    def test_h01_serial_runs_all(self):
        cands = [
            (0.0, 100.0, 1.0, 1.0),
            (math.pi, 120.0, 2.0, 2.0),
            (math.pi / 2, 110.0, 3.0, 1.5),
        ]
        rows = run_serial_real(cands, sample_level="coarse",
                                scan_step=0.05, seed=2025)
        self.assertEqual(len(rows), 3)
        for i, r in enumerate(rows):
            self.assertEqual(r.candidate_index, i)

    def test_h02_resume_skips_completed(self):
        cands = [
            (0.0, 100.0, 1.0, 1.0),
            (math.pi, 120.0, 2.0, 2.0),
            (math.pi / 2, 110.0, 3.0, 1.5),
        ]
        # First run: only first 2 cands
        first = run_serial_real(cands[:2], sample_level="coarse",
                                  scan_step=0.05, seed=2025)
        # Resume: all 3 cands, with first 2 already in resume_rows
        second = run_serial_real(cands, sample_level="coarse",
                                  scan_step=0.05, seed=2025,
                                  resume_rows=first)
        # candidate_index 0,1 already done; index 2 newly evaluated
        self.assertEqual(len(second), 3)
        # Rows for index 0,1 should match first run
        self.assertEqual(second[0].total_duration_s, first[0].total_duration_s)
        self.assertEqual(second[1].total_duration_s, first[1].total_duration_s)

    def test_h03_rank_top_k(self):
        rows = [
            SearchEvaluationRow(candidate_index=i, stage="coarse", seed=2025,
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
            SearchEvaluationRow(candidate_index=0, stage="coarse", seed=2025,
                                  heading_rad=0.0, speed_mps=100.0,
                                  release_time_s=1.0, delay_s=1.0,
                                  valid=False, status="invalid",
                                  total_duration_s=0.0,
                                  sample_level="coarse", scan_step_s=0.05,
                                  evaluator_kind="real"),
            SearchEvaluationRow(candidate_index=1, stage="coarse", seed=2025,
                                  heading_rad=0.0, speed_mps=100.0,
                                  release_time_s=1.0, delay_s=1.0,
                                  valid=True, status="ok",
                                  total_duration_s=2.0,
                                  sample_level="coarse", scan_step_s=0.05,
                                  evaluator_kind="real"),
        ]
        ranked = rank_top_k(rows, 5)
        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0].candidate_index, 1)


# =============================================================================
#  I — Checkpoint v2
# =============================================================================
class ICheckpointV2(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="q2_search_ckpt_v2_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_i01_roundtrip(self):
        ck = CheckpointV2(
            schema=CHECKPOINT_SCHEMA_V2, algorithm_version="v1",
            seed=2025, domain_hash="abc", manifest_sha256="def",
            evaluator_kind="real", code_revision="x",
            stage="coarse", sample_level="coarse", scan_step_s=0.05,
            completed_indexes=[0, 1],
            best_index=1, best_total=1.5,
            status_counts={"ok": 2},
        )
        path = os.path.join(self.tmpdir, "ck.json")
        save_checkpoint_v2(ck, path)
        loaded = load_checkpoint_v2(path)
        self.assertEqual(loaded.schema, CHECKPOINT_SCHEMA_V2)
        self.assertEqual(loaded.seed, 2025)
        self.assertEqual(loaded.completed_indexes, [0, 1])

    def test_i02_schema_mismatch_rejected(self):
        d = {"schema": 999, "algorithm_version": "v1", "seed": 2025,
             "domain_hash": "x", "manifest_sha256": "y", "evaluator_kind": "real",
             "code_revision": "z", "stage": "coarse", "sample_level": "coarse",
             "scan_step_s": 0.05}
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
            schema=CHECKPOINT_SCHEMA_V2, algorithm_version="v1",
            seed=2025, domain_hash=_hash_domain(desc),
            manifest_sha256="abc", evaluator_kind="real",
            code_revision="rev", stage="coarse", sample_level="coarse",
            scan_step_s=0.05,
        )
        # 不应抛
        verify_resume_identity(
            ck,
            expected_seed=2025, expected_domain=desc,
            expected_manifest_sha="abc", expected_evaluator_kind="real",
            expected_stage="coarse", expected_sample_level="coarse",
            expected_scan_step=0.05, expected_code_revision="rev",
        )

    def test_i04_verify_resume_identity_mismatch(self):
        d = build_search_domain(TEST_U0, TEST_G)
        d["release_time_s"]["max"] = TEST_T_ARRIVAL - 1
        desc = q_space_descriptor(d)
        ck = CheckpointV2(
            schema=CHECKPOINT_SCHEMA_V2, algorithm_version="v1",
            seed=2025, domain_hash=_hash_domain(desc),
            manifest_sha256="abc", evaluator_kind="real",
            code_revision="rev", stage="coarse", sample_level="coarse",
            scan_step_s=0.05,
        )
        with self.assertRaises(ValueError):
            verify_resume_identity(
                ck,
                expected_seed=9999,  # mismatch
                expected_domain=desc, expected_manifest_sha="abc",
                expected_evaluator_kind="real",
                expected_stage="coarse", expected_sample_level="coarse",
                expected_scan_step=0.05, expected_code_revision="rev",
            )

    def test_i05_atomic_write_no_leftover(self):
        ck = CheckpointV2(
            schema=CHECKPOINT_SCHEMA_V2, algorithm_version="v1",
            seed=2025, domain_hash="x", manifest_sha256="y",
            evaluator_kind="real", code_revision="z",
            stage="coarse", sample_level="coarse", scan_step_s=0.05,
        )
        path = os.path.join(self.tmpdir, "ck.json")
        save_checkpoint_v2(ck, path)
        leftovers = [f for f in os.listdir(self.tmpdir) if f.startswith(".ckpt_")]
        self.assertEqual(leftovers, [])


# =============================================================================
#  J — Pipeline coarse → medium → local → fine (small dry-run)
# =============================================================================
class JPipeline(unittest.TestCase):

    def test_j01_pipeline_stages(self):
        # 小规模 pilot 验证各阶段都被执行; 输出到 tmpdir
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
                    "fine_final_count": 1,
                },
                output_dir=out_dir,
            )
            # global_coarse_count=4 + anchor (1) = 5 coarse
            # + 2 medium re-evaluation
            # + 4 local (dedup top)
            # + 1 fine = 12 rows
            self.assertEqual(out["n_total_rows"], 12)
            self.assertEqual(out["status_counts"]["ok"]
                             + out["status_counts"]["invalid"]
                             + out["status_counts"]["pruned_zero"]
                             + out["status_counts"]["zero_window"]
                             + out["status_counts"]["system_error"],
                             12)
            # manifest_sha256 一致
            self.assertEqual(len(out["manifest_sha256"]), 64)
            # output 已写入
            self.assertTrue(os.path.isfile(os.path.join(out_dir, "pilot_result.json")))
        finally:
            shutil.rmtree(out_dir, ignore_errors=True)

    def test_j02_q1_anchor_appears_in_coarse(self):
        # Q1 anchor 出现在 coarse 阶段且 status=ok & total > 0
        out_dir = tempfile.mkdtemp(prefix="q2_pipeline_anchor_")
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
                    "fine_final_count": 1,
                },
                output_dir=out_dir,
            )
            anchor_found = False
            for r in out["all_rows"]:
                if (abs(r["heading_rad"] - Q1_ANCHOR_HEADING) < 1e-9
                    and abs(r["speed_mps"] - Q1_ANCHOR_SPEED) < 1e-9
                    and abs(r["release_time_s"] - Q1_ANCHOR_RELEASE) < 1e-9
                    and abs(r["delay_s"] - Q1_ANCHOR_DELAY) < 1e-9):
                    anchor_found = True
                    self.assertEqual(r["status"], "ok",
                                      f"Q1 anchor 应 status=ok, 实际 {r['status']}")
                    self.assertGreater(r["total_duration_s"], 0.0)
            self.assertTrue(anchor_found, "Q1 anchor 未出现在 coarse 候选池")
        finally:
            shutil.rmtree(out_dir, ignore_errors=True)


# =============================================================================
#  K — CLI
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

    def test_k04_help_returns_zero(self):
        # argparse --help 走 SystemExit; 我们捕获并断言 code 0
        try:
            qs_main(["--help"])
        except SystemExit as e:
            self.assertEqual(e.code, 0)
        else:
            # 若 main 重新捕获 SystemExit, 这里正常返回 0
            pass


# =============================================================================
#  L — No result files / no Q1 regression
# =============================================================================
class LNoSideEffects(unittest.TestCase):

    def test_l01_no_result_xlsx_created(self):
        # 显式断言 work/q2_search 之外不得存在 result*.xlsx
        # 本仓库根目录无 outputs/submission/result*.xlsx
        out_dir = "outputs/submission"
        if os.path.isdir(out_dir):
            xs = [f for f in os.listdir(out_dir)
                  if f.startswith("result") and f.endswith(".xlsx")]
            self.assertEqual(xs, [],
                              f"不得在 outputs/submission/ 写入 result*, 实际 {xs}")

    def test_l02_q1_baseline_numerical_unchanged(self):
        # 通过 evaluate_with_real_evaluator 验证 Q1 anchor 数值仍 ≥ 1.0
        row = evaluate_with_real_evaluator(
            Q1_ANCHOR_VEC, sample_level="coarse",
            scan_step=0.05, seed=2025,
        )
        self.assertGreater(row.total_duration_s, 1.0)
        self.assertLess(row.total_duration_s, 1.6)


# =============================================================================
#  M — Fake evaluator (test/dry-run only)
# =============================================================================
class MFakeEvaluator(unittest.TestCase):

    def test_m01_fake_returns_ok(self):
        row = evaluate_with_fake_evaluator(
            (math.pi, 120.0, 5.0, 4.0),
            sample_level="coarse", scan_step=0.05, seed=2025,
        )
        self.assertEqual(row.evaluator_kind, "fake")
        self.assertEqual(row.status, "ok")
        self.assertGreater(row.total_duration_s, 0.0)

    def test_m02_fake_deterministic(self):
        a = evaluate_with_fake_evaluator(
            (1.234, 95.0, 2.5, 0.5),
            sample_level="coarse", scan_step=0.05, seed=2025,
        )
        b = evaluate_with_fake_evaluator(
            (1.234, 95.0, 2.5, 0.5),
            sample_level="coarse", scan_step=0.05, seed=2025,
        )
        self.assertEqual(a.total_duration_s, b.total_duration_s)


if __name__ == "__main__":
    unittest.main(verbosity=2)
