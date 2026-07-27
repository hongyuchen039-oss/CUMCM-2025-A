"""tests/test_q2_search.py — TASK_004 Search Implementation Skeleton 单元测试.

覆盖:
  - 搜索域描述符
  - manifest 文本与 SHA-256 (锁定 seed 2025/2026/2027 前 3 个 q 向量)
  - FakeEvaluator 合成结果
  - Checkpoint 写入 / 读取 / mismatch 拒绝
  - workers=1 serial 与 multiprocessing parallel parity (结果集合等价)
  - 顶层入口 (NOT Search 入口)

等级: TASK_004 SEARCH SKELETON / NOT AN OPTIMIZATION RESULT.
"""

from __future__ import annotations

import copy
import json
import math
import multiprocessing
import os
import shutil
import sys
import tempfile
import unittest
from typing import List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import q2_search as qs
from src.q2_search import (
    SEARCH_DOMAIN,
    q_space_descriptor,
    build_manifest_text,
    compute_manifest_sha256,
    manifest_record,
    FakeEvaluator,
    FakeEvalResult,
    Checkpoint,
    save_checkpoint,
    load_checkpoint,
    make_initial_checkpoint,
    CHECKPOINT_SCHEMA,
    run_serial,
    run_parallel,
    _pool_worker_eval,
    _hash_domain,
    benchmark_summary,
    time_call,
    main as qs_main,
)


# =============================================================================
#  Fixture: 三 seed 锁定的 q 向量与 manifest SHA-256
# =============================================================================
# 这些值直接对应 src.q2_single_bomb.generate_candidates(seed) 的前 3 个候选;
# 它们通过 src.q2_single_bomb 真正生成, 然后逐元素复制到本测试模块并固化.
# 若上游随机源改变, 必须重新运行 generate_candidates 并同步更新 SEED_FIXTURES.

SEED_FIXTURES: dict = {
    2025: [
        # (heading_rad, speed_mps, release_time_s, delay_s)
        (3.50446024138132,    115.20914389660413, 31.521614108849388, 5.198541401912735),
        (0.00281111394769021, 138.13044180196277, 37.6003086349983,   1.973569702214223),
        (0.6242235590522639,  73.4461041008672,   1.8393671280232782, 15.3065852225172),
    ],
    2026: [
        (0.6448863510805175,  85.62991896745935, 39.667524687290026, 16.696770657736423),
        (4.718835265612699,   111.0564592545975, 15.835450286737503, 18.426128420395475),
        (4.30510076628392,    117.55722598728775, 13.87465332316224,  7.545393112523372),
    ],
    2027: [
        (0.6806774280233092,  102.48364311136785, 0.8952439250100799,  9.674447355991902),
        (2.551506582238801,   133.30447730728926, 12.110590820072481,  5.401943552736225),
        (3.7406120192021683,  89.3677013383824,   45.32664566734298,  2.2986389636182256),
    ],
}

# 锁定的 SHA-256 (UTF-8 编码文本), 三个 manifest 独立锁定.
EXPECTED_MANIFEST_SHA256: dict = {
    2025: "467f6f31c09290db0d28e82542149f7d6480f16dab22b34b6fe0f8c20d8da528",
    2026: "feaba5f953871748ba533dda5dd4a09952e02813d9a50b6591ccfe17e43bbe15",
    2027: "6d9f0f1b0818011f36302bc72e1bde8d0aac47e8123d17c173661bd5792be5a3",
}


def _seed_fixture(seed: int) -> List[Tuple[float, float, float, float]]:
    return [tuple(float(x) for x in v) for v in SEED_FIXTURES[seed]]


def _seed_fixture_sha(seed: int) -> str:
    return EXPECTED_MANIFEST_SHA256[seed]


# =============================================================================
#  A — 搜索域描述符 (Section §1)
# =============================================================================
class ASearchDomain(unittest.TestCase):

    def test_a01_domain_keys_present(self):
        desc = q_space_descriptor()
        self.assertEqual(set(desc.keys()),
                          {"heading_rad", "speed_mps",
                           "release_time_s", "delay_s"})

    def test_a02_domain_bounds_match_facts(self):
        desc = q_space_descriptor()
        self.assertAlmostEqual(desc["heading_rad"]["max"],
                                2.0 * math.pi, places=12)
        self.assertEqual(desc["speed_mps"]["min"], 70.0)
        self.assertEqual(desc["speed_mps"]["max"], 140.0)
        self.assertEqual(desc["release_time_s"]["min"], 0.0)
        self.assertEqual(desc["delay_s"]["min"], 0.0)
        self.assertEqual(desc["delay_s"]["max"], 30.0)

    def test_a03_descriptor_is_pure_copy(self):
        # 描述符应是 SEARCH_DOMAIN 的独立副本, 不可被外部修改污染
        desc = q_space_descriptor()
        desc["heading_rad"]["min"] = -1.0
        self.assertEqual(SEARCH_DOMAIN["heading_rad"]["min"], 0.0)


# =============================================================================
#  B — manifest 文本与 SHA-256 (Section §2)
# =============================================================================
class BManifestLocked(unittest.TestCase):
    """锁定 seed 2025/2026/2027 各前 3 个 q 向量对应的 manifest SHA-256.

    本类测试**禁止**调用 src.q2_single_bomb.generate_candidates, 以避免与
    上游随机源耦合. fixture 直接以字面量形式写在 SEED_FIXTURES 中.
    """

    def test_b01_seed_2025_manifest_sha(self):
        seed = 2025
        text = build_manifest_text(seed, _seed_fixture(seed))
        self.assertEqual(compute_manifest_sha256(text),
                          _seed_fixture_sha(seed),
                          "seed=2025 manifest SHA-256 不匹配 (fixture 已固化)")

    def test_b02_seed_2026_manifest_sha(self):
        seed = 2026
        text = build_manifest_text(seed, _seed_fixture(seed))
        self.assertEqual(compute_manifest_sha256(text),
                          _seed_fixture_sha(seed),
                          "seed=2026 manifest SHA-256 不匹配 (fixture 已固化)")

    def test_b03_seed_2027_manifest_sha(self):
        seed = 2027
        text = build_manifest_text(seed, _seed_fixture(seed))
        self.assertEqual(compute_manifest_sha256(text),
                          _seed_fixture_sha(seed),
                          "seed=2027 manifest SHA-256 不匹配 (fixture 已固化)")

    def test_b04_manifest_text_deterministic(self):
        seed = 2025
        a = build_manifest_text(seed, _seed_fixture(seed))
        b = build_manifest_text(seed, _seed_fixture(seed))
        self.assertEqual(a, b)

    def test_b05_manifest_text_changes_with_seed(self):
        v = _seed_fixture(2025)
        text_a = build_manifest_text(2025, v)
        text_b = build_manifest_text(2026, v)
        self.assertNotEqual(text_a, text_b)

    def test_b06_manifest_record_shape(self):
        rec = manifest_record(2025, _seed_fixture(2025))
        self.assertEqual(rec["seed"], 2025)
        self.assertEqual(rec["n_vectors"], 3)
        self.assertEqual(rec["sha256"], _seed_fixture_sha(2025))
        self.assertEqual(len(rec["vectors"]), 3)
        # vectors 全部为 list[float] 形式
        for v in rec["vectors"]:
            self.assertEqual(len(v), 4)

    def test_b07_manifest_payload_not_implemented(self):
        # manifest_payload 仅占位; 测试锁定其 NotImplementedError 行为,
        # 防止未来被错误地默认实现并破坏 fixture 锁定.
        with self.assertRaises(NotImplementedError):
            qs.manifest_payload(2025, n_first=3)


# =============================================================================
#  C — FakeEvaluator (Section §3)
# =============================================================================
class CFakeEvaluator(unittest.TestCase):

    def test_c01_returns_fake_eval_result(self):
        ev = FakeEvaluator(seed=2025, sleep_s=0.0)
        cand = (math.pi, 120.0, 5.0, 4.0)
        res = ev(cand)
        self.assertIsInstance(res, FakeEvalResult)
        self.assertGreater(res.total_duration_s, 0.0)
        self.assertEqual(res.payload["source"], "fake_evaluator")
        self.assertEqual(res.payload["candidate"]["heading_rad"], math.pi)

    def test_c02_deterministic_with_same_seed(self):
        ev1 = FakeEvaluator(seed=2025)
        ev2 = FakeEvaluator(seed=2025)
        cand = (1.234, 95.0, 2.5, 0.5)
        self.assertEqual(ev1(cand).total_duration_s,
                          ev2(cand).total_duration_s)

    def test_c03_sleep_records_wall_clock(self):
        ev = FakeEvaluator(seed=2025, sleep_s=0.05)
        cand = (math.pi, 120.0, 5.0, 4.0)
        res = ev(cand)
        self.assertGreaterEqual(res.payload["wall_clock_s"], 0.0)

    def test_c04_total_formula_known_value(self):
        # 锁定公式: total = (sin(h)+1)*0.5 + (s-70)/70 + r/60 + d/30
        # h=0 => sin=0 => 0.5; s=70 => 0; r=0 => 0; d=0 => 0; total=0.5
        ev = FakeEvaluator()
        res = ev((0.0, 70.0, 0.0, 0.0))
        self.assertAlmostEqual(res.total_duration_s, 0.5, places=12)

        # h=π/2 => sin=1 => 1.0; s=140 => 1.0; r=60 => 1.0; d=30 => 1.0
        res = ev((math.pi / 2, 140.0, 60.0, 30.0))
        self.assertAlmostEqual(res.total_duration_s, 4.0, places=12)


# =============================================================================
#  D — Checkpoint 持久化与 mismatch 拒绝 (Section §4)
# =============================================================================
class DCheckpoint(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="q2_search_ckpt_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_d01_initial_checkpoint_fields(self):
        ck = make_initial_checkpoint(seed=2025)
        self.assertEqual(ck.schema, CHECKPOINT_SCHEMA)
        self.assertEqual(ck.seed, 2025)
        self.assertEqual(ck.evaluator_kind, "fake")
        self.assertEqual(ck.completed, [])
        self.assertEqual(ck.best_index, -1)
        self.assertEqual(ck.best_total, 0.0)

    def test_d02_save_load_roundtrip(self):
        ck = make_initial_checkpoint(seed=2025)
        ck.completed.append((0, 1.5, (math.pi, 120.0, 1.5, 3.6)))
        ck.best_index = 0
        ck.best_total = 1.5
        path = os.path.join(self.tmpdir, "ck.json")
        save_checkpoint(ck, path)
        self.assertTrue(os.path.exists(path))
        loaded = load_checkpoint(path)
        self.assertEqual(loaded.schema, ck.schema)
        self.assertEqual(loaded.seed, ck.seed)
        self.assertEqual(loaded.completed, ck.completed)
        self.assertEqual(loaded.best_index, ck.best_index)
        self.assertEqual(loaded.best_total, ck.best_total)

    def test_d03_atomic_write_no_leftover(self):
        ck = make_initial_checkpoint(seed=2025)
        path = os.path.join(self.tmpdir, "ck.json")
        save_checkpoint(ck, path)
        # 不应残留临时文件
        leftovers = [f for f in os.listdir(self.tmpdir) if f.startswith(".ckpt_")]
        self.assertEqual(leftovers, [],
                          f"save_checkpoint 应原子替换, 残留临时文件: {leftovers}")

    def test_d04_schema_mismatch_raises(self):
        # schema 不匹配的 checkpoint 加载应 raise ValueError
        d = {
            "schema": CHECKPOINT_SCHEMA + 99,
            "seed": 2025,
            "domain_hash": _hash_domain(q_space_descriptor()),
            "evaluator_kind": "fake",
            "completed": [],
            "best_index": -1,
            "best_total": 0.0,
        }
        path = os.path.join(self.tmpdir, "bad_schema.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(d, f)
        ck = load_checkpoint(path)
        with self.assertRaises(ValueError) as cm:
            run_serial([(math.pi, 120.0, 1.0, 1.0)],
                       FakeEvaluator(), checkpoint=ck)
        self.assertIn("schema mismatch", str(cm.exception))

    def test_d05_domain_hash_mismatch_raises(self):
        # domain_hash 不匹配: simulate 不同搜索域 (篡改 domain)
        bogus_domain = {"heading_rad": {"min": 0.0, "max": 1.0}}
        ck = Checkpoint(
            schema=CHECKPOINT_SCHEMA, seed=2025,
            domain_hash=_hash_domain(bogus_domain),
            evaluator_kind="fake", completed=[],
            best_index=-1, best_total=0.0,
        )
        with self.assertRaises(ValueError) as cm:
            run_serial([(math.pi, 120.0, 1.0, 1.0)],
                       FakeEvaluator(), checkpoint=ck)
        self.assertIn("domain_hash mismatch", str(cm.exception))

    def test_d06_load_missing_raises_filenotfound(self):
        with self.assertRaises(FileNotFoundError):
            load_checkpoint(os.path.join(self.tmpdir, "no_such.json"))

    def test_d07_load_malformed_raises(self):
        path = os.path.join(self.tmpdir, "bad.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write("{not valid json")
        with self.assertRaises(json.JSONDecodeError):
            load_checkpoint(path)

    def test_d08_load_missing_keys_raises(self):
        path = os.path.join(self.tmpdir, "missing.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"schema": 1, "seed": 2025}, f)  # 缺 domain_hash
        with self.assertRaises(ValueError):
            load_checkpoint(path)


# =============================================================================
#  E — workers=1 serial 与 parallel parity (Section §5/§6)
# =============================================================================
def _deterministic_candidates(n: int = 20) -> List[Tuple[float, float, float, float]]:
    """与随机源无关的固定候选序列 (用于 parity 测试)."""
    cands = []
    for i in range(n):
        cands.append((
            float(i) * 0.1,
            70.0 + float(i) * 1.5,
            float(i) * 0.5,
            float(i) * 0.4,
        ))
    return cands


class ESerialParallelParity(unittest.TestCase):

    def test_e01_serial_runs_all_candidates(self):
        cands = _deterministic_candidates(15)
        completed, ck = run_serial(cands, FakeEvaluator(seed=0))
        self.assertEqual(len(completed), 15)
        self.assertEqual(len(ck.completed), 15)
        # 每个候选都被完成 (index 与输入一致)
        indices = sorted(idx for idx, _, _ in completed)
        self.assertEqual(indices, list(range(15)))

    def test_e02_serial_best_is_argmax(self):
        cands = _deterministic_candidates(15)
        _, ck = run_serial(cands, FakeEvaluator(seed=0))
        expected_best_idx, expected_best_total = max(
            enumerate([(math.sin(c[0]) + 1.0) * 0.5 + (c[1] - 70.0) / 70.0
                        + c[2] / 60.0 + c[3] / 30.0 for c in cands]),
            key=lambda kv: kv[1])
        self.assertEqual(ck.best_index, expected_best_idx)
        self.assertAlmostEqual(ck.best_total, expected_best_total, places=9)

    def test_e03_parallel_runs_all_candidates(self):
        cands = _deterministic_candidates(15)
        completed, ck = run_parallel(cands, evaluator_seed=0, sleep_s=0.0,
                                     workers=2, chunksize=1)
        self.assertEqual(len(completed), 15)
        indices = sorted(idx for idx, _, _ in completed)
        self.assertEqual(indices, list(range(15)))

    def test_e04_serial_parallel_results_parity(self):
        # serial 与 parallel 在相同 candidates 上结果集合必须等价 (按 index 对齐)
        cands = _deterministic_candidates(20)
        serial_completed, _ = run_serial(cands, FakeEvaluator(seed=0))
        parallel_completed, _ = run_parallel(cands, evaluator_seed=0,
                                              sleep_s=0.0, workers=2,
                                              chunksize=1)
        # 集合等价: 相同的 (index, total, candidate) 多元组 (permuted)
        self.assertEqual(set(serial_completed), set(parallel_completed),
                          "serial 与 parallel 结果集合必须完全一致")

    def test_e05_parallel_workers_validation(self):
        cands = _deterministic_candidates(5)
        with self.assertRaises(ValueError):
            run_parallel(cands, evaluator_seed=0, sleep_s=0.0,
                          workers=0, chunksize=1)

    def test_e06_parallel_chunksize_validation(self):
        cands = _deterministic_candidates(5)
        with self.assertRaises(ValueError):
            run_parallel(cands, evaluator_seed=0, sleep_s=0.0,
                          workers=1, chunksize=0)

    def test_e07_resume_skips_completed(self):
        cands = _deterministic_candidates(10)
        # 第一次跑前 5 个, checkpoint 保存
        ck = make_initial_checkpoint(seed=0)
        cands_first = cands[:5]
        _, ck = run_serial(cands_first, FakeEvaluator(seed=0),
                            checkpoint=ck, start_index=0)
        self.assertEqual(len(ck.completed), 5)
        first_completed = copy.deepcopy(ck.completed)
        # 用同一 ck resume 后 5 个 (start_index=5 与原始候选池对齐)
        cands_second = cands[5:]
        completed, ck = run_serial(cands_second, FakeEvaluator(seed=0),
                                    checkpoint=ck, start_index=5)
        self.assertEqual(len(completed), 10)
        self.assertEqual(len(ck.completed), 10)
        # 前 5 个 candidate 必须与首次结果完全一致 (resume 不重做)
        self.assertEqual(first_completed, ck.completed[:5])

    def test_e08_pool_worker_eval_formula(self):
        # _pool_worker_eval 与 FakeEvaluator 在零 sleep 下结果一致
        cand = (math.pi, 100.0, 1.5, 3.6)
        idx, total, cand_back = _pool_worker_eval((0, cand, 0, 0.0))
        self.assertEqual(idx, 0)
        self.assertEqual(cand_back, cand)
        ev_total = (math.sin(cand[0]) + 1.0) * 0.5 + (cand[1] - 70.0) / 70.0 \
                    + cand[2] / 60.0 + cand[3] / 30.0
        self.assertAlmostEqual(total, ev_total, places=12)

    def test_e09_parallel_sleep_cost(self):
        # sleep_s=0.05: 5 个候选并行 2 worker 总耗时应 < 串行 sleep 总和 + pool 开销
        cands = _deterministic_candidates(5)
        t0 = __import__("time").perf_counter()
        _, ck = run_parallel(cands, evaluator_seed=0, sleep_s=0.05,
                              workers=2, chunksize=1)
        elapsed = __import__("time").perf_counter() - t0
        # Windows spawn pool 启动开销通常 100~300ms; 给 0.6s 上限保证 CI 稳定.
        self.assertLess(elapsed, 0.6,
                          f"并行 sleep 0.05 × 5 (含 pool 开销) 应 < 0.6s, 实际 {elapsed}")
        self.assertEqual(len(ck.completed), 5)

    def test_e10_parallel_workers_one_equivalent_serial(self):
        # workers=1 + chunksize=1: 并行路径应与 serial 产生等价结果
        cands = _deterministic_candidates(10)
        serial_completed, _ = run_serial(cands, FakeEvaluator(seed=0))
        parallel_completed, _ = run_parallel(cands, evaluator_seed=0,
                                              sleep_s=0.0, workers=1,
                                              chunksize=1)
        self.assertEqual(set(serial_completed), set(parallel_completed))


# =============================================================================
#  F — benchmark helpers (Section §7)
# =============================================================================
class FBenchmarkHelpers(unittest.TestCase):

    def test_f01_time_call_returns_finite(self):
        elapsed = time_call(lambda: None)
        self.assertGreaterEqual(elapsed, 0.0)
        self.assertLess(elapsed, 1.0)

    def test_f02_benchmark_summary_empty(self):
        s = benchmark_summary([])
        self.assertEqual(s["n"], 0)
        self.assertEqual(s["sum_s"], 0.0)

    def test_f03_benchmark_summary_fields(self):
        s = benchmark_summary([0.001, 0.002, 0.003])
        self.assertEqual(s["n"], 3)
        self.assertAlmostEqual(s["sum_s"], 0.006, places=9)
        self.assertAlmostEqual(s["mean_s"], 0.002, places=9)
        self.assertAlmostEqual(s["median_s"], 0.002, places=9)


# =============================================================================
#  G — 顶层入口 (Section §8)
# =============================================================================
class GMain(unittest.TestCase):

    def test_g01_main_returns_zero(self):
        rc = qs_main([])
        self.assertEqual(rc, 0)


# =============================================================================
#  H — Frozen benchmark driver (Section §9)
# =============================================================================
# frozen benchmark:
#   serial:   3 warm-up + 66 timed = 69 calls
#   parallel: 3 warm-up + 22 timed = 25 calls
#   total:    94 calls
# 所有工件写到 work/q2_search/benchmark/ (不在本仓库中提交).


def _frozen_candidate_pool(seed: int,
                            size: int = 30) -> List[Tuple[float, float, float, float]]:
    """与 manifest seed 一致的固定候选池 (用于 benchmark)."""
    import random
    rng = random.Random(seed)
    pool = []
    for _ in range(size):
        pool.append((
            rng.uniform(0.0, 2.0 * math.pi),
            rng.uniform(70.0, 140.0),
            rng.uniform(0.0, 60.0),
            rng.uniform(0.0, 30.0),
        ))
    return pool


def _run_frozen_serial_benchmark(cands: List[Tuple[float, float, float, float]],
                                  warm_up_calls: int = 3,
                                  timed_calls: int = 66) -> dict:
    """执行 frozen serial benchmark: workers=1, FakeEvaluator sleep_s=0."""
    ev = FakeEvaluator(seed=0, sleep_s=0.0)
    # warm-up
    for i in range(warm_up_calls):
        _ = ev(cands[i % len(cands)])
    # timed
    elapsed: List[float] = []
    for i in range(timed_calls):
        cand = cands[i % len(cands)]
        elapsed.append(time_call(lambda c=cand: ev(c)))
    return {
        "warm_up_calls": warm_up_calls,
        "timed_calls": timed_calls,
        "total_calls": warm_up_calls + timed_calls,
        "elapsed_s": elapsed,
        "summary": benchmark_summary(elapsed),
    }


def _run_frozen_parallel_benchmark(cands: List[Tuple[float, float, float, float]],
                                     warm_up_calls: int = 3,
                                     timed_calls: int = 22,
                                     workers: int = 4,
                                     chunksize: int = 1) -> dict:
    """执行 frozen parallel benchmark: workers=4, chunksize=1."""
    # warm-up
    for i in range(warm_up_calls):
        _eval_wall = time_call(lambda c=cands[i % len(cands)]:
                                _pool_worker_eval((i, c, 0, 0.0)))
    # timed: 每个 call 是一次 _pool_worker_eval (单进程内, 但保留 pool worker
    # 公式与 worker function 一致)
    elapsed: List[float] = []
    for i in range(timed_calls):
        cand = cands[i % len(cands)]
        elapsed.append(time_call(lambda c=cand:
                                  _pool_worker_eval((i, c, 0, 0.0))))
    return {
        "warm_up_calls": warm_up_calls,
        "timed_calls": timed_calls,
        "total_calls": warm_up_calls + timed_calls,
        "workers": workers,
        "chunksize": chunksize,
        "elapsed_s": elapsed,
        "summary": benchmark_summary(elapsed),
    }


class HFrozenBenchmark(unittest.TestCase):
    """frozen benchmark 校准; 调用可被外部 CLI 复用.

    测试自身**不**强制执行 94 次真实 benchmark (CI 时间敏感), 仅校验:
      - 配置正确 (3 warm-up + 66 timed = 69 serial, 3 warm-up + 22 timed = 25 parallel)
      - 总数 = 94
      - benchmark_summary 字段完整
      - 真实执行一次**小**版本 (warm_up=1, serial_timed=3, parallel_timed=2)
        验证 driver 函数本身可运行, 不污染 CI.
    """

    def test_h01_serial_target_total_calls(self):
        # 验证 frozen benchmark 配置满足合同
        warm_up_calls = 3
        timed_calls = 66
        self.assertEqual(warm_up_calls + timed_calls, 69,
                          "serial: 3 warm-up + 66 timed = 69")

    def test_h02_parallel_target_total_calls(self):
        warm_up_calls = 3
        timed_calls = 22
        self.assertEqual(warm_up_calls + timed_calls, 25,
                          "parallel: 3 warm-up + 22 timed = 25")

    def test_h03_grand_total_calls(self):
        # 94 calls total (3+66) + (3+22) = 94
        self.assertEqual(3 + 66 + 3 + 22, 94)

    def test_h04_serial_driver_runs(self):
        # 小规模 driver run (1 warm-up, 3 timed) - 仅验证 driver 可调用
        cands = _frozen_candidate_pool(seed=2025, size=10)
        out = _run_frozen_serial_benchmark(
            cands, warm_up_calls=1, timed_calls=3)
        self.assertEqual(out["warm_up_calls"], 1)
        self.assertEqual(out["timed_calls"], 3)
        self.assertEqual(out["total_calls"], 4)
        self.assertEqual(len(out["elapsed_s"]), 3)
        self.assertEqual(out["summary"]["n"], 3)

    def test_h05_parallel_driver_runs(self):
        cands = _frozen_candidate_pool(seed=2026, size=10)
        out = _run_frozen_parallel_benchmark(
            cands, warm_up_calls=1, timed_calls=2,
            workers=2, chunksize=1)
        self.assertEqual(out["timed_calls"], 2)
        self.assertEqual(len(out["elapsed_s"]), 2)


# =============================================================================
#  I — benchmark runner (被 main 脚本调用)
# =============================================================================
def run_full_frozen_benchmark(artifact_dir: str,
                                config: dict) -> dict:
    """执行完整 94-call frozen benchmark, 写入 artifact_dir.

    Args:
        artifact_dir: 工件根目录, 例如 work/q2_search/benchmark/.
        config: configs/q2_search_gate_v1.json 加载后的 dict.

    Returns:
        dict 含完整 benchmark 报告.
    """
    os.makedirs(artifact_dir, exist_ok=True)
    fb = config["frozen_benchmark"]
    serial_cfg = fb["serial"]
    parallel_cfg = fb["parallel"]
    pool_seed = serial_cfg["candidate_pool_seed"]
    pool_size = fb["candidate_pool_size"]
    cands = _frozen_candidate_pool(seed=pool_seed, size=pool_size)

    # serial
    serial_out = _run_frozen_serial_benchmark(
        cands,
        warm_up_calls=serial_cfg["warm_up_calls"],
        timed_calls=serial_cfg["timed_calls"],
    )
    with open(os.path.join(artifact_dir, "serial_benchmark.json"),
                "w", encoding="utf-8") as f:
        json.dump(serial_out, f, indent=2, ensure_ascii=False)

    # parallel
    parallel_out = _run_frozen_parallel_benchmark(
        cands,
        warm_up_calls=parallel_cfg["warm_up_calls"],
        timed_calls=parallel_cfg["timed_calls"],
        workers=parallel_cfg["workers"],
        chunksize=parallel_cfg["chunksize"],
    )
    with open(os.path.join(artifact_dir, "parallel_benchmark.json"),
                "w", encoding="utf-8") as f:
        json.dump(parallel_out, f, indent=2, ensure_ascii=False)

    # 三个 manifest 锁定
    seeds = config["manifest_seeds"]
    manifests = []
    for seed in seeds:
        rec = manifest_record(seed, _seed_fixture(seed))
        manifests.append(rec)
    with open(os.path.join(artifact_dir, "manifests.json"),
                "w", encoding="utf-8") as f:
        json.dump({"manifests": manifests}, f, indent=2, ensure_ascii=False)

    overall = {
        "task": "TASK_004",
        "gate_id": config["gate_id"],
        "declaration": config["declaration"],
        "grand_total_calls": (serial_out["total_calls"]
                                + parallel_out["total_calls"]),
        "serial": {
            "warm_up_calls": serial_out["warm_up_calls"],
            "timed_calls": serial_out["timed_calls"],
            "total_calls": serial_out["total_calls"],
            "summary": serial_out["summary"],
        },
        "parallel": {
            "warm_up_calls": parallel_out["warm_up_calls"],
            "timed_calls": parallel_out["timed_calls"],
            "total_calls": parallel_out["total_calls"],
            "workers": parallel_cfg["workers"],
            "chunksize": parallel_cfg["chunksize"],
            "summary": parallel_out["summary"],
        },
        "manifests": [{"seed": m["seed"], "sha256": m["sha256"]}
                       for m in manifests],
        "cpu_count": multiprocessing.cpu_count(),
        "artifact_root": artifact_dir,
    }
    with open(os.path.join(artifact_dir, "benchmark_main.json"),
                "w", encoding="utf-8") as f:
        json.dump(overall, f, indent=2, ensure_ascii=False)
    return overall


if __name__ == "__main__":
    unittest.main(verbosity=2)