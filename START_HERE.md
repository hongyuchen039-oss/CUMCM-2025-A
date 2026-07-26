# 项目驾驶舱

## 当前阶段
**TASK_004 FOUNDATION (Q2 单弹评估器基础, NOT AN OPTIMIZATION RESULT)** —
Q2 单弹策略四变量合同、合法性判断、单候选完整圆柱评估器与 100 候选
本地 smoke 已实现. 已通过 **FIX 加固**: 7 个 P1 修复组 (valid/status
语义、EPS_GROUND 三区分类、Q1 直接区间对照、非 vacuous 多区间测试、
system_error 退出码、smoke candidate_source + mixed-batch、coarse/medium/fine
实测), 71 个 Q2 单元测试 + 117 个 Q1 回归测试 = 188/188 全过.
正式 Q2 搜索尚未启动. PR #3 / PR #4 均已合并; CI 已进入 main.

## 本轮交付物 (TASK_004 Foundation)
- `src/q2_single_bomb.py` — Q2 单弹评估器主程序 (Python 标准库, 复用 q1_baseline 与 q1_cylinder)
- `tests/test_q2_single_bomb.py` — 单元测试 (71 测, 19 组 A-Q, 全过)
- `MODEL.md` — 增加"Q2 单弹策略评估合同"章节 + 本轮 FIX 7 P1 变更表
- `NEXT_TASK.md` — 更新为 TASK_004 Foundation + 下一阶段 TASK_004 Search
- `README.md` — 同步当前阶段

## 本轮交付物 (历史: TASK_003, 等待 TASK_004 Search 接续)
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

## 当前对题目的理解
2025 A 题"烟幕干扰弹的投放策略"——用 1~5 架无人机 (FY1~FY5) 投放烟幕干扰弹,
在来袭空地导弹 (M1/M2/M3, 300 m/s 直飞假目标) 与真目标 (圆柱 r=7 m, h=10 m,
**下底面圆心 (0, 200, 0)**, 几何中心 (0, 200, 5)) 之间形成烟幕云团
(云团 3 m/s 下沉, 起爆后 20 s 内、中心 10 m 范围有效遮蔽)。共 5 个问题:
- Q1: 给定参数求遮蔽时长 — 方案 A 1.435082 s ✓, 方案 B 1.392384 s ✓
- Q2: 单弹求最优策略 (待审后启动)
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

## 需要陈虹宇决定
- 是否接受本轮方案 B 1.392384 s 作为完整圆柱正式候选 (FULL-CYLINDER CANDIDATE / EXPERIMENTAL)?
- 是否接受 ΔT = −0.042698 s (方案 B 比方案 A 短 2.975%) 作为 Q1 点目标近似误差的量化?
- 是否接受 margin_max = 5.282478 m (0.001 s 局部网格估计) 报告口径?
- 是否接受 ρ=1 平台持续 1.380 s 作为口径?
- 是否批准合并 PR #3?

## 下一任务 (本轮已唯一固定)

**TASK_004 Foundation 已完成** — 等 PR 审核合并.

任务目的:
- 仅建立四变量合同、合法性、单候选评估器与 smoke, **不**启动搜索
- 现有 Q1 几何冻结保持不变 (42 + 75 = 117 个回归测试全过)

下一阶段: **TASK_004 Search** (尚未启动), 进入条件:
- Foundation PR 审核并合并
- CI 持续 PASS
- 本地 Foundation smoke 性能已记入下一阶段预算
- 搜索算法 / 收敛标准 / 性能预算重新冻结
- 仍需外部授权才能启动 Search

不得在本轮启动 TASK_004 Search.
不得提前切换任何分支或 PR.

## 下一步只做一件事
本轮完成 → 等 Foundation PR 审核 → 等待授权后再进入 TASK_004 Search.
不得提前切换任何分支或 PR.