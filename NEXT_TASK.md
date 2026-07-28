# 当前唯一任务

## 任务编号
TASK_004 Q2 REAL SEARCH CORE V1 — P1 PATCH BUILT / WAITING FOR READ-ONLY REVIEW

## 唯一目标
将 P1 补丁 HEAD (commit) 提交独立审查 GPT 复核；等待复核结论。

## 为什么值得做
本轮 P1 补丁施工已完成 (P1-A/B/C/D/E/F/G + P2 formal-disabled)，但尚未经过独立审查 GPT 复核；补丁 HEAD 在冻结范围内且已通过 85 个单元测试 + 真实 pilot + resume 等价验证。

## 输入
- 本轮 P1 补丁 HEAD；
- 独立审查 GPT 复核报告；
- PR #9 状态。

## 允许修改
当前为只读等待状态；不得仓库写入。
若独立审查 GPT 要求返工，必须重新获得用户明确授权。

## 禁止修改
- Q1 与 Q2 Foundation 数学和代码；
- RESULTS.md；
- problem/；
- result1/2/3.xlsx；
- main；
- Git 历史。

禁止扩大预算、进入 Q3、声明全局最优或自动合并。

## 必须执行
- 等待独立审查 GPT 复核 PR #9；
- 等待复核结论（接受 / 最小修补 / 核心返工）。

## 必须产出
- 独立审查 GPT 的复核报告。

## 验收标准
1. P1 项全部封闭；
2. 补丁 HEAD 通过 85 个 Q2 search 单元测试；
3. pilot 与 resume 输出完全一致（已验证）；
4. 不修改 Q1 / Q2 Foundation；
5. 不写入 RESULTS.md；不生成 result1/2/3.xlsx。

## 返工
若独立审查 GPT 要求返工：最多一次冻结补丁返工；不得无限循环润色。

## 停止条件
独立审查 GPT 复核完成后停止，不自动转 Ready、不合并、不进入下一阶段。