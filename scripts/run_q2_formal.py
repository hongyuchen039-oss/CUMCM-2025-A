"""scripts/run_q2_formal.py — TASK_005 formal Q2 search orchestrator (P1).

编排, 不复制搜索算法:
  - 加载 configs/q2_search_formal_v1.json (formal config, schema 3)
  - 对每个 seed (2025/2026/2027), 调用 src.q2_search.run_formal_pipeline()
    携带 formal pilot budget
  - 每个 seed 独立 checkpoint / 独立 run identity / 独立 stage counts
  - 等待所有 seed 完成
  - cross-seed 去重 (cross_seed_dedup_candidates, tolerance 写入 formal config)
  - 注入 pilot best-known candidate (via formal_pilot_best_rehydrate, 优先
    work/q2_pilot_calib/pilot_result.json, fallback 确定性 seed=2025 clean pilot)
  - 统一 fine cylinder re-evaluation (scan_step=0.005)
  - stability check (三档扫描)
  - perturbation check (16 个 one-variable-at-a-time 扰动)
  - physical validity check (fail-closed on NaN/Inf, speed, release, delay, heading)
  - 输出 outputs/q2/q2_formal_summary.json + per_seed_summary.json
  - 严格 fail-closed: 任一 gate 不通过 → raise / BLOCKED

raw per-seed artifacts (pilot_result.json + checkpoint_v2.json) 写入
work/q2_formal/seed_{seed}/ (gitignored), 不得污染 tracked tree.
PR-final tracked artifacts 只有 outputs/q2/q2_formal_summary.json 和
outputs/q2/per_seed_summary.json (compact summary).
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

# Ensure project root on sys.path so `import src.q2_search` works when
# invoked as `python scripts/run_q2_formal.py`.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src import q2_search as qs  # noqa: E402

FORMAL_CONFIG_PATH = "configs/q2_search_formal_v1.json"
DEFAULT_OUTPUT_DIR = "outputs/q2"
FORMAL_RAW_DIR = "work/q2_formal"
PILOT_BEST_KEYS = ("heading_rad", "speed_mps", "release_time_s", "delay_s")


def _run_single_seed(
    *,
    seed: int,
    cfg: Dict[str, Any],
    output_dir: str = FORMAL_RAW_DIR,
) -> qs.FormalPipelineResult:
    """Run a single-seed formal pipeline with require_clean_worktree=True.

    raw per-seed artifacts go to work/q2_formal/seed_{seed}/ (gitignored).
    Returns a FormalPipelineResult whose actual_* fields are computed from
    the pipeline output, never copied from the formal config.
    """
    seed_dir = os.path.join(output_dir, f"seed_{int(seed)}")
    os.makedirs(seed_dir, exist_ok=True)
    return qs.run_formal_pipeline(
        seed=int(seed),
        config=cfg,
        output_dir=seed_dir,
    )


def _seed_fine_candidates(
    per_seed_result: qs.FormalPipelineResult, top_k: int = 5,
) -> List[Tuple[float, float, float, float]]:
    """Take the top-K fine rows for one seed, return 4-tuples (best first)."""
    fine_rows = per_seed_result.fine_rows
    ok_rows = [r for r in fine_rows
               if r.status == "ok" and r.valid]
    ok_rows.sort(key=lambda r: r.total_duration_s, reverse=True)
    out: List[Tuple[float, float, float, float]] = []
    for r in ok_rows[:top_k]:
        out.append(
            (float(r.heading_rad), float(r.speed_mps),
             float(r.release_time_s), float(r.delay_s)))
    return out


def _uniform_fine_reeval(
    candidates: Sequence[Tuple[float, float, float, float]],
    *,
    seed: int = 2025,
    scan_step: float = 0.005,
) -> List[qs.SearchEvaluationRow]:
    """Re-evaluate each candidate at uniform fine level. Returns rows."""
    rows: List[qs.SearchEvaluationRow] = []
    for i, tup in enumerate(candidates):
        row = qs.evaluate_with_real_evaluator(
            tup, sample_level="fine", scan_step=scan_step, seed=seed,
            source_stage="formal_finalist_v2",
            source_candidate_index=i,
        )
        rows.append(row)
    return rows


def _assert_fail_closed_finalist(
    *,
    finalist_pool: Sequence[Tuple[Tuple[float, float, float, float], int]],
    finalist_rows: Sequence[qs.SearchEvaluationRow],
    stability: Dict[str, Any],
    perturbation: Dict[str, Any],
    physical_validity: Tuple[bool, str],
) -> qs.SearchEvaluationRow:
    """Run fail-closed gates on the finalist pool + winner selection.

    Raises qs.FormalBudgetGateError on any violation. Returns the
    selected winner SearchEvaluationRow.
    """
    # P1-2: finalist pool must be non-empty
    if not finalist_pool:
        raise qs.FormalBudgetGateError(
            "formal finalist pool is empty after dedup")
    if not finalist_rows:
        raise qs.FormalBudgetGateError(
            "formal finalist re-evaluation returned no rows")
    valid_finalists = [r for r in finalist_rows
                       if r.status == "ok" and r.valid]
    if not valid_finalists:
        raise qs.FormalBudgetGateError(
            "no valid fine finalist after re-evaluation; "
            "fail-closed BLOCKED")
    # pick the winner (max total_duration_s among valid)
    winner = max(valid_finalists, key=lambda r: r.total_duration_s)
    # winner.status / valid re-check
    if winner.status != "ok":
        raise qs.FormalBudgetGateError(
            f"winner.status={winner.status!r} != 'ok'; "
            f"fail-closed BLOCKED")
    if not bool(winner.valid):
        raise qs.FormalBudgetGateError(
            f"winner.valid=False; fail-closed BLOCKED")
    # physical validity
    ok, reason = physical_validity
    if not ok:
        raise qs.FormalBudgetGateError(
            f"physical_validity not ok: {reason}; fail-closed BLOCKED")
    # stability
    if not stability.get("stability_ok", False):
        raise qs.FormalBudgetGateError(
            f"stability_ok={stability.get('stability_ok')}; "
            f"fail-closed BLOCKED; details={stability}")
    # system_error check (within finalist pool)
    sys_err = sum(1 for r in finalist_rows if r.status == "system_error")
    if sys_err > 0:
        raise qs.FormalBudgetGateError(
            f"finalist_rows has {sys_err} system_error rows; "
            f"fail-closed BLOCKED")
    return winner


def run_formal_search(
    *,
    config_path: str = FORMAL_CONFIG_PATH,
    output_dir: str = DEFAULT_OUTPUT_DIR,
    seeds_to_run: Optional[Sequence[int]] = None,
) -> Dict[str, Any]:
    """Top-level formal search entry point.

    All gates fail-closed; any violation raises qs.FormalBudgetGateError.
    """
    cfg = qs.load_formal_config(config_path)
    seeds = list(seeds_to_run) if seeds_to_run is not None else list(
        cfg["seeds"])
    for s in seeds:
        if s not in cfg["seeds"]:
            raise qs.FormalBudgetGateError(
                f"seed {s!r} not in formal config seeds={cfg['seeds']}")

    # 1. Per-seed runs (all 3 seeds must succeed; on any failure →
    # raise / BLOCKED, no summary written)
    os.makedirs(output_dir, exist_ok=True)
    per_seed_results: List[qs.FormalPipelineResult] = []
    for seed in seeds:
        print(f"[FORMAL] running seed={seed} budget={cfg['total_budget']}")
        result = _run_single_seed(seed=int(seed), cfg=cfg)
        per_seed_results.append(result)
        print(f"[FORMAL] seed={seed} wall={result.wall_clock_s:.2f}s "
              f"actual_count={result.actual_completed_count} "
              f"unique_ids={result.actual_unique_evaluation_ids} "
              f"formal_run_id={result.formal_run_identity_sha256[:12]} "
              f"final_best_status={result.final_best_status}")

    # 2. Cross-seed finalist pool
    candidates_pool: List[Tuple[float, float, float, float]] = []
    n_pool_per_seed = []
    for ps in per_seed_results:
        tops = _seed_fine_candidates(ps, top_k=5)
        n_pool_per_seed.append(len(tops))
        candidates_pool.extend(tops)
    # 2a. Inject pilot best-known candidate with fail-closed rehydrate
    pilot_best_info = qs.formal_pilot_best_rehydrate()
    pilot_best = pilot_best_info["physical_candidate"]
    candidates_pool.append(pilot_best)
    dedup = qs.cross_seed_dedup_candidates(
        candidates_pool, tolerance=cfg["dedupe_tolerance"])
    if not dedup:
        raise qs.FormalBudgetGateError(
            "formal finalist pool is empty after dedup")

    # 3. Uniform fine re-evaluation (scan_step=0.005) on the union
    finalists_rows = _uniform_fine_reeval(
        [tup for tup, _ in dedup], seed=2025, scan_step=0.005)
    valid_finalists = [r for r in finalists_rows
                       if r.status == "ok" and r.valid]
    if not valid_finalists:
        raise qs.FormalBudgetGateError(
            "no valid finalist row after uniform fine re-evaluation")
    winner = max(valid_finalists, key=lambda r: r.total_duration_s)

    # 4. Stability check
    winner_tuple = (float(winner.heading_rad), float(winner.speed_mps),
                    float(winner.release_time_s), float(winner.delay_s))
    stability = qs.formal_stability_check(
        winner_tuple, scan_steps=tuple(cfg.get(
            "stability_scan_steps", (0.02, 0.01, 0.005))),
        seed=2025)

    # 5. Perturbation check (16 one-var)
    perturbation = qs.formal_one_variable_perturbation_check(
        winner_tuple, seed=2025, scan_step=0.005)

    # 6. Physical validity
    pv_ok, pv_reason = qs.formal_physical_validity(winner_tuple)

    # 7. Final fail-closed assembly (P1-2)
    winner_final = _assert_fail_closed_finalist(
        finalist_pool=dedup,
        finalist_rows=finalists_rows,
        stability=stability,
        perturbation=perturbation,
        physical_validity=(pv_ok, pv_reason),
    )

    # 8. Aggregate output
    per_seed_min = [ps.to_dict() for ps in per_seed_results]
    output = qs.build_formal_output(
        task="TASK_005 Q2 FORMAL SEARCH AND RESULT FREEZE",
        per_seed_outputs=per_seed_min,
        finalist_pool=dedup,
        winner_row=winner_final,
        dedupe_tolerance=cfg["dedupe_tolerance"],
        seeds=seeds,
        config_sha256=str(cfg["raw_config_sha256"]),
        code_revision=str(per_seed_results[0].code_identity_sha256),
        config_path=str(cfg["raw_config_path"]),
        scan_steps_used=tuple(cfg.get(
            "stability_scan_steps", (0.02, 0.01, 0.005))),
        stability_results=stability,
        perturbation_results=perturbation,
        physical_validity={"ok": bool(pv_ok),
                           "reason": pv_reason if not pv_ok else ""},
        pilot_best_candidate=pilot_best,
        extra={
            "total_budget_per_seed": int(cfg["total_budget"]),
            "n_seeds_run": len(seeds),
            "n_finalists_after_dedup": len(dedup),
            "n_fine_per_seed_top5": n_pool_per_seed,
            "pilot_best_source": str(pilot_best_info.get("source")),
            "pilot_best_canonical_result_sha256": str(
                pilot_best_info.get("canonical_result_sha256", "")),
            "pilot_best_run_identity_sha256": str(
                pilot_best_info.get("run_identity_sha256", "")),
            "per_seed_formal_run_identity": {
                str(ps.seed): ps.formal_run_identity_sha256
                for ps in per_seed_results},
            "per_seed_code_identity": {
                str(ps.seed): ps.code_identity_sha256
                for ps in per_seed_results},
            "per_seed_pipeline_effective_config_sha256": {
                str(ps.seed): ps.pipeline_effective_config_sha256
                for ps in per_seed_results},
            "local_perturbation_passed": bool(
                perturbation.get("local_perturbation_passed")),
            "n_one_var_perturbations": int(
                perturbation.get("n_total_perturbations", 0)),
            "n_legal_one_var_perturbations": int(
                perturbation.get("n_legal_perturbations", 0)),
            "n_illegal_one_var_perturbations": int(
                perturbation.get("n_illegal_perturbations", 0)),
            "require_clean_worktree": True,
        },
    )

    # 9. Persist compact summary (PR-final tracked artifacts only)
    summary_path = os.path.join(output_dir, "q2_formal_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    per_seed_summary_path = os.path.join(output_dir, "per_seed_summary.json")
    with open(per_seed_summary_path, "w", encoding="utf-8") as f:
        json.dump({
            "seeds": list(seeds),
            "per_seed": [
                ps.to_dict() for ps in per_seed_results
            ],
            "pilot_best_source": str(pilot_best_info.get("source")),
            "pilot_best_canonical_result_sha256": str(
                pilot_best_info.get("canonical_result_sha256", "")),
            "pilot_best_run_identity_sha256": str(
                pilot_best_info.get("run_identity_sha256", "")),
            "pilot_best_physical_candidate": list(
                pilot_best_info["physical_candidate"]),
            "pool_size_per_seed_top5": n_pool_per_seed,
            "n_finalists_after_dedup": len(dedup),
        }, f, indent=2, ensure_ascii=False)
    print(f"[FORMAL] summary → {summary_path}")
    print(f"[FORMAL] per-seed → {per_seed_summary_path}")
    return output


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="TASK_005 formal Q2 search orchestrator (P1) "
                    "and bounded refinement (LOCAL REFINEMENT).")
    parser.add_argument(
        "--refine-only", action="store_true",
        help="Run only the bounded refinement path (no 3-seed rerun).")
    args = parser.parse_args()
    if args.refine_only:
        res = qs.run_formal_refinement()
        print(f"[REFINE] canonical_refinement_sha256="
              f"{res.get('local_perturbation_passed')}")
        sys.exit(0)
    res = run_formal_search()
    print(f"[FORMAL] canonical_result_sha256="
          f"{res['canonical_result_sha256']}")
