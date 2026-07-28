# 当前唯一任务

## 任务编号
TASK_004 Q2 REAL SEARCH CORE V1 — FINAL REMAINING-P1 CLOSURE BUILT / WAITING FOR CLEAN-HEAD VERIFICATION

## 唯一目标
提交 v1.2 RP1 闭合补丁 → clean-HEAD pilot + interrupted + resume 验证 → 更新 PR #9 → 等待独立审查 GPT 复核。

## 为什么值得做
v1.2 已落地 (RP1-1/2/3/4/5/7 + P2 uniq output schema + 163 fixed-budget); 133 个单元测试通过 (85 + 48); 但 clean-HEAD pilot 验证尚未执行（spec 要求 commit-before-pilot）。

## 输入
- v1.2 源码（src/q2_search.py + configs/q2_search_gate_v1.json + tests/test_q2_search_rp1.py）；
- git HEAD 待 commit；
- PR #9。

## 允许修改
本轮可写入：src/q2_search.py、configs/q2_search_gate_v1.json、tests/test_q2_search_rp1.py、START_HERE.md、NEXT_TASK.md、README.md、MODEL.md §9、PR #9 描述；其它冻结。

## 禁止修改
- Q1 与 Q2 Foundation 数学和代码 (q1_baseline/q1_cylinder/q2_single_bomb)；
- RESULTS.md；
- problem/；
- result1/2/3.xlsx；
- main；
- Git 历史；
- .github/、outputs/、scripts/、CLAUDE.md、.claude/skills/。

禁止扩大预算（必须保持 163 evaluations 固定）、进入 Q3、声明全局最优、自动合并、自动转 Ready。

## 必须执行
- commit BEFORE pilot (clean HEAD first)；
- clean-HEAD pilot 完整跑通（97+8+48+8+2 = 163 evals, rc=0）；
- interrupted pilot（--stop-after-evaluations 80）→ rc=3 + checkpoint_v2.json 完整 + controlled_interruption.json；
- resume from interrupted checkpoint → 完整跑通 → canonical_result_sha256 == uninterrupted 路径；
- push + 更新 PR #9 描述（移除旧 overclaims / 旧 identity）；
- 50-item 验收报告。

## 必须产出
- 一次冻结 commit（v1.2 RP1 closure）；
- work/q2_search/pilot_result.json（uninterrupted）；
- work/q2_search/pilot_result.json（interrupted + resume 验证）；
- work/q2_search/checkpoint_v2.json（controlled_interruption 状态）；
- work/q2_search/controlled_interruption.json；
- PR #9 更新描述。

## 验收标准
1. RP1-1..7 + P2 uniq output 全部闭合；
2. 133 个 Q2 search 单元测试通过；
3. clean-HEAD pilot + interrupted + resume 三轮验证全部 rc 正确；
4. uninterrupted 与 resumed canonical_result_sha256 一致；
5. 不修改 Q1/Q2 Foundation；不写入 RESULTS.md；不生成 result1/2/3.xlsx。

## 返工
RP1 闭合为本轮最后一次返工上限（spec 明示）。

## 停止条件
clean-HEAD 验证完成 + PR #9 更新后立即停止，不自动转 Ready、不合并、不进入下一阶段。