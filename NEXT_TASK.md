# 当前唯一任务

## 任务编号
TASK_005 Q2 FORMAL SEARCH & RESULT FREEZE — BUILT AND RUN, WAITING FOR INDEPENDENT MATH/RESULT REVIEW

## 唯一目标
不修改本任务分支；不进入 Q3；不写 result1.xlsx；不声明全局最优。
等待独立审查（Audit CC / Hermes）复算 winner 物理量 + 稳定性 + 扰动 +
finalist pool 解释性。仅在审查通过后另立 TASK_006（Q3 三弹串接 / result1.xlsx）。

## 为什么值得做
TASK_005 已在本任务分支完成：
- 独立 schema 3 / gate_id `q2_search_formal_v1` / declaration
  `FORMAL BEST-KNOWN Q2 CANDIDATE / NOT A PROVEN GLOBAL OPTIMUM`；
- 三 seeds (2025, 2026, 2027) × 1000 evals/seed × 5-stage pipeline 全部完成；
- 跨 seed 13 finalists，pilot best-known 已显式注入；
- 统一 fine cylinder re-evaluation（scan_step=0.005）→ winner 与 pilot
  fixed-163 best-known 完全一致
  (h=3.121767217560497, s=115.43351397802584, r=1.7672692031529031,
  d=3.889202402720746, dur=2.48275905609131 s)；
- 0.02 / 0.01 / 0.005 三档 duration delta=0.000s；
- 4 方向扰动均未改善 winner（局部收敛）；
- 物理合法性校验通过（speed ∈ [70,140], release ≥ 0, delay 在落地约束内,
  heading ∈ [0, 2π)）；
- 22 个新增 FormalProfileTests 通过, 148 个 pilot 测试未删除或放宽；
- PR "TASK_005: formalize and freeze Q2 best-known result" 已开 Draft.

## 输入
- src/q2_search.py（仅追加 formal block, pilot fixed-163 不动）；
- configs/q2_search_formal_v1.json (新, schema 3)；
- scripts/run_q2_formal.py (新, 唯一 orchestrator)；
- tests/test_q2_search.py（追加 22 个 FormalProfileTests）；
- outputs/q2/q2_formal_summary.json + per_seed_summary.json；
- outputs/q2/seed_{2025,2026,2027}/pilot_result.json；
- work/q2_formal/ + work/q2_pilot_calib/（gitignored）；
- START_HERE.md / NEXT_TASK.md / README.md / MODEL.md / RESULTS.md；
- Draft PR "TASK_005: formalize and freeze Q2 best-known result".

## 允许修改
本轮（仅剩收口动作）：
- START_HERE.md / NEXT_TASK.md / README.md / MODEL.md / RESULTS.md；
- 1 个 REVIEW 风格 commit；
- PR 描述更新；
- 175 项 unittest 全量回归。

## 禁止修改
- configs/q2_search_gate_v1.json（pilot 不动）；
- src/q1_baseline.py / src/q1_cylinder.py / src/q2_single_bomb.py；
- tests/test_q1_baseline.py / tests/test_q1_cylinder.py /
  tests/test_q2_single_bomb.py；
- scripts/verify_task_context.py；
- tests/test_verify_task_context.py；
- problem/；
- outputs/submission/；
- result1/2/3.xlsx；
- .github/；
- CLAUDE.md / .claude/；
- main / Git 历史；
- 旧 pilot identity（4a8ee08 / f81f436 / 8861203e… / 98 global_coarse /
  164 completed_count）不得回写 MODEL.md / PR 描述 / 代码。

禁止：自动合并 / 自动转 Ready / 自行写入 result1.xlsx / 启动 Q3 / 扩大
formal 预算到 2000（> 3600s wall-clock gate）/ 声明全局最优 / 改写
正式历史。

## 必须执行
1. 收口：REMOVE 旧 TASK_004 文本（PR #9 / Verification Correction 等），
   REPLACE 为 TASK_005 现状；
2. 1 个 REVIEW 风格 commit（不拆分、不 amend、不 baseline commit）；
3. push 到 task/TASK_005-q2-formal-search；
4. 创建/更新 Draft PR "TASK_005: formalize and freeze Q2 best-known result"；
5. 175 项 unittest 全量回归 `python -m unittest discover -s tests -p "test_*.py" -v`；
6. 报告：`TASK_005 Q2 FORMAL SEARCH BUILT AND RUN — WAITING FOR INDEPENDENT MATH/RESULT REVIEW`；
7. 停止（不自动进入下一阶段，不自动合并，不启动 Q3 / Audit CC / Hermes / TASK_GOV_002）。

## 必须产出
- 1 个收口 commit（REVIEW 前缀）；
- PR "TASK_005: formalize and freeze Q2 best-known result" 草稿已开 / 已更新；
- 175 项 unittest 全部 PASS（148 pilot + 22 formal + 5 harness）；
- 50-item 收口报告；
- 独立审查 checklist（winner 物理量复算 / 稳定性 / 扰动 / finalist pool 解释性）。

## 验收标准
1. 148 个 pilot 测试 + 22 个 formal 测试 + 5 个 harness 测试共 175 项全 PASS；
2. PR "TASK_005: formalize and freeze Q2 best-known result" 是 Open / Draft；
3. declaration = `FORMAL BEST-KNOWN Q2 CANDIDATE / NOT A PROVEN GLOBAL OPTIMUM`；
4. final_best_status = `OK_FINE_RESULT`；
5. 不写入 result1/2/3.xlsx，不启动 Q3，不声明全局最优；
6. pilot best-known 数值与 formal winner 数值一致
   (h=3.121767217560497, s=115.43351397802584, r=1.7672692031529031,
   d=3.889202402720746, dur=2.48275905609131 s)；
7. stability_ok=True, perturbation.any_improves=False,
   physical_validity.ok=True；
8. 入口文档同步（START_HERE.md / NEXT_TASK.md / README.md / MODEL.md / RESULTS.md）。

## 停止条件
独立审查清单交付 + 175 项全量回归 PASS + PR 已开 Draft 后立即停止，
不自动合并、不进入 Q3 / TASK_006、不启动 Audit CC / Hermes / TASK_GOV_002。
