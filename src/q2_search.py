"""Q2 Search Implementation Skeleton (TASK_004 / NOT AN OPTIMIZATION RESULT).

本轮任务范围 (TASK_004 Search Skeleton):

- 仅搭建 Search 工程的最小骨架: 候选生成、FakeEvaluator、checkpoint/resume、
  workers=1 (serial) 与 multiprocessing.Pool 并行执行。
- 真实 Q2 单弹评估必须通过注入的 evaluator 提供; 默认 FakeEvaluator 仅返回
  (total_duration_s, payload) 形式的合成结果, 不调用 q2_single_bomb 的几何
  评估。本轮**不**执行正式 Search, **不**声明 Q2 最优解, **不**写
  outputs/submission/result*.xlsx。
- Frozen benchmark (serial 66 timed + 3 warm-up, parallel 22 timed + 3 warm-up,
  总计 94 calls) 仅用于校准 skeleton 自身的开销。

显式不做:

- 不得声称 Q2 最优结果。
- 不得写入 outputs/submission/result*.xlsx。
- 不得修改 src/q1_baseline.py / src/q1_cylinder.py / src/q2_single_bomb.py。
- 不得修改 PR #5 / Foundation 相关分支。
- 不得执行正式 Search。

参考:
- problem/FACTS.md (官方事实)
- src/q2_single_bomb.py (Q2 单弹评估, 仅注入接口, 默认 evaluator 不调用)
- configs/q2_search_gate_v1.json (本轮 frozen gate)
- CLAUDE.md (本项目长期规则)

只使用 Python 标准库.
"""

from __future__ import annotations

import hashlib
import json
import multiprocessing
import os
import statistics
import sys
import tempfile
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

# === Standard library only ===
# 仅依赖 Python 标准库. 任何 numba/numpy 等运行时不在允许范围内.


# =============================================================================
#  第一节: 搜索域与 manifest (TASK_004 Search §1)
# =============================================================================
# 搜索域 (节选, 与 src/q2_single_bomb.generate_candidates 一致, 但此处只描述
# 边界, 不在此生成 candidates).
SEARCH_DOMAIN: Dict[str, Any] = {
    "heading_rad": {"min": 0.0, "max": 6.283185307179586},
    "speed_mps":   {"min": 70.0, "max": 140.0},
    "release_time_s": {"min": 0.0, "max": 66.0},
    "delay_s":     {"min": 0.0, "max": 30.0},
}


def q_space_descriptor() -> Dict[str, Any]:
    """返回搜索域描述符 (纯 dict). 用于 manifest / 配置校验.

    Returns:
        dict 含四个变量的 min/max 边界与单位. 不含任何候选或评估结果.
    """
    return {k: dict(v) for k, v in SEARCH_DOMAIN.items()}


# =============================================================================
#  第二节: manifest 文本与 SHA-256 (TASK_004 Search §2)
# =============================================================================
def manifest_payload(seed: int, n_first: int = 3) -> str:
    """构造 (seed, 前 n_first 个 q 向量) 的 manifest 文本.

    必须与 src/q2_single_bomb.generate_candidates(seed) 在前 n_first 项上
    **逐元素**一致; 一旦上游随机源改变, 本函数输出的前 n_first 行也会变,
    测试应随之更新 manifest SHA-256.

    Args:
        seed: random 种子.
        n_first: 取前 n_first 个候选, 锁定在 manifest 中.

    Returns:
        str: 文本 (UTF-8). 每行 (heading_rad, speed_mps, release_time_s, delay_s).
    """
    # 本函数仅描述 manifest 文本构造; 不直接调用 generate_candidates,
    # 测试中显式传入已经生成的候选行以避免重复随机源依赖. 这里给出
    # 行格式: "seed=<seed>" + 4 个浮点数 / 行.
    raise NotImplementedError(
        "manifest_payload 必须由调用方提供候选行 (避免与随机源耦合). "
        "tests/test_q2_search.py 通过 build_manifest_text 直接构造.")


def build_manifest_text(seed: int,
                         vectors: Sequence[Tuple[float, float, float, float]]
                         ) -> str:
    """从已知的 (seed, vectors) 显式构造 manifest 文本.

    测试 (test_manifest_locked_three_seeds) 中直接调用本函数以锁定 SHA-256.

    Args:
        seed: 种子值.
        vectors: 候选行序列, 每行 (heading_rad, speed_mps, release_time_s, delay_s).

    Returns:
        str: manifest 文本 (UTF-8).
    """
    lines = [f"seed={seed}"]
    for v in vectors:
        # repr() 保证 Python 默认浮点精度可复现 (与 str(float) 等价, 无截断)
        lines.append(
            f"({v[0]!r}, {v[1]!r}, {v[2]!r}, {v[3]!r})")
    return "\n".join(lines) + "\n"


def compute_manifest_sha256(text: str) -> str:
    """计算 manifest 文本的 SHA-256 (UTF-8)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def manifest_record(seed: int,
                     vectors: Sequence[Tuple[float, float, float, float]]
                     ) -> Dict[str, Any]:
    """构造 manifest dict (用于 JSON 序列化 / 测试断言)."""
    text = build_manifest_text(seed, vectors)
    sha = compute_manifest_sha256(text)
    return {
        "seed": int(seed),
        "n_vectors": len(vectors),
        "sha256": sha,
        "text": text,
        "vectors": [list(v) for v in vectors],
    }


# =============================================================================
#  第三节: FakeEvaluator (TASK_004 Search §3)
# =============================================================================
# FakeEvaluator 是默认 evaluator: 不调用任何几何 / 烟幕 / 云团评估, 仅根据
# q 向量生成 (total_duration_s, payload) 形式的合成结果. 本轮不允许默认
# evaluator 触发真实 Q2 几何评估, 故 fake 是唯一允许的默认行为.

@dataclass(frozen=True)
class FakeEvalResult:
    """FakeEvaluator 单次返回结果.

    与真实 SingleBombEvaluation **不**同构; 仅作为 skeleton 内部信号.
    字段:
      - total_duration_s: float, 合成目标值
      - payload: dict, 包含 source / elapsed_s / candidate 元数据
    """
    total_duration_s: float
    payload: Dict[str, Any]


def _fake_eval_total(candidate: Tuple[float, float, float, float],
                      seed: int = 0,
                      sleep_s: float = 0.0,
                      wall_clock: Optional[float] = None
                      ) -> FakeEvalResult:
    """单次 FakeEvaluator 调用 (top-level, multiprocessing 可 pickle).

    Args:
        candidate: (heading_rad, speed_mps, release_time_s, delay_s).
        seed: evaluator 内随机源种子 (默认 0, 确定性).
        sleep_s: 模拟几何评估的 sleep 时长 (s). 0 表示零成本.
        wall_clock: 由 multiprocessing pool 注入的 wall-clock; 默认为 None.

    Returns:
        FakeEvalResult 含合成 total_duration_s 与 payload.
    """
    if sleep_s > 0.0:
        time.sleep(sleep_s)
    # 合成目标值: 简单线性函数, 仅用于 skeleton 信号, 不解释物理意义.
    h, s, r, d = candidate
    # 锁定公式 (TASK_004 frozen): total = (sin(h) + 1) * 0.5 + (s - 70) / 70
    # + (r / 60) + (d / 30). 范围大致 [0, ~3.0].
    total = (math_sin(h) + 1.0) * 0.5 + (s - 70.0) / 70.0 \
             + (r / 60.0) + (d / 30.0)
    payload = {
        "source": "fake_evaluator",
        "seed": int(seed),
        "candidate": {
            "heading_rad": float(h),
            "speed_mps": float(s),
            "release_time_s": float(r),
            "delay_s": float(d),
        },
        "wall_clock_s": float(wall_clock) if wall_clock is not None else 0.0,
    }
    return FakeEvalResult(total_duration_s=total, payload=payload)


def math_sin(x: float) -> float:
    """局部 sin, 避免与 math.sin 名字冲突. 实际就是 math.sin."""
    import math
    return math.sin(x)


class FakeEvaluator:
    """FakeEvaluator 工厂: 注入 sleep_s / seed.

    不得在 __call__ 中调用 q2_single_bomb 几何评估; 任何时候 sleep_s=0
    即可作为零成本 stub.
    """

    def __init__(self, seed: int = 0, sleep_s: float = 0.0) -> None:
        self.seed = int(seed)
        self.sleep_s = float(sleep_s)

    def __call__(self,
                  candidate: Tuple[float, float, float, float],
                  ) -> FakeEvalResult:
        return _fake_eval_total(
            candidate, seed=self.seed, sleep_s=self.sleep_s,
            wall_clock=time.perf_counter())


# =============================================================================
#  第四节: Checkpoint / Resume (TASK_004 Search §4)
# =============================================================================
@dataclass
class Checkpoint:
    """Search checkpoint.

    字段:
      - schema: 当前 schema 版本号
      - seed: 当前 seed (用于 mismatch 校验)
      - domain_hash: 搜索域描述符的 SHA-256 (用于 mismatch 校验)
      - evaluator_kind: evaluator 类型 (用于 mismatch 校验)
      - completed: 已完成的 (index, total_duration_s, candidate) 元组列表
      - best_index / best_total: 当前最优候选索引与目标值
    """
    schema: int
    seed: int
    domain_hash: str
    evaluator_kind: str
    completed: List[Tuple[int, float, Tuple[float, float, float, float]]] \
        = field(default_factory=list)
    best_index: int = -1
    best_total: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema": int(self.schema),
            "seed": int(self.seed),
            "domain_hash": self.domain_hash,
            "evaluator_kind": self.evaluator_kind,
            "completed": [
                {"index": int(i), "total": float(t),
                 "candidate": [float(x) for x in c]}
                for (i, t, c) in self.completed
            ],
            "best_index": int(self.best_index),
            "best_total": float(self.best_total),
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "Checkpoint":
        if not isinstance(d, Mapping):
            raise ValueError(f"checkpoint 必须是 mapping, 实际 {type(d).__name__}")
        if "schema" not in d or "seed" not in d \
                or "domain_hash" not in d or "evaluator_kind" not in d:
            raise ValueError("checkpoint 缺少必要字段 (schema/seed/domain_hash/evaluator_kind)")
        try:
            schema = int(d["schema"])
            seed = int(d["seed"])
        except (TypeError, ValueError) as e:
            raise ValueError(f"checkpoint schema/seed 非整数: {e}")
        domain_hash = str(d["domain_hash"])
        evaluator_kind = str(d["evaluator_kind"])
        completed_raw = d.get("completed", [])
        completed: List[Tuple[int, float, Tuple[float, float, float, float]]] = []
        for entry in completed_raw:
            if not isinstance(entry, Mapping):
                raise ValueError(f"completed 项必须是 mapping, 实际 {type(entry).__name__}")
            try:
                idx = int(entry["index"])
                total = float(entry["total"])
                cand = tuple(float(x) for x in entry["candidate"])
            except (KeyError, TypeError, ValueError) as e:
                raise ValueError(f"completed 项字段错误: {e}")
            if len(cand) != 4:
                raise ValueError(f"completed 项 candidate 长度必须为 4, 实际 {len(cand)}")
            completed.append((idx, total, cand))
        best_index = int(d.get("best_index", -1))
        best_total = float(d.get("best_total", 0.0))
        return cls(
            schema=schema, seed=seed, domain_hash=domain_hash,
            evaluator_kind=evaluator_kind, completed=completed,
            best_index=best_index, best_total=best_total,
        )


CHECKPOINT_SCHEMA: int = 1


def _hash_domain(domain: Mapping[str, Any]) -> str:
    """对搜索域描述符生成 SHA-256 (基于规范化 JSON 文本)."""
    text = json.dumps(domain, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def save_checkpoint(checkpoint: Checkpoint, path: str) -> None:
    """将 checkpoint 写入文件 (原子: 写临时文件后 rename)."""
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=parent, prefix=".ckpt_", suffix=".json")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(checkpoint.to_dict(), f, ensure_ascii=False,
                      indent=2, sort_keys=False)
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        raise


def load_checkpoint(path: str) -> Checkpoint:
    """从文件加载 checkpoint. 文件不存在则 raise FileNotFoundError."""
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)
    return Checkpoint.from_dict(d)


def make_initial_checkpoint(seed: int,
                            evaluator_kind: str = "fake",
                            domain: Optional[Mapping[str, Any]] = None
                            ) -> Checkpoint:
    """构造初始 (空) checkpoint."""
    if domain is None:
        domain = q_space_descriptor()
    return Checkpoint(
        schema=CHECKPOINT_SCHEMA,
        seed=int(seed),
        domain_hash=_hash_domain(domain),
        evaluator_kind=str(evaluator_kind),
        completed=[],
        best_index=-1,
        best_total=0.0,
    )


# =============================================================================
#  第五节: workers=1 (serial) 执行 (TASK_004 Search §5)
# =============================================================================
def _eval_and_record(checkpoint: Checkpoint,
                      idx: int,
                      candidate: Tuple[float, float, float, float],
                      evaluator: Callable[[Tuple[float, float, float, float]],
                                          FakeEvalResult],
                      ) -> Tuple[float, Tuple[float, float, float, float]]:
    """调用 evaluator, 写入 checkpoint.completed, 返回 total/candidate."""
    ev = evaluator(candidate)
    total = float(ev.total_duration_s)
    checkpoint.completed.append((idx, total, candidate))
    if total > checkpoint.best_total:
        checkpoint.best_total = total
        checkpoint.best_index = idx
    return total, candidate


def run_serial(candidates: Sequence[Tuple[float, float, float, float]],
               evaluator: Callable[[Tuple[float, float, float, float]],
                                   FakeEvalResult],
               checkpoint: Optional[Checkpoint] = None,
               start_index: int = 0,
               ) -> Tuple[List[Tuple[int, float, Tuple[float, float, float, float]]],
                          Checkpoint]:
    """workers=1 serial 执行.

    Args:
        candidates: 待评估候选序列.
        evaluator: FakeEvaluator 或等价 callable.
        checkpoint: 可选, 已存在的 checkpoint 用于 resume. None 则新建空白.
        start_index: enumerate 起始 index (用于 resume 时与原始候选池对齐).

    Returns:
        (completed_list, checkpoint): completed_list 与 checkpoint.completed 一致.

    Raises:
        ValueError: 若 checkpoint 的 schema/seed/domain_hash 与当前不匹配.
    """
    if checkpoint is None:
        checkpoint = make_initial_checkpoint(seed=0)
    expected_domain_hash = _hash_domain(q_space_descriptor())
    if checkpoint.schema != CHECKPOINT_SCHEMA:
        raise ValueError(
            f"checkpoint schema mismatch: 当前 {CHECKPOINT_SCHEMA}, "
            f"文件 {checkpoint.schema}")
    if checkpoint.domain_hash != expected_domain_hash:
        raise ValueError(
            f"checkpoint domain_hash mismatch: 当前 {expected_domain_hash}, "
            f"文件 {checkpoint.domain_hash}")
    if start_index < 0:
        raise ValueError(f"start_index 必须 ≥ 0, 实际 {start_index}")
    completed_set = {i for (i, _, _) in checkpoint.completed}
    for offset, cand in enumerate(candidates):
        idx = start_index + offset
        if idx in completed_set:
            continue
        _eval_and_record(checkpoint, idx, cand, evaluator)
    return list(checkpoint.completed), checkpoint


# =============================================================================
#  第六节: 并行执行 (multiprocessing.Pool) (TASK_004 Search §6)
# =============================================================================
# Pool.map 的 worker 必须是 module-level function, 否则 pickle 失败.
def _pool_worker_eval(args: Tuple[int,
                                    Tuple[float, float, float, float],
                                    int,
                                    float,
                                    ]) -> Tuple[int, float,
                                                  Tuple[float, float, float, float]]:
    """multiprocessing worker: 单次评估.

    Args:
        args: (idx, candidate, seed, sleep_s).

    Returns:
        (idx, total, candidate).
    """
    idx, candidate, seed, sleep_s = args
    if sleep_s > 0.0:
        time.sleep(sleep_s)
    h, s, r, d = candidate
    total = (math_sin(h) + 1.0) * 0.5 + (s - 70.0) / 70.0 \
             + (r / 60.0) + (d / 30.0)
    return int(idx), float(total), candidate


def run_parallel(candidates: Sequence[Tuple[float, float, float, float]],
                  evaluator_seed: int,
                  sleep_s: float,
                  workers: int,
                  chunksize: int = 1,
                  checkpoint: Optional[Checkpoint] = None,
                  start_index: int = 0,
                  ) -> Tuple[List[Tuple[int, float, Tuple[float, float, float, float]]],
                             Checkpoint]:
    """multiprocessing 并行执行.

    注意: FakeEvaluator 的合成公式与 _pool_worker_eval **逐行一致**; 但
    并行路径不依赖 evaluator 对象 (依赖 pickle-friendly worker).

    Args:
        candidates: 待评估候选序列.
        evaluator_seed: FakeEvaluator 随机种子 (并行路径下不参与计算, 仅记录).
        sleep_s: 单候选模拟 sleep 时长 (s).
        workers: 进程数 (≥ 1).
        chunksize: Pool.map 的 chunksize (≥ 1).
        checkpoint: 可选 resume checkpoint.
        start_index: enumerate 起始 index (用于 resume 时与原始候选池对齐).

    Returns:
        (completed_list, checkpoint).

    Raises:
        ValueError: workers / chunksize 不合法; 或 checkpoint mismatch.
    """
    if workers < 1:
        raise ValueError(f"workers 必须 ≥ 1, 实际 {workers}")
    if chunksize < 1:
        raise ValueError(f"chunksize 必须 ≥ 1, 实际 {chunksize}")
    if start_index < 0:
        raise ValueError(f"start_index 必须 ≥ 0, 实际 {start_index}")
    if checkpoint is None:
        checkpoint = make_initial_checkpoint(seed=evaluator_seed,
                                              evaluator_kind="fake_pool")
    expected_domain_hash = _hash_domain(q_space_descriptor())
    if checkpoint.schema != CHECKPOINT_SCHEMA:
        raise ValueError(
            f"checkpoint schema mismatch: 当前 {CHECKPOINT_SCHEMA}, "
            f"文件 {checkpoint.schema}")
    if checkpoint.domain_hash != expected_domain_hash:
        raise ValueError(
            f"checkpoint domain_hash mismatch: 当前 {expected_domain_hash}, "
            f"文件 {checkpoint.domain_hash}")
    completed_set = {i for (i, _, _) in checkpoint.completed}
    todo: List[Tuple[int, Tuple[float, float, float, float]]] = []
    for offset, cand in enumerate(candidates):
        idx = start_index + offset
        if idx in completed_set:
            continue
        todo.append((idx, cand))
    if not todo:
        return list(checkpoint.completed), checkpoint
    args_list = [(idx, cand, evaluator_seed, sleep_s) for idx, cand in todo]
    # 启动进程池; chunksize 是 Pool 调度的最小批大小.
    ctx = multiprocessing.get_context("spawn")
    with ctx.Pool(processes=workers) as pool:
        results = pool.map(_pool_worker_eval, args_list, chunksize=chunksize)
    for idx, total, cand in results:
        checkpoint.completed.append((idx, total, cand))
        if total > checkpoint.best_total:
            checkpoint.best_total = total
            checkpoint.best_index = idx
    return list(checkpoint.completed), checkpoint


# =============================================================================
#  第七节: benchmark helper (TASK_004 Search §7)
# =============================================================================
def time_call(call: Callable[[], Any]) -> float:
    """单次 call 计时 (perf_counter). 不抛异常时返回 elapsed_s."""
    t0 = time.perf_counter()
    call()
    return time.perf_counter() - t0


def benchmark_summary(elapsed_list: Sequence[float],
                       ) -> Dict[str, float]:
    """统计一组 elapsed 时间序列的 summary."""
    if not elapsed_list:
        return {"n": 0, "min_s": 0.0, "max_s": 0.0,
                "mean_s": 0.0, "median_s": 0.0, "sum_s": 0.0}
    ts = list(elapsed_list)
    return {
        "n": len(ts),
        "min_s": min(ts),
        "max_s": max(ts),
        "mean_s": statistics.fmean(ts),
        "median_s": statistics.median(ts),
        "sum_s": sum(ts),
    }


# =============================================================================
#  第八节: 顶层入口 (TASK_004 Search §8)
# =============================================================================
def main(argv: Optional[Sequence[str]] = None) -> int:
    """Skeleton main: 仅打印版本, 不执行 Search."""
    print("Q2 SEARCH IMPLEMENTATION SKELETON (NOT AN OPTIMIZATION RESULT)")
    print("=" * 70)
    print("本入口仅打印骨架版本. 实际 Search 未运行.")
    print("如需跑 frozen benchmark:")
    print("  python -m tests.test_q2_search.benchmark_runner")
    return 0


if __name__ == "__main__":
    sys.exit(main())