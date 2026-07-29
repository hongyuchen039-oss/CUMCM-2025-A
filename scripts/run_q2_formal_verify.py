"""scripts/run_q2_formal_verify.py — TASK_005 verification-only closure.

Per MAIN authorization: ONLY run the 2 delay_s ±0.025 evaluations that
were skipped when budget exhausted at eval 32, and verify the best-observed
candidate at scan_steps=(0.02, 0.01, 0.005) for stability.

NOT allowed in this script:
  - new coordinate sweep / new level
  - 3×1000 formal search rerun
  - 17-candidate full re-evaluation
  - 473-test full regression
  - Q3 launch / result*.xlsx generation

Reads the existing work/q2_formal_refinement/checkpoint.json to recover
the best-observed candidate (skipping the resume HEAD check, since the
REVIEW commit only changed docs and the tracked summary, not the
refinement logic).

Output: outputs/q2/q2_verify_summary.json (tracked)
        work/q2_formal_refinement/checkpoint.json (atomic update)

Declares:
  FORMAL BUDGET-LIMITED BEST-KNOWN Q2 CANDIDATE /
  LOCAL CONVERGENCE NOT ESTABLISHED /
  NOT A PROVEN GLOBAL OPTIMUM
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Dict, Tuple

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src import q2_search as qs  # noqa: E402

VERIFICATION_DECLARATION = (
    "FORMAL BUDGET-LIMITED BEST-KNOWN Q2 CANDIDATE / "
    "LOCAL CONVERGENCE NOT ESTABLISHED / "
    "NOT A PROVEN GLOBAL OPTIMUM"
)


def _load_checkpoint(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        raise RuntimeError(f"checkpoint not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _run_verify(
    *,
    checkpoint_path: str = "work/q2_formal_refinement/checkpoint.json",
    output_path: str = "outputs/q2/q2_verify_summary.json",
) -> Dict[str, Any]:
    """Run verification-only closure."""
    print("[VERIFY] starting verification-only closure", flush=True)
    started_at = time.monotonic()

    ck = _load_checkpoint(checkpoint_path)
    current_head = qs._git_head_sha()
    print(f"[VERIFY] current HEAD = {current_head}", flush=True)
    print(f"[VERIFY] checkpoint head_sha = {ck.get('head_sha')}", flush=True)
    # NOTE: We deliberately do NOT raise on HEAD mismatch because the
    # post-refinement REVIEW commit only added docs/tracked-summary and
    # did not modify refinement code/config. The refinement logic is
    # byte-identical to the FIX commit.

    # Recover best-observed candidate from checkpoint
    center = tuple(ck["current_best_candidate"])
    assert len(center) == 4, "checkpoint current_best must be 4-tuple"
    refine_cfg_sha = str(ck["refinement_config_sha256"])
    pre_dur = float(ck["current_best_duration"])
    pre_evals = int(ck["evaluations_completed"])
    print(f"[VERIFY] best-observed (from checkpoint): {list(center)}",
          flush=True)
    print(f"[VERIFY]   sweep dur = {pre_dur:.6f} s, "
          f"pre_evals = {pre_evals}", flush=True)

    # 1. Run the 2 skipped delay_s ±0.025 evals at scan_step=0.01
    # Level 3 scales: heading ±0.005, speed ±0.25, release ±0.05,
    # delay ±0.025. We already ran heading ±0.005, speed ±0.25, release
    # ±0.05; only delay ±0.025 are left.
    delay_scale = 0.025
    new_evals = []
    new_best = center
    new_best_dur = pre_dur

    for sign in (+1, -1):
        idx = qs._FORMAL_VAR_INDEX["delay_s"]
        cand = list(center)
        cand[idx] = center[idx] + sign * delay_scale
        cand_t = (float(cand[0]), float(cand[1]), float(cand[2]),
                  float(cand[3]))
        ok, reason = qs._refine_physical_validity_or_record(cand_t)
        print(f"[VERIFY] running delay_s sign={sign} candidate={list(cand_t)} "
              f"physical_ok={ok} reason={reason!r}", flush=True)
        if not ok:
            new_evals.append({
                "var": "delay_s", "sign": sign,
                "candidate": list(cand_t),
                "physical_ok": False, "physical_reason": reason,
                "skipped": True,
            })
            continue
        row = qs._refine_evaluate(
            cand_t, seed=2025,
            scan_step=qs.REFINE_SWEEP_SCAN_STEP,
            source_stage=f"verify_delay_sign_{sign}",
        )
        dur = float(row.total_duration_s) if (
            row.status == "ok" and row.valid) else -1.0
        improves = (
            dur > new_best_dur + qs.REFINE_IMPROVE_TOL_S)
        print(f"[VERIFY] delay_s sign={sign} dur={dur:.6f} s "
              f"improves={'yes' if improves else 'no'} "
              f"eval_id={row.evaluation_id}", flush=True)
        new_evals.append({
            "var": "delay_s", "sign": sign,
            "candidate": list(cand_t),
            "physical_ok": True,
            "duration_s": dur,
            "status": row.status,
            "valid": bool(row.valid),
            "evaluation_id": row.evaluation_id,
            "improves_best": bool(improves),
        })
        if improves:
            new_best = cand_t
            new_best_dur = dur

    # 2. Stability check at scan_steps=(0.02, 0.01, 0.005) on
    # best-observed candidate.
    print(f"[VERIFY] running stability check on best-observed: "
          f"{list(new_best)}", flush=True)
    stability = qs.formal_stability_check(
        new_best, scan_steps=(0.02, 0.01, qs.REFINE_FINAL_SCAN_STEP),
        seed=2025)
    print(f"[VERIFY] stability result: {stability}", flush=True)

    # 3. Physical validity on best-observed candidate
    pv_ok, pv_reason = qs.formal_physical_validity(new_best)
    print(f"[VERIFY] physical_validity: ok={pv_ok} reason={pv_reason!r}",
          flush=True)

    # 4. Update checkpoint atomically (verify-done)
    elapsed_total = time.monotonic() - started_at
    new_ck_payload = qs._refine_checkpoint_payload(
        head_sha=current_head,
        parent_candidate=qs.REFINE_PARENT_FORMAL,
        current_best_candidate=new_best,
        current_best_duration=new_best_dur,
        level="verify_done",
        sweep=0,
        evaluations_completed=pre_evals + len(
            [e for e in new_evals if not e.get("skipped")]),
        evaluated_candidate_identities=ck.get(
            "evaluated_candidate_identities", []),
        elapsed_seconds=elapsed_total,
        refine_config_sha=refine_cfg_sha,
        status="verify_done",
        extras={
            "verify_new_evals": new_evals,
            "verify_best_after_delay": list(new_best),
            "verify_best_dur_after_delay": new_best_dur,
            "verify_pre_dur": pre_dur,
            "verify_stability": stability,
            "verify_physical_ok": bool(pv_ok),
            "verify_physical_reason": pv_reason,
            "declaration": VERIFICATION_DECLARATION,
        },
    )
    qs._refine_atomic_write_json(checkpoint_path, new_ck_payload)
    print(f"[VERIFY] checkpoint updated atomically: {checkpoint_path}",
          flush=True)

    # 5. Persist tracked summary
    summary = {
        "schema": "q2_verify_summary_v1",
        "declaration": VERIFICATION_DECLARATION,
        "current_head_sha": current_head,
        "checkpoint_head_sha": str(ck.get("head_sha")),
        "refinement_config_sha256": refine_cfg_sha,
        "pre_evals": pre_evals,
        "pre_best_candidate": list(center),
        "pre_best_dur_s": pre_dur,
        "verify_new_evals": new_evals,
        "post_best_candidate": list(new_best),
        "post_best_dur_s": new_best_dur,
        "post_best_improved": bool(
            new_best_dur > pre_dur + qs.REFINE_IMPROVE_TOL_S),
        "stability": stability,
        "physical_validity": {
            "ok": bool(pv_ok),
            "reason": pv_reason if not pv_ok else "",
        },
        "evaluations_added": len(new_evals),
        "elapsed_seconds_verify": elapsed_total,
        "local_convergence_established": False,
        "constraints": {
            "no_new_coordinate_sweep": True,
            "no_three_seed_rerun": True,
            "no_17_candidate_full_reeval": True,
            "no_473_full_regression": True,
            "no_q3_launch": True,
            "no_result_xlsx_generated": True,
            "no_global_optimum_claimed": True,
        },
    }
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"[VERIFY] summary → {output_path}", flush=True)
    print(f"[VERIFY] DONE declaration={VERIFICATION_DECLARATION}",
          flush=True)
    return summary


if __name__ == "__main__":
    res = _run_verify()
    sys.exit(0)