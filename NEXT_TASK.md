# 当前唯一任务

## 任务编号
TASK_005 CLEAN-HEAD VERIFICATION IDENTITY CLOSURE (per MAIN §7
修订) — BUDGET-LIMITED BEST-KNOWN Q2 CANDIDATE / LOCAL CONVERGENCE
NOT ESTABLISHED / NOT A PROVEN GLOBAL OPTIMUM.

## 最终声明

```
declaration = "FORMAL BUDGET-LIMITED BEST-KNOWN Q2 CANDIDATE / "
              "LOCAL CONVERGENCE NOT ESTABLISHED / "
              "NOT A PROVEN GLOBAL OPTIMUM"
```

## 唯一目标
不修改本任务分支；不进入 Q3；不写 result*.xlsx；不声明全局最优；
不扩大 refinement 预算。

把之前 4ca43eb 上的 verification-only closure 升级为
CLEAN-HEAD IDENTITY-BOUND CLOSURE:
- 删除 "deliberately do NOT raise on HEAD mismatch" fail-open 行为；
- 把 verification runner 改为显式 identity 验证
  (worktree clean + HEAD identity + refinement config sha256 +
   parent candidate identity + q2_search code identity +
   checkpoint source head_sha + evaluator_call_count = 5)；
- 在 verification summary 中明确记录 verification_head_sha,
  verification_script_sha256, q2_search_code_identity,
  checkpoint_source_head_sha, checkpoint_identity_validation=true,
  evaluator_call_count=5；
- 仅在干净 committed HEAD 上重跑 5 次 evaluation (2 delay ±0.025
  + 3 stability)，硬墙钟 300s。

## 为什么值得做
原 verification runner (4ca43eb) 在 HEAD 不匹配时静默跳过
"deliberately do NOT raise on HEAD mismatch"，属于 fail-open 行为，
与 MAIN 的 verification-only closure 目标（必须能独立验证
checkpoint 身份）相冲突。升级后：
1. 验证运行前 tracked worktree 必须 clean;
2. 显式记录 verification_head_sha / script sha256 / q2_search
   code identity / checkpoint_source_head_sha；
3. 显式验证 refinement_config_sha256 / parent_candidate /
   evaluations_completed=32 全部匹配；
4. evaluator_call_count 必须正好等于 5。

## Verification 结果 (clean HEAD, 5 evaluator calls)

```
checkpoint_source_head_sha = ac97a38c7564c9d7f2c0793c935eeb27bbd1fa90
checkpoint_identity_validation = True
refinement_config_sha256 = 6f9cb503397996b788d0edfc6491b5a4425dd6e4a784f7ad82f8616acfd65a3d
parent_candidate = (3.121767217560497, 115.43351397802584, 1.7672692031529031, 3.889202402720746)
current_best_candidate = (3.126767217560497, 116.43351397802584, 1.2672692031529031, 3.789202402720746)
current_best_duration = 4.260970878601073
evaluations_completed = 32 (baseline before verify)

delay_s +0.025: candidate=(3.126767, 116.4335, 1.267269, 3.814202),
  physical_ok=True, dur=4.258950, improves_best=False
delay_s -0.025: candidate=(3.126767, 116.4335, 1.267269, 3.764202),
  physical_ok=True, dur=4.140284, improves_best=False
stability (scan_steps=0.02/0.01/0.005): 三档 duration=4.260971 完全一致,
  evaluation_id 三档同 (8557adb752828fef76ac21d48684cd15),
  stability_ok=True, delta_0p01_vs_0p005_s=0.000000
physical_validity: ok=True, reason=""
evaluator_call_count = 5/5
elapsed_seconds_verify < 300s
```

## Best-known candidate (NOT frozen)
```
h=3.126767217560497
s=116.43351397802584
r=1.2672692031529031
d=3.789202402720746
total_duration_s=4.260970878601073  (scan_step=0.005 re-eval)
```

## 严格不冒充
- 不得冒充 VERIFIED / FINAL / 全局最优 / 官方答案.
- 不得冒充 local_perturbation_passed (本轮未跑完整 16 项 one-var).
- 不得冒充 local convergence established (声明 = NOT ESTABLISHED).
- 不得替换 335a1f4d REVIEW 上的 FORMAL BEST-KNOWN Q2 CANDIDATE
  冻结结论.

## Inputs
- work/q2_formal_refinement/checkpoint.json
  (gitignored, 已 restore 到 ac97a38 32-eval post-run state)
- outputs/q2/q2_verify_summary.json (新 tracked, identity-bound)
- work/q2_formal_verification.log (gitignored, tee output)
- scripts/run_q2_formal_verify.py (新, identity-bound orchestrator)

## 允许修改
本轮 (clean-head identity closure):
- scripts/run_q2_formal_verify.py (rewrite with identity binding)
- outputs/q2/q2_verify_summary.json (tracked, identity fields)
- work/q2_formal_refinement/checkpoint.json
  (gitignored, restore + atomic verify-done update)
- work/q2_formal_verification.log (gitignored, tee output)
- START_HERE.md / NEXT_TASK.md / RESULTS.md / MODEL.md / README.md
- work/task_context.json (expected_head 推齐新 FIX/REVIEW commit)
- 1 个 FIX commit (verification runner with identity binding)
  + 1 个 REVIEW commit (refresh clean-head verification evidence)

## 禁止修改
- configs/q2_search_gate_v1.json (pilot 不动)
- src/q1_baseline.py / src/q1_cylinder.py / src/q2_single_bomb.py
- tests/test_q1_baseline.py / tests/test_q1_cylinder.py / tests/test_q2_single_bomb.py
- scripts/verify_task_context.py / tests/test_verify_task_context.py
- problem/ / outputs/submission/ / result*.xlsx
- .github/ / CLAUDE.md / .claude/
- main / Git 历史
- 335a1f4d 上的 FORMAL BEST-KNOWN Q2 CANDIDATE 冻结结论

禁止: 自动合并 / 转 Ready / 写 result*.xlsx / 启动 Q3 / 扩大
refinement 预算 / 跳过 identity 验证 / 改写正式历史.

## 必须执行
1. 1 个 FIX commit (verification runner with identity binding);
2. push 到 task/TASK_005-q2-formal-search + 更新 PR #11 描述;
3. clean HEAD 上 5-evaluator-call verification 重跑
   (≤300s wall-clock);
4. 1 个 REVIEW commit (refresh clean-head verification evidence);
5. push + 更新 PR #11 描述;
6. 报告 final declaration 与 verification 结果;
7. 立即停止 (不自动合并 / 不进入 Q3 / 不启动 Audit CC / Hermes /
   TASK_GOV_002).

## 必须产出
- 1 个 FIX commit + 1 个 REVIEW commit (均推到现有分支和 PR #11);
- outputs/q2/q2_verify_summary.json
  (含 verification_head_sha, verification_script_sha256,
   q2_search_code_identity, checkpoint_source_head_sha,
   checkpoint_identity_validation=true, evaluator_call_count=5);
- work/q2_formal_refification.log (gitignored);
- work/q2_formal_refinement/checkpoint.json (gitignored, identity
  -bound verify-done state);
- 收口报告 (final declaration + identity binding + 5 eval calls +
  stability + 物理合法性 + 不冒充承诺).

## 验收标准
1. outputs/q2/q2_verify_summary.json 已写入, declaration 严格匹配
   "FORMAL BUDGET-LIMITED BEST-KNOWN Q2 CANDIDATE / LOCAL CONVERGENCE
   NOT ESTABLISHED / NOT A PROVEN GLOBAL OPTIMUM";
2. checkpoint_identity_validation=true, checkpoint_source_head_sha
   =ac97a38...;
3. evaluator_call_count=5, evaluation_id 与 strict 5-call signature
   一致;
4. delay_s ±0.025 两项 evaluation 完成, 不改善 best-known;
5. stability 三档 (0.02/0.01/0.005) duration 完全一致,
   stability_ok=True;
6. physical_validity ok=True;
7. elapsed_seconds_verify < 300s;
8. PR #11 是 Open / Draft;
9. 不写入 result*.xlsx, 不启动 Q3, 不声明全局最优.

## 停止条件
FIX commit + REVIEW commit + push + PR #11 描述更新后立即停止,
不自动合并, 不进入 Q3 / TASK_006, 不启动 Audit CC / Hermes /
TASK_GOV_002.

## 失败模式 (fail-closed)
- TASK_005 CLEAN-HEAD VERIFICATION IDENTITY BINDING FAILED
- TASK_005 CLEAN-HEAD VERIFICATION WALL-CLOCK GATE HIT
- TASK_005 CLEAN-HEAD VERIFICATION EVALUATOR COUNT MISMATCH
- TASK_005 CLEAN-HEAD VERIFICATION CHECKPOINT IDENTITY MISMATCH
- TASK_005 CLEAN-HEAD VERIFICATION WORKTREE DIRTY AT START