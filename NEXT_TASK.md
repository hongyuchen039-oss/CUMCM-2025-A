# 当前唯一任务

## 任务编号
TASK_005 LOCAL REFINEMENT — BUDGET EXHAUSTED (RESULT REVIEW BLOCKED).

## 唯一目标
不重跑 3 seeds / 不重跑 17 候选完整复评 / 不重跑 473 项全量回归.
只在 clean HEAD 上做最多 32 次 refinement evaluation 的 deterministic
coordinate search (3 levels × 单 sweep), 仅复评 2 个 parent (formal winner
+ pert_09 best). 硬时间上限 2100s. 真实 winner duration 较大者作为
refinement 起点 (不信任文档中 3.312s 的舍入).

## 为什么值得做
P1 证据门已闭环 (HEAD 335a1f4d):
- canonical_result_sha256 = 2efcc91486d4ce9d22bfdedc0a4d57c36857d506126bca40c1a31695a96d1b3a
- formal winner = (h=3.121767217560497, s=115.43351397802584,
  r=1.7672692031529031, d=3.889202402720746, dur=2.48275905609131 s)
- 16 项 one-var 扰动 5/16 改善 → local_perturbation_passed=False
- 3 seeds × 1000 evals 全部 OK_FINE_RESULT, system_error=0

pert_09 (release_time_s -0.5) 在 16 项扰动中持续改善 →
值得在 ±0.2 / ±0.5 邻域做 local refinement.

## 输入 (本轮, 不重跑)
- src/q2_search.py (本轮追加 refinement 模块, 原 formal block 不动)
- scripts/run_q2_formal.py (本轮加 --refine-only 分支)
- tests/test_q2_search.py (本轮加 20 个 RefinementGateTests)
- configs/q2_search_formal_v1.json (本轮不动)
- outputs/q2/q2_formal_summary.json + per_seed_summary.json (本轮不动)
- work/q2_formal/seed_* (gitignored, 本轮不动)

## 允许修改
本轮:
- src/q2_search.py (追加 run_formal_refinement + RefinementGateTests 配合)
- scripts/run_q2_formal.py (追加 --refine-only 入口)
- tests/test_q2_search.py (追加 RefinementGateTests 类, 20 个新测试)
- START_HERE.md / NEXT_TASK.md / RESULTS.md / MODEL.md / README.md
- work/q2_formal_refinement/checkpoint.json (gitignored, runtime artifact)
- work/q2_formal_refinement.log (gitignored, tee output)
- outputs/q2/q2_refine_summary.json (refinement summary, tracked)
- work/task_context.json (expected_head 推齐新 FIX commit)
- 1 个 FIX commit + 1 个 REVIEW commit

## 禁止修改
- configs/q2_search_gate_v1.json (pilot 不动)
- src/q1_baseline.py / src/q1_cylinder.py / src/q2_single_bomb.py
- tests/test_q1_baseline.py / tests/test_q1_cylinder.py / tests/test_q2_single_bomb.py
- scripts/verify_task_context.py / tests/test_verify_task_context.py
- problem/ / outputs/submission/ / result1/2/3.xlsx
- .github/ / CLAUDE.md / .claude/
- main / Git 历史
- 旧 pilot identity / 旧 PRE-FIX canonical / 旧 4-方向扰动描述

禁止: 自动合并 / 转 Ready / 写 result*.xlsx / 启动 Q3 / 扩大 refinement
预算到 33+ / 跳过 wall-clock gate / 跳过 budget gate / 改写正式历史.

## 必须执行
1. 1 个 FIX commit (refinement 代码 + 20 个新测试);
2. 推 task_context.json expected_head 推齐新 FIX commit;
3. 启动 refinement:
   `set -o pipefail; python -u scripts/run_q2_formal.py --refine-only
    2>&1 | tee work/q2_formal_refinement.log; rc=${PIPESTATUS[0]}; exit "$rc"`
4. refine 结束后跑稳定性 (3 档) + 最终 16 项 one-var 扰动;
5. 1 个 REVIEW commit (refresh 文档 + refinement summary);
6. push 到 task/TASK_005-q2-formal-search + PR #11 描述更新;
7. 报告 (per MAIN §十 格式).

## 必须产出
- 1 个 FIX commit + 1 个 REVIEW commit (均推到现有分支和 PR #11);
- outputs/q2/q2_refine_summary.json (tracked, 含 refined candidate +
  16 项最终扰动结果);
- work/q2_formal_refinement/checkpoint.json (gitignored);
- work/q2_formal_refinement.log (gitignored);
- 210 项 tests.test_q2_search PASS (148 pilot + 22 formal + 20 P1 + 20 RefinementGate);
- 收口报告.

## 验收标准
1. 210 项 tests.test_q2_search 全 PASS (本轮唯一一次 test_q2_search 全跑);
2. PR #11 是 Open / Draft;
3. refinement summary 写到 outputs/q2/q2_refine_summary.json;
4. refinement 总 evaluations_completed ≤ 32;
5. refinement 总 elapsed ≤ 2100s;
6. 不写入 result*.xlsx, 不启动 Q3, 不声明全局最优;
7. final 16 项 one-var 全部无改善 (≥ 1e-6 容差) → local_perturbation_passed=true
   才能冻结; 否则 → TASK_005 LOCAL REFINEMENT P1 REMAINS — BLOCKED.

## 停止条件
refinement summary 写入 + 1 个 REVIEW commit + push + PR #11 描述更新
后立即停止, 不自动合并, 不进入 Q3 / TASK_006, 不启动
Audit CC / Hermes / TASK_GOV_002.

## 失败模式 (fail-closed)
- TASK_005 LOCAL REFINEMENT BUDGET EXHAUSTED — RESULT REVIEW BLOCKED
- TASK_005 LOCAL REFINEMENT WALL-CLOCK GATE HIT — RESULT REVIEW BLOCKED
- TASK_005 LOCAL REFINEMENT P1 REMAINS — MATH/RESULT REVIEW BLOCKED