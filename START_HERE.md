# 项目驾驶舱

## 当前阶段
**TASK_004 Q2 REAL SEARCH CORE V1** — Q2 Real Search Core v1 部分抢救施工.

Foundation 已通过 PR #5 合并到 main (commit 8cfe770); PR #6 (governance) 已合并;
PR #8 (post-Foundation status 同步) 已合并. 当前 main = bed2d9e.

本轮对 Search prototype commit (6f728d45b3bb776c19bbe8a857b26570eb79dc68) 进行
**部分抢救 (PARTIAL SALVAGE)**: 已通过普通 merge (--no-ff) 把 main 同步到
task/TASK_004-search (merge commit 453c098); prototype 仍为 ancestor.

实评估器已接入: `evaluate_with_real_evaluator` 调用
`src.q2_single_bomb.evaluate_single_bomb_strategy`. 串行 pipeline
(coarse → medium → local → fine) 已实现; pilot 跑通.

本轮**不等待 CI**; CI 不作为合并硬门槛; CI timeout 不代表数学失败。
正式 Search 仍为 PILOT / NOT A FORMAL Q2 RESULT; best-known 仍为
NOT A PROVEN GLOBAL OPTIMUM. result*.xlsx 尚未生成.

## 主线状态 (合并后)

- Foundation PR #5 → main (merge commit 8cfe770)
- Governance PR #6 → main (merge commit 72c7523)
- Status Sync PR #8 → main (merge commit bed2d9e)
- 当前 main = bed2d9e (含 Foundation + governance + role-boundary 修正)
- Q2 Foundation 88/88 本地通过; Q1 baseline 42/42 + Q1 cylinder 75/75 = 117/117; 全量 205/205 本地通过
- Q2 Search 54/54 本地通过 (本轮新增)
- profile-measure 退出码合同: 0 正常 / 1 任一程序异常 / 2 参数错误
- 默认 smoke 退出码: 0 无 system_error / 1 有 system_error / 2 参数错误
- Search CLI 退出码: 0 无 system_error / 1 有 system_error / 2 参数错误 / 拒绝 fake + workers>1

## 本轮交付物 (TASK_004 Foundation, 已合并)
- `src/q2_single_bomb.py` — Q2 单弹评估器主程序 (Python 标准库, 复用 q1_baseline 与 q1_cylinder)
- `tests/test_q2_single_bomb.py` — 单元测试 (88 测, 22 组 A-Q + U2/R2/S2 返工加固类, 全过)
- `MODEL.md` — 增加"Q2 单弹策略评估合同"章节 + 本轮 FIX 7 P1 + Profile Measurement 程序错误行为合同
- `NEXT_TASK.md` — 已升级为 TASK_004 SEARCH PROTOTYPE AUDIT AND SALVAGE
- `README.md` — 同步当前阶段与测试计数

## 本轮交付物 (历史: TASK_003, 已合并)
- `src/q1_cylinder.py` — 主程序 (Python 标准库, 仅复用 q1_baseline)
- `tests/test_q1_cylinder.py` — 单元测试 (75 测, 12 组 A-L, 全过, 含 2 个失败路径测试)
- `outputs/q1/q1_cylinder_comparison.svg` — x-z 投影 + 时间对照图 (`os.path.getsize` = 78857 字节 ≈ 77 KB)
- `MODEL.md` — 增加"完整圆柱遮蔽正式候选"章节 (固定方案 B 主判定与采样) + 本轮 FIX 变更表 (§12)
- `RESULTS.md` — 增加完整圆柱候选结果 + 收敛数据 + 本轮 FIX 后实测数字

## 关键计算结果 (FULL-CYLINDER CANDIDATE / EXPERIMENTAL, 本轮 FIX 后实测)

### 方案 A: 点目标基线 (沿用 TASK_002)
- **有效遮蔽总时长: 1.435082 s**
- 遮蔽区间: **(8.013006, 9.448088) s**

### 方案 B: 完整圆柱严格遮蔽 (本轮候选已实现, FIX 后实测, 等待审核冻结)
- **有效遮蔽总时长 (fine 采样): 1.392384 s**
- 遮蔽区间: **(8.055704, 9.448088) s**
- 最大覆盖率 ρ_max = 1.000
- ρ=1 平台 (DIAG_STEP=0.01 s 诊断网格): 约为 **(8.06, 9.44) s**, 网格区间跨度 **1.380 s**
- SVG_STEP=0.05 s 绘图网格首次采到 ρ=1: t ≈ **8.100 s** (仅用于 SVG 绘图, 不作为平台精确起点)
- 最大严格裕量 margin_max (0.001 s 局部网格估计): **5.282478 m** @ t = **9.418317 s**
  (SVG 网格峰值附近 ±0.05 s 局部估计, 非解析极值)

### 与 Q1 点目标对照 (ΔT = 方案 B − 方案 A)
- ΔT = **−0.042698 s** (圆柱更短, 因严格约束)
- 相对差异 = **−2.975%** (|ΔT| / 点目标时长)
- 上界 9.448088 s 在两方案中一致 (云团下沉后期几何对称)
- 下界 8.055704 s (圆柱) > 8.013006 s (点目标), 因点目标几何中心比圆柱表面更容易被遮挡

## 本轮已检查的内容
- [x] 圆柱采样几何 (侧面 + 顶面 + 底面) 总权重 = 2πR_T H_T + 2πR_T² (精确)
- [x] 法向量均为单位向量 (|n| = 1 ± 1e-12)
- [x] 单元中心在内部 (z ∈ (0, H_T) 严格, 避免公共棱边)
- [x] 可见性测试: n(X) · (M(t) − X) >= −EPS_VISIBLE (支持平面法, 切线轮廓保守可见)
- [x] 严格遮蔽: 所有当前可见表面采样点的视线均被烟幕球体相交 (max_d ≤ 10)
- [x] 覆盖率: ρ = occluded_weight / visible_weight (辅助诊断)
- [x] 空间三档收敛: coarse / medium / fine 总时长差 ≤ 0.0023 s
- [x] 时间三档收敛: 0.02 / 0.01 / 0.005 s 端点完全一致 (max |Δt| = 0)
- [x] check_spatial_convergence / check_temporal_convergence 真实执行阈值, 均 PASS
- [x] main() 在空间/时间任一未收敛时 return 2, 真实退出码
- [x] 75 个单元测试全过 (A 10 + B 10 + C 5 + D 6 + E 6 + F 8 + G 5 + H 9 + I 6 + J 4 + K 3 + L 4)
- [x] SVG 合法可解析, 含圆柱标识 + 时间对照面板 + 图例, 红色副标题标 NOT FINAL
- [x] Python 标准库, 无第三方依赖
- [x] Q1 点目标基线 42/42 测试仍通过 (回归保证)
- [x] Q2 Foundation 88/88 测试通过 (PR #5 已合并)
- [x] profile-measure 退出码合同已加固 (PR #5 已合并)
- [x] 全量 205/205 本地通过

## 当前对题目的理解
2025 A 题"烟幕干扰弹的投放策略"——用 1~5 架无人机 (FY1~FY5) 投放烟幕干扰弹,
在来袭空地导弹 (M1/M2/M3, 300 m/s 直飞假目标) 与真目标 (圆柱 r=7 m, h=10 m,
**下底面圆心 (0, 200, 0)**, 几何中心 (0, 200, 5)) 之间形成烟幕云团
(云团 3 m/s 下沉, 起爆后 20 s 内、中心 10 m 范围有效遮蔽)。共 5 个问题:
- Q1: 给定参数求遮蔽时长 — 方案 A 1.435082 s ✓, 方案 B 1.392384 s ✓
- Q2: 单弹求最优策略 (Foundation 已就绪, Search 等待审核)
- Q3: 单机 3 弹, result1.xlsx
- Q4: 三机各 1 弹, result2.xlsx
- Q5: 五机各至多 3 弹, result3.xlsx

## 官方材料核验
- PDF 读取: 成功 (1 页题面)
- PDF 事实逐项核对: 完成
- 三个结果模板 xlsx 表头逐项核对: 完成 (`problem/FACTS.md §13`)
- 未明确事项: 见 `problem/FACTS.md §15`

## 当前风险
- 方案 B 完整圆柱仍是**有限采样近似** (单元中心法, medium/fine 双档已收敛).
- 圆柱是凸体, 面内可见性使用支持平面判定;
  公共棱边未直接采样, 由相邻表面单元中心随网格加密逼近.
- 严格遮蔽裕量有上下界 (上界由粗采样锁定, 严格判据下限由 fine 锁定).
- 覆盖率仅作辅助诊断, 当前**不**使用人为覆盖率阈值 (避免人造结果).
- 仍标记为 FULL-CYLINDER CANDIDATE / EXPERIMENTAL, 不得冒充 VERIFIED / FINAL.
- **远程存在未审核 Search prototype commit (6f728d45b3bb776c19bbe8a857b26570eb79dc68)**, 尚未审计, 尚未接受, 尚未创建 PR.

## 当前任务 (唯一)

**TASK_004 SEARCH PROTOTYPE READ-ONLY AUDIT AND SALVAGE DECISION** — 远程未审核 Search prototype 的只读审核与处置决策.

任务目的:
- Foundation 已合并; 主线 governance 已落地; 全量 205/205 本地通过
- 远程存在一份未审核 Search prototype commit (6f728d45b3bb776c19bbe8a857b26570eb79dc68)
- Audit CC 只读审核并形成建议 (审核代码 / 测试 / 算法 / 数学合同 / 性能预算 / 可复用性)
- Hermes 只读核验仓库事实 (branch / SHA / changed files / PR 状态)
- MAIN 综合两家证据后作出最终处置决定 (整体采用 / 局部抢救 / 不采用并重写)
- "Salvage" 只表示形成处置建议, 不表示实施修改
- 不得在审计前擅自 cherry-pick / merge / 重写
- 仍不得生成 result1.xlsx
- 不删除现有 prototype commit; 不删除远程分支

## 下一阶段 (待当前任务结束)

SEARCH PROTOTYPE 决策后的下一阶段仍在冻结中。
可能路径:
- 整体采用
- 局部抢救
- 不采用并重写

无论选择哪条路径, 旧 prototype commit 和远程分支均保留,
"不采用"不等于删除历史.

由 MAIN 综合 Audit CC 与 Hermes 证据后作最终处置决定.

## 下一步只做一件事
本轮完成 → 等 Audit CC 只读审核 + Hermes 仓库事实核验 + MAIN 最终处置决定.
不得提前切换任何分支或 PR.
