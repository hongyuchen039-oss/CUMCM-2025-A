# TASK_004 Foundation Audit Handoff

> Purpose: provide MAIN and Hermes with a durable, auditable summary of the Foundation review history without copying private platform internals or hidden reasoning.
>
> Scope: TASK_004 Foundation only. This document does not approve Search, does not report a Q2 optimum, and does not replace repository artifacts, tests, commit diffs, or independent verification.

## 1. Project identity

- Repository: `hongyuchen039-oss/CUMCM-2025-A`
- Foundation branch: `task/TASK_004-foundation`
- Foundation PR: `#5`
- Local main worktree used by the project: `C:\Users\33560\Desktop\CUMCM_2025_A`
- Local read-only audit worktree used by the project: `C:\Users\33560\Desktop\CUMCM_2025_A_AUDIT`

## 2. Roles used in the workflow

- **MAIN**: owns task routing, merge decisions, and stage transitions.
- **Main CC / Claude Code**: performs local engineering work and returns command evidence.
- **Audit CC**: performs read-only contract review, risk classification, and gate decisions.
- **Search CC**: may design or implement Search only after Foundation approval and explicit authorization.
- **Hermes**: performs final independent verification before MAIN acts on the merge decision.

No role may infer a successful local run or a clean worktree without evidence from the relevant environment.

## 3. High-level task history

### TASK_001 — official problem intake

- Official facts, coordinate conventions, and result-template fields were extracted and reviewed.
- PR `#1` was merged.

### TASK_002 — Q1 point-target baseline

- Point-target baseline and its test suite were implemented.
- PR `#2` was merged.

### TASK_003 — full-cylinder candidate

- Full-cylinder strict occlusion candidate, spatial/temporal convergence checks, and Q1 comparison were implemented.
- PR `#3` was merged.
- The model remains labeled `FULL-CYLINDER CANDIDATE / EXPERIMENTAL`, not `VERIFIED` or `FINAL`.

### TASK_INFRA_001 — CI

- GitHub Actions workflow was introduced.
- PR `#4` was merged.
- For the final Foundation decision, the user explicitly froze the policy that CI timeout/cancellation is not a P0/P1 blocker unless there is concrete evidence of assertion failure, mathematical error, or code-contract failure.

### TASK_004 — Q2 single-bomb Foundation

The Foundation provides:

- the four independent strategy variables;
- physical and contract validation;
- derived release/detonation geometry;
- strict full-cylinder single-candidate evaluation;
- explicit statuses and program-error separation;
- coarse/medium/fine profiles;
- smoke and profile-measurement entry points;
- regression coverage against Q1 contracts.

It remains `NOT AN OPTIMIZATION RESULT`.

## 4. Foundation commit chain reviewed

The final PR `#5` chain includes, among earlier Foundation commits, the following two final commits:

### `6fe47ba1e3c0d744b8d0165b774ba1ba8eea4d90`

`FIX: close Foundation exit semantics and CI debt`

Relevant Foundation behavior changes:

- `main --profile-measure` returns `1` when any row contains a warm-up program error;
- formal repeat program errors continue to return `1`;
- parameter errors remain `2`;
- normal profile measurement remains `0`;
- warm-up errors and formal repeat errors remain stored in separate fields;
- three R2 tests were added for the final exit-code contract.

The commit also modified the workflow, but workflow state is not a Foundation P0/P1 merge blocker under the final user policy.

### `1d39c790b1171d32ac11fe8e00248e22ac795e7f`

`DOCS: restore modeling-first Foundation close`

This commit was verified to modify only:

- `MODEL.md`
- `NEXT_TASK.md`
- `START_HERE.md`

It did not modify source code, tests, Q1 mathematics, workflow, Search code, outputs, or result spreadsheets.

## 5. Final verified GitHub artifact

The final read-only review verified that PR `#5` had:

- state: open;
- draft: true;
- merged: false;
- branch: `task/TASK_004-foundation`;
- head SHA: `1d39c790b1171d32ac11fe8e00248e22ac795e7f`.

The review was required to stop immediately if the head differed. It matched exactly.

## 6. Frozen P0/P1 acceptance rubric

Only the following items were treated as Foundation P0/P1 for final acceptance:

1. warm-up-only program error must produce CLI exit `1`;
2. formal repeat program error must produce CLI exit `1`;
3. parameter error must remain CLI exit `2`;
4. normal path must remain CLI exit `0`;
5. remaining cells must continue after a cell reports an error;
6. Q1 mathematical core must not be modified;
7. real tests must not be deleted or weakened;
8. the reported complete local regression must be real and internally consistent with code/test changes;
9. formal Search must not have started;
10. `result*.xlsx` must not have been generated.

CI timeout, workflow presentation, and ordinary documentation formatting were frozen as P2/P3 unless tied to concrete correctness evidence.

## 7. Final program-behavior contract

### Profile-measurement exit codes

| Condition | CLI exit code |
|---|---:|
| All rows have `warm_up_error is None` and `n_system_error == 0` | `0` |
| Any row has a warm-up program error | `1` |
| Any row has a formal repeat program error | `1` |
| Warm-up and repeat errors both occur | `1` |
| Argument/type/range/mutual-exclusion error | `2` |

### Error-field separation

- `warm_up_error` records warm-up failures.
- Warm-up failures do **not** increment `n_system_error`.
- `n_system_error` and `system_errors` record formal repeat failures.
- Both error classes influence the final CLI result, but their data semantics remain separate.

### Continuation behavior

- A warm-up failure does not prevent formal repeats from being attempted.
- A repeat failure does not terminate later repeats.
- A single failing profile cell does not terminate the other cells.
- The selective single-cell warm-up test verifies that all 9 cells are still processed.

## 8. Test evidence recorded by the Foundation artifact

The PR artifact records the following local results:

- Q2 Foundation: `88/88 OK`;
- full test discovery: `205/205 OK`;
- 100-candidate coarse smoke: `EXIT=0`;
- normal profile-measurement path: `EXIT=0`;
- warm-up-only injected error: `EXIT=1`;
- warm-up plus repeat injected error: `EXIT=1`;
- repeat-only injected error: `EXIT=1`;
- argument error: `EXIT=2`.

The final Audit CC did not rerun these tests because the user restricted the review to the real GitHub artifact. Static review found no contradiction between the reported counts and the code/test delta:

- prior Q2 suite: 85 tests;
- added final R2 tests: 3;
- final Q2 suite: 88;
- prior full suite: 202;
- final full suite: 205.

## 9. Q1 mathematical freeze

The final two commits did not modify:

- `src/q1_baseline.py`;
- `src/q1_cylinder.py`;
- `tests/test_q1_baseline.py`;
- `tests/test_q1_cylinder.py`.

Therefore the final Foundation close did not alter:

- Q1 point-target kinematics;
- full-cylinder strict boundary geometry;
- Q1 sampling grades;
- Q1 convergence algorithms;
- existing Q1 numerical results.

## 10. Scope boundaries verified

At Foundation acceptance:

- no formal Q2 Search run was accepted;
- no Q2 optimum was reported;
- no Search PR existed as an accepted stage artifact;
- no transition to Q3 was approved;
- no global-optimum claim was permitted;
- no `result1.xlsx`, `result2.xlsx`, or `result3.xlsx` was generated by Foundation;
- Q2 remained a single-candidate Foundation evaluator.

## 11. Search prototype status

`NEXT_TASK.md` registers a remote, unreviewed Search prototype commit:

`6f728d45b3bb776c19bbe8a857b26570eb79dc68`

Its frozen status is:

- retained but not accepted;
- no accepted Search PR;
- not a formal Search run;
- not a Q2 numerical result;
- must be audited only after Foundation merge and explicit stage authorization.

MAIN must not treat the existence of this commit as Search approval.

## 12. Final Audit CC decision

The final read-only review found:

- P0: none;
- P1: none;
- P2: one non-blocking documentation inconsistency;
- P3: legacy debt labels remaining in code/test comments, non-behavioral.

Final decision:

> **FOUNDATION ACCEPTED**  
> **— READY FOR HERMES FINAL VERIFICATION**

This decision authorized Hermes verification and MAIN's merge decision. It did not authorize Audit CC to merge, mark Ready, modify the PR, or start Search.

## 13. Non-blocking residual issue

A legacy section in `MODEL.md` still listed `CI sustained PASS` as a Search-entry condition, while the final modeling-first documents and user policy state that the Foundation merge does not wait for CI and CI timeout is not a mathematical failure.

Classification:

- P2 documentation consistency;
- not a Foundation merge blocker;
- must not be retroactively promoted to P1 without concrete correctness evidence.

## 14. Instructions to MAIN

MAIN should use this handoff as an index, not as a substitute for GitHub evidence.

Recommended reading order:

1. PR `#5` metadata and head SHA;
2. commit `6fe47ba1e3c0d744b8d0165b774ba1ba8eea4d90` diff;
3. commit `1d39c790b1171d32ac11fe8e00248e22ac795e7f` diff;
4. `src/q2_single_bomb.py` profile-measurement return logic;
5. `tests/test_q2_single_bomb.py` R2 tests;
6. `MODEL.md`, `NEXT_TASK.md`, and `START_HERE.md`;
7. this handoff's final decision and scope boundaries.

MAIN may proceed to Hermes final verification. After Hermes verification, MAIN owns the explicit decision to merge or reject PR `#5`.

MAIN must not:

- infer CI PASS;
- treat a timeout/cancelled run as a mathematical failure without concrete evidence;
- accept the Search prototype before its own audit stage;
- generate result spreadsheets during Foundation;
- claim a Q2 optimum or global optimum from Foundation evidence.

## 15. Provenance and privacy limitations

This is a structured audit handoff, not a byte-for-byte export of the ChatGPT UI conversation.

Included:

- user-approved project facts;
- public repository identifiers;
- commit and PR identifiers;
- review decisions;
- test evidence reported in project artifacts;
- acceptance boundaries and next actions.

Not included:

- hidden chain-of-thought;
- system or developer instructions;
- platform-internal metadata;
- credentials or private tokens;
- unrelated personal conversation history.

Repository artifacts and independently reproducible evidence remain the source of truth.
