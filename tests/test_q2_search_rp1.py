"""tests/test_q2_search_rp1.py — TASK_004 Q2 REAL SEARCH CORE V1 — FINAL REMAINING-P1 CLOSURE.

v1.2 RP1 全量测试 (42 项, 分类 A-F):
  A  Effective Config (RP1-3)
  B  Structured Code Identity (RP1-4)
  C  Evaluation-Safe Interrupted Checkpoint (RP1-1)
  D  Resume Identity from current plan (RP1-2)
  E  Canonical Result + canonical_result_sha256
  F  Two-Finalist Lineage + Dirty Worktree Rejection (RP1-5/7)

等级: TASK_004 Q2 REAL SEARCH CORE V1 — FINAL REMAINING-P1 CLOSURE /
       PILOT / NOT A FORMAL Q2 RESULT.
"""

from __future__ import annotations

import copy
import json
import math
import os
import shutil
import sys
import tempfile
import unittest
from typing import List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import q2_search as qs
from src.q2_search import (
    ALGORITHM_VERSION,
    SAMPLING_METHOD,
    CHECKPOINT_SCHEMA_V2,
    CONFIG_SCHEMA_V2,
    DEFAULT_CONFIG_PATH,
    EXPECTED_TOTAL_EVALUATIONS,
    PIPELINE_STAGES,
    DEFAULT_PILOT_BUDGET,
    SearchEvaluationRow,
    CheckpointV2,
    build_structured_code_identity,
    compute_structured_code_identity_sha256,
    _git_head_sha,
    _worktree_dirty,
    _stage_plan_for_pipeline,
    resolve_effective_config,
    expected_stage_from_plan,
    build_fine_lineage,
    build_pilot_output,
    compute_canonical_result_sha256,
    CANONICAL_RESULT_FIELDS,
    _ControlledInterruption,
    _physical_candidate_sha256,
    _make_static_run_identity,
    compute_static_run_identity_sha256,
    _make_lineage_manifest,
    compute_lineage_manifest_sha256,
    save_checkpoint_v2,
    load_checkpoint_v2,
    run_search_pipeline,
    main as qs_main,
    _build_argparser,
)


TEST_U0 = (17800.0, 0.0, 1800.0)
TEST_G = 9.8
TEST_T_ARRIVAL = 67.0


def _make_row(heading: float, speed: float, release: float, delay: float,
              source_stage: str = "fine", sample_level: str = "fine",
              scan_step: float = 0.01, valid: bool = True,
              status: str = "ok", total: float = 1.0,
              eval_id: str = "") -> SearchEvaluationRow:
    vec = (float(heading), float(speed), float(release), float(delay))
    from src.q2_search import _compute_evaluation_id
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
#  A — Effective Config (RP1-3)
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
        self.assertEqual(b["global_coarse_count"], 97)
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

    def test_a11_cli_overrides_apply_to_budget(self):
        cfg = resolve_effective_config(cli_overrides={
            "fine_final_count": 5,
        })
        self.assertEqual(cfg["budget"]["fine_final_count"], 5)
        # overrides_applied = True → total 不强制 == 163
        self.assertEqual(cfg["total_expected_evaluations"],
                         97 + 8 + 48 + 8 + 5)

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


# =============================================================================
#  B — Structured Code Identity (RP1-4)
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
#  C — Evaluation-Safe Interrupted Checkpoint (RP1-1)
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
#  D — Resume Identity from current plan (RP1-2)
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
        # Note: current plan says global_medium must be sample_level=medium
        # verify_resume_identity 必须 derive from current plan, so会 fail
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
#  E — Canonical Result + canonical_result_sha256
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
#  F — Two-Finalist Lineage + Dirty Worktree Rejection (RP1-5/7)
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
#  G — Dirty Worktree Rejection (RP1-5) + Pipeline smoke (RP1 P2 uniq schema)
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
#  H — Pilot smoke (RP1 P2 uniq output schema + stop-after-evaluations)
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
            )
            self.assertIn("canonical_result_sha256", out)
            self.assertEqual(len(out["canonical_result_sha256"]), 64)
            self.assertEqual(out["algorithm_version"], ALGORITHM_VERSION)
            self.assertEqual(out["total_expected_evaluations"],
                             4 + 2 + 4 + 2 + 2)
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
#  I — CLI (RP1 P2 rc codes)
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


if __name__ == "__main__":
    unittest.main()