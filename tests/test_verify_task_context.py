"""Tests for TASK_GOV_002 verify_task_context.py.

All tests build a temporary git repository locally (no network, no global
git config, no modification of the user repo). The 'gh' CLI is mocked via
unittest.mock so the test is platform-agnostic.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from typing import Dict, Optional, Tuple
from unittest import mock

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(THIS_DIR)
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
sys.path.insert(0, SCRIPTS_DIR)

import verify_task_context as vtc  # noqa: E402


# ----------------------------- helpers ----------------------------------- #

def _run_git(*args: str, cwd: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=10,
    )


def _init_tmp_repo() -> Tuple[str, str]:
    """Create a temp git repo with a local bare 'origin' remote, make one
    commit, push to origin, return (tmpdir, head_sha)."""
    # Bare origin
    bare_dir = tempfile.mkdtemp(prefix="vtc_bare_")
    _run_git("init", "--bare", "-q", "--initial-branch=main", cwd=bare_dir)
    # Work repo
    tmp = tempfile.mkdtemp(prefix="vtc_test_repo_")
    _run_git("init", "-q", cwd=tmp)
    _run_git("config", "user.email", "vtc@test.local", cwd=tmp)
    _run_git("config", "user.name", "vtc-test", cwd=tmp)
    _run_git("checkout", "-q", "-b", "main", cwd=tmp)
    with open(os.path.join(tmp, "README.md"), "w") as f:
        f.write("init\n")
    _run_git("add", "README.md", cwd=tmp)
    _run_git("commit", "-q", "-m", "init", cwd=tmp)
    head = _run_git("rev-parse", "HEAD", cwd=tmp).stdout.strip()
    # Wire up local bare as 'origin' and push so origin/main exists
    _run_git("remote", "add", "origin", bare_dir, cwd=tmp)
    _run_git("push", "-q", "origin", "main", cwd=tmp)
    _run_git("branch", "--set-upstream-to=origin/main", cwd=tmp)
    # After the push, set the remote URL to the public GitHub URL so
    # the origin-URL check passes.  origin/main already exists locally
    # so the URL change does not affect tracking.
    _run_git("remote", "set-url", "origin",
             "https://github.com/hongyuchen039-oss/CUMCM-2025-A.git",
             cwd=tmp)
    # Stash bare_dir path on the tmp for cleanup
    setattr(_init_tmp_repo, "_bare_for_" + tmp, bare_dir)
    return tmp, head


def _cleanup_tmp_repo(tmp: str) -> None:
    bare = getattr(_init_tmp_repo, "_bare_for_" + tmp, None)
    if bare:
        shutil.rmtree(bare, ignore_errors=True)
        try:
            delattr(_init_tmp_repo, "_bare_for_" + tmp)
        except AttributeError:
            pass
    shutil.rmtree(tmp, ignore_errors=True)


def _base_context(tmp: str, head: str,
                  branch: str = "main",
                  pr_number: Optional[int] = None,
                  allowed_modified: Optional[list] = None,
                  allowed_untracked: Optional[list] = None,
                  forbidden: Optional[list] = None,
                  ) -> Dict:
    return {
        "schema_version": 1,
        "task_id": "TASK_TEST",
        "repository_full_name": "hongyuchen039-oss/CUMCM-2025-A",
        "worktree_path": tmp,
        "branch": branch,
        "expected_head": head,
        "base_branch": "main",
        "base_sha": head,
        "pr_number": pr_number,
        "pr_head_branch": branch,
        "allowed_modified_paths": allowed_modified or [],
        "allowed_untracked_paths": allowed_untracked or [],
        "forbidden_paths": forbidden or [],
    }


# ----------------------------- gh mock ----------------------------------- #

class _FakeGhProcess:
    """Subprocess.run replacement that intercepts 'gh pr view' and passes
    through to real subprocess for git and other commands. The real
    subprocess.run must be supplied as `real_run` to avoid recursion when
    the test has patched verify_task_context.subprocess.run."""

    def __init__(self, real_run, head_branch: str, head_sha: str,
                 cross_repo: bool = False,
                 fail: bool = False):
        self.real_run = real_run
        self.head_branch = head_branch
        self.head_sha = head_sha
        self.cross_repo = cross_repo
        self.fail = fail

    def __call__(self, args, **kwargs):
        # Only intercept 'gh pr view'; pass through everything else.
        if isinstance(args, (list, tuple)) and len(args) >= 1 \
                and args[0] == "gh":
            class _R:
                def __init__(self, payload, fail):
                    if fail:
                        self.stdout = ""
                        self.stderr = "GraphQL: Could not resolve"
                        self.returncode = 1
                    else:
                        self.stdout = json.dumps(payload)
                        self.stderr = ""
                        self.returncode = 0
            payload = {
                "headRefName": self.head_branch,
                "headRefOid": self.head_sha,
                "state": "OPEN",
                "isCrossRepository": self.cross_repo,
            }
            return _R(payload, self.fail)
        # Pass through to real subprocess (NOT the patched one)
        return self.real_run(args, **kwargs)


# ----------------------------- test class -------------------------------- #

class VerifyTaskContextTests(unittest.TestCase):

    # ---- 1. clean + identity all correct -> VALID_CLEAN ----
    def test_01_clean_and_all_identity_correct(self):
        tmp, head = _init_tmp_repo()
        try:
            ctx = _base_context(tmp, head)
            s = vtc.run_checks(ctx, cwd=tmp)
            self.assertEqual(s["status"], vtc.STATUS_VALID_CLEAN, s)
            self.assertEqual(s["violations"], [], s)
        finally:
            _cleanup_tmp_repo(tmp)

    # ---- 2. allowed tracked dirty -> VALID_AUTHORIZED_DIRTY ----
    def test_02_allowed_tracked_dirty(self):
        tmp, head = _init_tmp_repo()
        try:
            with open(os.path.join(tmp, "README.md"), "a") as f:
                f.write("\nmore\n")
            ctx = _base_context(tmp, head,
                                allowed_modified=["README.md"])
            s = vtc.run_checks(ctx, cwd=tmp)
            self.assertEqual(s["status"],
                             vtc.STATUS_VALID_AUTHORIZED_DIRTY, s)
            self.assertEqual(s["violations"], [], s)
        finally:
            _cleanup_tmp_repo(tmp)

    # ---- 3. allowed untracked work/ -> VALID_AUTHORIZED_DIRTY ----
    def test_03_allowed_untracked_work(self):
        tmp, head = _init_tmp_repo()
        try:
            os.makedirs(os.path.join(tmp, "work"), exist_ok=True)
            with open(os.path.join(tmp, "work", "u.txt"), "w") as f:
                f.write("u\n")
            ctx = _base_context(tmp, head,
                                allowed_untracked=["work/"])
            s = vtc.run_checks(ctx, cwd=tmp)
            self.assertEqual(s["status"],
                             vtc.STATUS_VALID_AUTHORIZED_DIRTY, s)
            self.assertEqual(s["violations"], [], s)
        finally:
            _cleanup_tmp_repo(tmp)

    # ---- 4. wrong worktree_path -> INVALID ----
    def test_04_wrong_worktree_path(self):
        tmp, head = _init_tmp_repo()
        try:
            ctx = _base_context(tmp, head)
            ctx["worktree_path"] = "C:/definitely/not/the/real/path"
            s = vtc.run_checks(ctx, cwd=tmp)
            self.assertEqual(s["status"], vtc.STATUS_INVALID, s)
            self.assertTrue(any("worktree_path mismatch" in v
                                for v in s["violations"]), s)
        finally:
            _cleanup_tmp_repo(tmp)

    # ---- 5. wrong branch -> INVALID ----
    def test_05_wrong_branch(self):
        tmp, head = _init_tmp_repo()
        try:
            ctx = _base_context(tmp, head, branch="some-other-branch")
            s = vtc.run_checks(ctx, cwd=tmp)
            self.assertEqual(s["status"], vtc.STATUS_INVALID, s)
            self.assertTrue(any("branch mismatch" in v
                                for v in s["violations"]), s)
        finally:
            _cleanup_tmp_repo(tmp)

    # ---- 6. detached HEAD -> INVALID ----
    def test_06_detached_head(self):
        tmp, head = _init_tmp_repo()
        try:
            _run_git("checkout", "--detach", "-q", head, cwd=tmp)
            ctx = _base_context(tmp, head)
            s = vtc.run_checks(ctx, cwd=tmp)
            self.assertEqual(s["status"], vtc.STATUS_INVALID, s)
            self.assertTrue(any("detached HEAD" in v
                                for v in s["violations"]), s)
        finally:
            _cleanup_tmp_repo(tmp)

    # ---- 7. wrong expected_head -> INVALID ----
    def test_07_wrong_expected_head(self):
        tmp, head = _init_tmp_repo()
        try:
            ctx = _base_context(tmp, head)
            ctx["expected_head"] = "0" * 40
            s = vtc.run_checks(ctx, cwd=tmp)
            self.assertEqual(s["status"], vtc.STATUS_INVALID, s)
            self.assertTrue(any("HEAD mismatch" in v
                                for v in s["violations"]), s)
        finally:
            _cleanup_tmp_repo(tmp)

    # ---- 8. unexpected modified file -> INVALID ----
    def test_08_unexpected_modified_file(self):
        tmp, head = _init_tmp_repo()
        try:
            with open(os.path.join(tmp, "README.md"), "a") as f:
                f.write("\nmore\n")
            ctx = _base_context(tmp, head, allowed_modified=[])
            s = vtc.run_checks(ctx, cwd=tmp)
            self.assertEqual(s["status"], vtc.STATUS_INVALID, s)
            self.assertTrue(any(
                "modified file outside allowed_modified_paths" in v
                for v in s["violations"]), s)
        finally:
            _cleanup_tmp_repo(tmp)

    # ---- 9. forbidden path modified -> INVALID ----
    def test_09_forbidden_path_modified(self):
        tmp, head = _init_tmp_repo()
        try:
            with open(os.path.join(tmp, "RESULTS.md"), "w") as f:
                f.write("x\n")
            _run_git("add", "RESULTS.md", cwd=tmp)
            _run_git("commit", "-q", "-m", "add", cwd=tmp)
            new_head = _run_git("rev-parse", "HEAD", cwd=tmp).stdout.strip()
            # update origin so tracking is consistent
            _run_git("push", "-q", "origin", "main", cwd=tmp)
            _run_git("branch", "--set-upstream-to=origin/main", cwd=tmp)
            with open(os.path.join(tmp, "RESULTS.md"), "a") as f:
                f.write("y\n")
            ctx = _base_context(tmp, new_head, forbidden=["RESULTS.md"])
            s = vtc.run_checks(ctx, cwd=tmp)
            self.assertEqual(s["status"], vtc.STATUS_INVALID, s)
            self.assertTrue(any("forbidden path" in v
                                for v in s["violations"]), s)
        finally:
            _cleanup_tmp_repo(tmp)

    # ---- 10. staged file -> INVALID ----
    def test_10_staged_file_rejected(self):
        tmp, head = _init_tmp_repo()
        try:
            with open(os.path.join(tmp, "README.md"), "a") as f:
                f.write("\nmore\n")
            _run_git("add", "README.md", cwd=tmp)
            ctx = _base_context(tmp, head)
            s = vtc.run_checks(ctx, cwd=tmp)
            self.assertEqual(s["status"], vtc.STATUS_INVALID, s)
            self.assertTrue(any("staged files" in v
                                for v in s["violations"]), s)
        finally:
            _cleanup_tmp_repo(tmp)

    # ---- 11. merge conflict -> INVALID ----
    def test_11_merge_conflict_detected(self):
        tmp, head = _init_tmp_repo()
        try:
            _run_git("checkout", "-q", "-b", "feat", cwd=tmp)
            with open(os.path.join(tmp, "README.md"), "w") as f:
                f.write("feature\n")
            _run_git("commit", "-q", "-am", "feat", cwd=tmp)
            _run_git("checkout", "-q", "main", cwd=tmp)
            with open(os.path.join(tmp, "README.md"), "w") as f:
                f.write("main\n")
            _run_git("commit", "-q", "-am", "main", cwd=tmp)
            # Force conflict markers in working tree, then add to index
            with open(os.path.join(tmp, "README.md"), "w") as f:
                f.write("<<<<<<< HEAD\nmain\n=======\nfeature\n>>>>>>> feat\n")
            _run_git("add", "README.md", cwd=tmp)
            ctx = _base_context(tmp, head)
            s = vtc.run_checks(ctx, cwd=tmp)
            self.assertEqual(s["status"], vtc.STATUS_INVALID, s)
        finally:
            _cleanup_tmp_repo(tmp)

    # ---- 12. malformed / missing context -> fail closed ----
    def test_12a_missing_context_file(self):
        with self.assertRaises(vtc.ContextError):
            vtc._load_context("/definitely/not/a/real/path.json")

    def test_12b_malformed_json(self):
        with tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8",
        ) as f:
            f.write("{not valid json")
            path = f.name
        try:
            with self.assertRaises(vtc.ContextError):
                vtc._load_context(path)
        finally:
            os.unlink(path)

    def test_12c_missing_required_field(self):
        with tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8",
        ) as f:
            json.dump({"schema_version": 1, "task_id": "T"}, f)
            path = f.name
        try:
            with self.assertRaises(vtc.ContextError):
                vtc._load_context(path)
        finally:
            os.unlink(path)

    def test_12d_main_returns_unavailable_for_missing(self):
        rc = vtc.main(["--context", "/no/such/file.json"])
        self.assertEqual(rc, vtc.RC_UNAVAILABLE)

    # ---- 13. origin remote mismatch -> INVALID ----
    def test_13_origin_remote_mismatch(self):
        tmp, head = _init_tmp_repo()
        try:
            _run_git("remote", "set-url", "origin",
                     "https://github.com/some-other/repo.git", cwd=tmp)
            ctx = _base_context(tmp, head)
            s = vtc.run_checks(ctx, cwd=tmp)
            self.assertEqual(s["status"], vtc.STATUS_INVALID, s)
            self.assertTrue(any("origin remote URL" in v
                                for v in s["violations"]), s)
        finally:
            _cleanup_tmp_repo(tmp)

    # ---- 14. pr_number set, mock gh returns mismatched PR -> INVALID ----
    def test_14_pr_number_branch_sha_mismatch_via_fake_gh(self):
        tmp, head = _init_tmp_repo()
        try:
            fake = _FakeGhProcess(
                real_run=subprocess.run,
                head_branch="WRONG_BRANCH", head_sha="f" * 40,
            )
            with mock.patch("verify_task_context.subprocess.run",
                            side_effect=fake):
                ctx = _base_context(tmp, head, pr_number=42)
                s = vtc.run_checks(ctx, cwd=tmp)
            self.assertEqual(s["status"], vtc.STATUS_INVALID, s)
            joined = " | ".join(s["violations"])
            self.assertTrue(
                "pr head branch" in joined or "pr head SHA" in joined,
                f"unexpected violations: {s['violations']}",
            )
        finally:
            _cleanup_tmp_repo(tmp)

    def test_14b_pr_number_match_via_fake_gh(self):
        tmp, head = _init_tmp_repo()
        try:
            fake = _FakeGhProcess(real_run=subprocess.run,
                                  head_branch="main", head_sha=head)
            with mock.patch("verify_task_context.subprocess.run",
                            side_effect=fake):
                ctx = _base_context(tmp, head, pr_number=42)
                s = vtc.run_checks(ctx, cwd=tmp)
            self.assertEqual(s["status"], vtc.STATUS_VALID_CLEAN, s)
        finally:
            _cleanup_tmp_repo(tmp)

    def test_14c_pr_number_cross_repo(self):
        tmp, head = _init_tmp_repo()
        try:
            fake = _FakeGhProcess(real_run=subprocess.run,
                                  head_branch="main", head_sha=head,
                                  cross_repo=True)
            with mock.patch("verify_task_context.subprocess.run",
                            side_effect=fake):
                ctx = _base_context(tmp, head, pr_number=42)
                s = vtc.run_checks(ctx, cwd=tmp)
            self.assertEqual(s["status"], vtc.STATUS_INVALID, s)
            self.assertTrue(any("cross-repository" in v
                                for v in s["violations"]), s)
        finally:
            _cleanup_tmp_repo(tmp)

    # ---- 15. Windows path normalization ----
    def test_15_windows_path_normalization(self):
        a = "C:/Users/Test/repo"
        b = "c:\\users\\test\\repo"
        self.assertEqual(vtc._normalize_path(a), vtc._normalize_path(b))
        c = "C:/Users/Test/other"
        self.assertNotEqual(vtc._normalize_path(a), vtc._normalize_path(c))
        d = "C:/Users/Test/repo/sub/file.txt"
        self.assertTrue(vtc._is_path_under(
            vtc._normalize_path(d), vtc._normalize_path(b),
        ))
        self.assertFalse(vtc._is_path_under(
            vtc._normalize_path(c), vtc._normalize_path(b),
        ))

    # ---- additional: untracked not in allowed -> INVALID ----
    def test_16_untracked_outside_allowed(self):
        tmp, head = _init_tmp_repo()
        try:
            with open(os.path.join(tmp, "stray.txt"), "w") as f:
                f.write("x\n")
            ctx = _base_context(tmp, head, allowed_untracked=["work/"])
            s = vtc.run_checks(ctx, cwd=tmp)
            self.assertEqual(s["status"], vtc.STATUS_INVALID, s)
            self.assertTrue(any("untracked file outside" in v
                                for v in s["violations"]), s)
        finally:
            _cleanup_tmp_repo(tmp)

    # ---- additional: main() returns proper rc on VALID ----
    def test_17_main_returns_zero_on_valid(self):
        tmp, head = _init_tmp_repo()
        # Write ctx.json to a temp dir OUTSIDE the worktree so the worktree
        # stays clean.  This mirrors the real production setup where the
        # runtime lock lives in work/task_context.json (gitignored) and
        # the user passes it via --context.
        ctx_dir = tempfile.mkdtemp(prefix="vtc_ctx_")
        try:
            ctx = _base_context(tmp, head)
            ctx_path = os.path.join(ctx_dir, "task_context.json")
            with open(ctx_path, "w") as f:
                json.dump(ctx, f)
            rc = vtc.main(["--context", ctx_path, "--cwd", tmp])
            self.assertEqual(rc, vtc.RC_VALID)
        finally:
            shutil.rmtree(ctx_dir, ignore_errors=True)
            _cleanup_tmp_repo(tmp)


if __name__ == "__main__":
    unittest.main()
