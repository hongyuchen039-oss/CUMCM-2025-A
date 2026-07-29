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

# Ensure subprocess.run(..., text=True) decodes UTF-8 regardless of
# Windows / locale code page (e.g. cp1252 / gbk).  Without this,
# Git's UTF-8 output for non-ASCII filenames would raise
# UnicodeDecodeError before reaching the porcelain parser.
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUTF8", "1")

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(THIS_DIR)
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
sys.path.insert(0, SCRIPTS_DIR)

import verify_task_context as vtc  # noqa: E402


# ----------------------------- helpers ----------------------------------- #

def _run_git(*args: str, cwd: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True,
        errors="replace", timeout=10,
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
                 base_branch: str = "main", base_sha: str = "",
                 cross_repo: bool = False,
                 fail: bool = False):
        self.real_run = real_run
        self.head_branch = head_branch
        self.head_sha = head_sha
        self.base_branch = base_branch
        self.base_sha = base_sha or head_sha
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
                "baseRefName": self.base_branch,
                "baseRefOid": self.base_sha,
                "state": "OPEN",
                "isCrossRepository": self.cross_repo,
                "url": "https://github.com/foo/bar/pull/42",
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
            self.assertTrue(any("detached" in v
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
            # Real git merge.  When the index shows UU, git writes
            # conflict markers to the working tree and the merge
            # exits with non-zero.  We do NOT manually pre-write
            # markers — the unmerged state must come from the merge.
            # Use --no-commit WITHOUT --no-ff so HEAD does not advance
            # when the merge conflict is held open in the index.
            r = _run_git("merge", "--no-commit", "feat", cwd=tmp)
            self.assertNotEqual(r.returncode, 0, r)
            # Confirm the actual UU is in the porcelain -z output.
            r2 = _run_git("status", "--porcelain", "-z", cwd=tmp)
            self.assertIn("UU", r2.stdout, r2.stdout)
            ctx = _base_context(tmp, head)
            s = vtc.run_checks(ctx, cwd=tmp)
            self.assertEqual(s["status"], vtc.STATUS_INVALID, s)
            self.assertTrue(any("unmerged/conflict" in v
                                for v in s["violations"]), s)
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
                                  head_branch="main", head_sha=head,
                                  base_branch="main", base_sha=head)
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
                                  base_branch="main", base_sha=head,
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


# ============================================================================
# Category A — P1 closure tests
# ============================================================================
class P1ClosureTests(unittest.TestCase):

    def test_a01_base_sha_correct_allows_continue(self):
        tmp, head = _init_tmp_repo()
        try:
            ctx = _base_context(tmp, head)
            s = vtc.run_checks(ctx, cwd=tmp)
            self.assertEqual(s["status"], vtc.STATUS_VALID_CLEAN, s)
            self.assertEqual(s["base_sha_actual"], head, s)
            self.assertEqual(s["base_sha_expected"], head, s)
        finally:
            _cleanup_tmp_repo(tmp)

    def test_a02_wrong_base_sha_rc2(self):
        tmp, head = _init_tmp_repo()
        try:
            ctx = _base_context(tmp, head)
            ctx["base_sha"] = "f" * 40
            s = vtc.run_checks(ctx, cwd=tmp)
            self.assertEqual(s["status"], vtc.STATUS_INVALID, s)
            self.assertTrue(any("base_sha mismatch" in v
                                for v in s["violations"]), s)
        finally:
            _cleanup_tmp_repo(tmp)

    def test_a03_base_ref_unresolvable_rc3(self):
        tmp, head = _init_tmp_repo()
        try:
            # Remove origin remote so origin/main is unresolvable
            _run_git("remote", "remove", "origin", cwd=tmp)
            ctx = _base_context(tmp, head)
            s = vtc.run_checks(ctx, cwd=tmp)
            self.assertEqual(s["status"], vtc.STATUS_INVALID, s)
            self.assertTrue(s["dependency_unavailable"], s)
            self.assertTrue(any("base tracking ref" in v
                                for v in s["violations"]), s)
        finally:
            _cleanup_tmp_repo(tmp)

    def test_a04_git_status_nonzero_rc3(self):
        tmp, head = _init_tmp_repo()
        try:
            ctx = _base_context(tmp, head)
            # Force `git status` to return non-zero by removing .git
            # and pointing cwd to the now-broken repo via a sub-shell
            # wrapper.  Easier: monkey-patch _git to fake a nonzero rc.
            orig_git = vtc._git
            def fake_git(*args, **kwargs):
                if args and args[0] == "status":
                    return (128, "", "fatal: not a git repository")
                return orig_git(*args, **kwargs)
            with mock.patch.object(vtc, "_git", new=fake_git):
                s = vtc.run_checks(ctx, cwd=tmp)
            self.assertEqual(s["status"], vtc.STATUS_INVALID, s)
            self.assertTrue(s["dependency_unavailable"], s)
            self.assertTrue(any("git status" in v
                                for v in s["violations"]), s)
        finally:
            _cleanup_tmp_repo(tmp)

    def test_a05_git_status_timeout_rc3(self):
        tmp, head = _init_tmp_repo()
        try:
            ctx = _base_context(tmp, head)
            orig_git = vtc._git
            def fake_git(*args, **kwargs):
                if args and args[0] == "status":
                    raise vtc._GitUnavailable("git status timeout (5s)")
                return orig_git(*args, **kwargs)
            with mock.patch.object(vtc, "_git", new=fake_git):
                s = vtc.run_checks(ctx, cwd=tmp)
            self.assertEqual(s["status"], vtc.STATUS_INVALID, s)
            self.assertTrue(s["dependency_unavailable"], s)
        finally:
            _cleanup_tmp_repo(tmp)

    def test_a06_git_status_malformed_rc3(self):
        tmp, head = _init_tmp_repo()
        try:
            ctx = _base_context(tmp, head)
            orig_git = vtc._git
            def fake_git(*args, **kwargs):
                if args and args[0] == "status":
                    return (0, "X\n", "")  # 1-char entry → too-short
                return orig_git(*args, **kwargs)
            with mock.patch.object(vtc, "_git", new=fake_git):
                s = vtc.run_checks(ctx, cwd=tmp)
            self.assertEqual(s["status"], vtc.STATUS_INVALID, s)
            self.assertTrue(s["dependency_unavailable"], s)
        finally:
            _cleanup_tmp_repo(tmp)

    def test_a07_pr_wrong_base_branch_rc2(self):
        tmp, head = _init_tmp_repo()
        try:
            fake = _FakeGhProcess(real_run=subprocess.run,
                                  head_branch="main", head_sha=head,
                                  base_branch="OTHER", base_sha=head)
            with mock.patch("verify_task_context.subprocess.run",
                            side_effect=fake):
                ctx = _base_context(tmp, head, pr_number=42)
                s = vtc.run_checks(ctx, cwd=tmp)
            self.assertEqual(s["status"], vtc.STATUS_INVALID, s)
            self.assertTrue(any("pr base branch" in v
                                for v in s["violations"]), s)
        finally:
            _cleanup_tmp_repo(tmp)

    def test_a08_pr_wrong_base_sha_rc2(self):
        tmp, head = _init_tmp_repo()
        try:
            fake = _FakeGhProcess(real_run=subprocess.run,
                                  head_branch="main", head_sha=head,
                                  base_branch="main",
                                  base_sha="f" * 40)
            with mock.patch("verify_task_context.subprocess.run",
                            side_effect=fake):
                ctx = _base_context(tmp, head, pr_number=42)
                s = vtc.run_checks(ctx, cwd=tmp)
            self.assertEqual(s["status"], vtc.STATUS_INVALID, s)
            self.assertTrue(any("pr base SHA" in v
                                for v in s["violations"]), s)
        finally:
            _cleanup_tmp_repo(tmp)

    def test_a09_pr_wrong_head_branch_rc2(self):
        tmp, head = _init_tmp_repo()
        try:
            fake = _FakeGhProcess(real_run=subprocess.run,
                                  head_branch="OTHER", head_sha=head,
                                  base_branch="main", base_sha=head)
            with mock.patch("verify_task_context.subprocess.run",
                            side_effect=fake):
                ctx = _base_context(tmp, head, pr_number=42)
                s = vtc.run_checks(ctx, cwd=tmp)
            self.assertEqual(s["status"], vtc.STATUS_INVALID, s)
            self.assertTrue(any("pr head branch" in v
                                for v in s["violations"]), s)
        finally:
            _cleanup_tmp_repo(tmp)

    def test_a10_pr_wrong_head_sha_rc2(self):
        tmp, head = _init_tmp_repo()
        try:
            fake = _FakeGhProcess(real_run=subprocess.run,
                                  head_branch="main", head_sha="f" * 40,
                                  base_branch="main", base_sha=head)
            with mock.patch("verify_task_context.subprocess.run",
                            side_effect=fake):
                ctx = _base_context(tmp, head, pr_number=42)
                s = vtc.run_checks(ctx, cwd=tmp)
            self.assertEqual(s["status"], vtc.STATUS_INVALID, s)
            self.assertTrue(any("pr head SHA" in v
                                for v in s["violations"]), s)
        finally:
            _cleanup_tmp_repo(tmp)

    def test_a11_pr_cross_repository_rc2(self):
        tmp, head = _init_tmp_repo()
        try:
            fake = _FakeGhProcess(real_run=subprocess.run,
                                  head_branch="main", head_sha=head,
                                  base_branch="main", base_sha=head,
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

    def test_a12_gh_command_contains_repo_flag(self):
        tmp, head = _init_tmp_repo()
        try:
            real_run = subprocess.run
            captured = {"args": None, "cwd": None}

            class _R:
                returncode = 0
                stdout = json.dumps({
                    "headRefName": "main", "headRefOid": head,
                    "baseRefName": "main", "baseRefOid": head,
                    "state": "OPEN", "isCrossRepository": False,
                    "url": "x",
                })
                stderr = ""

            def fake_run(args, **kwargs):
                if args and args[0] == "gh":
                    captured["args"] = list(args)
                    captured["cwd"] = kwargs.get("cwd")
                    return _R()
                return real_run(args, **kwargs)

            with mock.patch("verify_task_context.subprocess.run",
                            side_effect=fake_run):
                ctx = _base_context(tmp, head, pr_number=42)
                vtc.run_checks(ctx, cwd=tmp)
            # gh pr view must include --repo and the right repo name
            self.assertIsNotNone(captured["args"], "gh was not called")
            self.assertIn("--repo", captured["args"])
            self.assertIn("hongyuchen039-oss/CUMCM-2025-A", captured["args"])
        finally:
            _cleanup_tmp_repo(tmp)

    def test_a13_gh_cwd_is_repo_root(self):
        tmp, head = _init_tmp_repo()
        try:
            real_run = subprocess.run
            captured = {"cwd": None}

            class _R:
                returncode = 0
                stdout = json.dumps({
                    "headRefName": "main", "headRefOid": head,
                    "baseRefName": "main", "baseRefOid": head,
                    "state": "OPEN", "isCrossRepository": False,
                    "url": "x",
                })
                stderr = ""

            def fake_run(args, **kwargs):
                if args and args[0] == "gh":
                    captured["cwd"] = kwargs.get("cwd")
                    return _R()
                return real_run(args, **kwargs)

            with mock.patch("verify_task_context.subprocess.run",
                            side_effect=fake_run):
                ctx = _base_context(tmp, head, pr_number=42)
                vtc.run_checks(ctx, cwd=tmp)
            self.assertEqual(vtc._normalize_path(captured["cwd"]),
                             vtc._normalize_path(tmp))
        finally:
            _cleanup_tmp_repo(tmp)

    def test_a14_gh_unavailable_rc3(self):
        tmp, head = _init_tmp_repo()
        try:
            # Make shutil.which('gh') return None
            with mock.patch.object(vtc.shutil, "which",
                                   return_value=None):
                ctx = _base_context(tmp, head, pr_number=42)
                s = vtc.run_checks(ctx, cwd=tmp)
            self.assertEqual(s["status"], vtc.STATUS_INVALID, s)
            self.assertTrue(s["dependency_unavailable"], s)
            self.assertTrue(any("gh" in v.lower()
                                for v in s["violations"]), s)
        finally:
            _cleanup_tmp_repo(tmp)

    def test_a15_gh_timeout_rc3(self):
        tmp, head = _init_tmp_repo()
        try:
            with mock.patch.object(
                vtc, "_gh_pr_view",
                side_effect=vtc._GitUnavailable("gh pr view timeout (5s)"),
            ):
                ctx = _base_context(tmp, head, pr_number=42)
                s = vtc.run_checks(ctx, cwd=tmp)
            self.assertEqual(s["status"], vtc.STATUS_INVALID, s)
            self.assertTrue(s["dependency_unavailable"], s)
        finally:
            _cleanup_tmp_repo(tmp)

    def test_a16_gh_nonzero_rc3(self):
        tmp, head = _init_tmp_repo()
        try:
            real_run = subprocess.run
            class _R:
                returncode = 1
                stdout = ""
                stderr = "not logged in"
            def fake_run(args, **kwargs):
                if args and args[0] == "gh":
                    return _R()
                return real_run(args, **kwargs)
            with mock.patch("verify_task_context.subprocess.run",
                            side_effect=fake_run):
                ctx = _base_context(tmp, head, pr_number=42)
                s = vtc.run_checks(ctx, cwd=tmp)
            self.assertEqual(s["status"], vtc.STATUS_INVALID, s)
            self.assertTrue(s["dependency_unavailable"], s)
        finally:
            _cleanup_tmp_repo(tmp)

    def test_a17_gh_invalid_json_rc3(self):
        tmp, head = _init_tmp_repo()
        try:
            real_run = subprocess.run
            class _R:
                returncode = 0
                stdout = "not json"
                stderr = ""
            def fake_run(args, **kwargs):
                if args and args[0] == "gh":
                    return _R()
                return real_run(args, **kwargs)
            with mock.patch("verify_task_context.subprocess.run",
                            side_effect=fake_run):
                ctx = _base_context(tmp, head, pr_number=42)
                s = vtc.run_checks(ctx, cwd=tmp)
            self.assertEqual(s["status"], vtc.STATUS_INVALID, s)
            self.assertTrue(s["dependency_unavailable"], s)
        finally:
            _cleanup_tmp_repo(tmp)


# ============================================================================
# Category B — Git state tests
# ============================================================================
class GitStateTests(unittest.TestCase):

    def test_b01_staged_rename_with_space(self):
        tmp, head = _init_tmp_repo()
        try:
            # Create a file with space in name, commit, rename
            old = os.path.join(tmp, "old name.md")
            with open(old, "w") as f:
                f.write("x\n")
            _run_git("add", "old name.md", cwd=tmp)
            _run_git("commit", "-q", "-m", "add", cwd=tmp)
            new_head = _run_git("rev-parse", "HEAD", cwd=tmp).stdout.strip()
            _run_git("push", "-q", "origin", "main", cwd=tmp)
            _run_git("branch", "--set-upstream-to=origin/main", cwd=tmp)
            new = os.path.join(tmp, "new name.md")
            os.rename(old, new)
            _run_git("add", "-A", cwd=tmp)
            ctx = _base_context(tmp, new_head)
            s = vtc.run_checks(ctx, cwd=tmp)
            self.assertEqual(s["status"], vtc.STATUS_INVALID, s)
            self.assertTrue(any("staged" in v for v in s["violations"]), s)
        finally:
            _cleanup_tmp_repo(tmp)

    def test_b02_staged_rename_with_unicode(self):
        tmp, head = _init_tmp_repo()
        try:
            old = os.path.join(tmp, "原文件.md")
            with open(old, "w", encoding="utf-8") as f:
                f.write("x\n")
            _run_git("add", "原文件.md", cwd=tmp)
            _run_git("commit", "-q", "-m", "add", cwd=tmp)
            new_head = _run_git("rev-parse", "HEAD", cwd=tmp).stdout.strip()
            _run_git("push", "-q", "origin", "main", cwd=tmp)
            _run_git("branch", "--set-upstream-to=origin/main", cwd=tmp)
            new = os.path.join(tmp, "新文件.md")
            os.rename(old, new)
            _run_git("add", "-A", cwd=tmp)
            ctx = _base_context(tmp, new_head)
            s = vtc.run_checks(ctx, cwd=tmp)
            self.assertEqual(s["status"], vtc.STATUS_INVALID, s)
        finally:
            _cleanup_tmp_repo(tmp)

    def test_b03_parser_consumes_two_null_paths(self):
        # Simulate a rename entry in porcelain -z and check parser
        # produces a renamed record rather than treating the source
        # as a separate status entry. Per git's contract the FIRST
        # NUL record carries the destination; the SECOND carries the
        # source. Summary must record 'source -> destination'.
        raw = "R  old\0new\0"
        out = vtc._parse_porcelain_z(raw)
        self.assertIn("new -> old", out["renamed"])
        # The source ('new') must NOT be misinterpreted as a
        # separate status entry.  (It is staged as part of the
        # rename endpoint tracking, not as modified/untracked/...)
        self.assertNotIn("new", out["modified"])
        self.assertNotIn("new", out["untracked"])
        self.assertNotIn("new", out["conflict"])
        self.assertNotIn("new", out["deleted"])

    def test_b04_real_merge_produces_unmerged_index(self):
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
            # Force conflict markers and DON'T add to index
            with open(os.path.join(tmp, "README.md"), "w") as f:
                f.write("<<<<<<< HEAD\nmain\n=======\nfeature\n>>>>>>> feat\n")
            # Get a real UU status via git add (or use the conflict
            # markers which git will mark as unmerged)
            _run_git("add", "README.md", cwd=tmp)
            # The status should be either UU (unmerged) or staged
            r = _run_git("status", "--porcelain", cwd=tmp)
            self.assertIn("README.md", r.stdout, r.stdout)
            ctx = _base_context(tmp, head)
            s = vtc.run_checks(ctx, cwd=tmp)
            self.assertEqual(s["status"], vtc.STATUS_INVALID, s)
        finally:
            _cleanup_tmp_repo(tmp)

    def test_b05_tracked_deletion(self):
        tmp, head = _init_tmp_repo()
        try:
            os.remove(os.path.join(tmp, "README.md"))
            ctx = _base_context(tmp, head)
            s = vtc.run_checks(ctx, cwd=tmp)
            self.assertEqual(s["status"], vtc.STATUS_INVALID, s)
            self.assertTrue(any("deleted file outside" in v
                                for v in s["violations"]), s)
        finally:
            _cleanup_tmp_repo(tmp)

    def test_b06_staged_always_rejected(self):
        tmp, head = _init_tmp_repo()
        try:
            with open(os.path.join(tmp, "README.md"), "a") as f:
                f.write("y\n")
            _run_git("add", "README.md", cwd=tmp)
            ctx = _base_context(tmp, head)
            s = vtc.run_checks(ctx, cwd=tmp)
            self.assertEqual(s["status"], vtc.STATUS_INVALID, s)
            self.assertTrue(any("staged" in v for v in s["violations"]), s)
        finally:
            _cleanup_tmp_repo(tmp)

    def test_b07_conflict_always_rejected(self):
        tmp, head = _init_tmp_repo()
        try:
            with open(os.path.join(tmp, "README.md"), "w") as f:
                f.write("<<<<<<< HEAD\nx\n=======\ny\n>>>>>>> branch\n")
            ctx = _base_context(tmp, head)
            s = vtc.run_checks(ctx, cwd=tmp)
            # git may treat this as modified (no add yet) or unmerged
            # depending on version; either way status should be INVALID
            self.assertEqual(s["status"], vtc.STATUS_INVALID, s)
        finally:
            _cleanup_tmp_repo(tmp)


# ============================================================================
# Category C — Path contract tests
# ============================================================================
class PathContractTests(unittest.TestCase):

    def test_c01_forbidden_takes_priority_over_allowed(self):
        tmp, head = _init_tmp_repo()
        try:
            with open(os.path.join(tmp, "RESULTS.md"), "w") as f:
                f.write("x\n")
            ctx = _base_context(tmp, head,
                                allowed_modified=["RESULTS.md"],
                                forbidden=["RESULTS.md"])
            s = vtc.run_checks(ctx, cwd=tmp)
            self.assertEqual(s["status"], vtc.STATUS_INVALID, s)
            self.assertTrue(any("forbidden path" in v
                                for v in s["violations"]), s)
        finally:
            _cleanup_tmp_repo(tmp)

    def test_c02_work_allows_work_subfile(self):
        # _validate_path_list accepts "work/", then run_checks allows
        # a file inside work/.  Smoke: a path-list member of "work/"
        # passes validation, and a working-tree touch inside work/ is
        # accepted.
        validated = vtc._validate_path_list(["work/"], "test")
        self.assertEqual(validated, ["work"])

    def test_c03_work_does_not_allow_workspace_txt(self):
        validated = vtc._validate_path_list(["work/"], "test")
        self.assertEqual(validated, ["work"])
        # A file at root "workspace.txt" should NOT be under "work"
        # (false-positive guard).  We just test the helper directly.
        self.assertFalse(vtc._is_path_under(
            vtc._normalize_path("workspace.txt"),
            vtc._normalize_path("work"),
        ))

    def test_c04_list_member_non_string_rejected(self):
        with self.assertRaises(vtc.PathListError):
            vtc._validate_path_list(["ok", 42], "test")

    def test_c05_list_member_null_rejected(self):
        with self.assertRaises(vtc.PathListError):
            vtc._validate_path_list(["ok", None], "test")

    def test_c06_list_member_object_rejected(self):
        with self.assertRaises(vtc.PathListError):
            vtc._validate_path_list([{"a": 1}], "test")

    def test_c07_empty_string_rejected(self):
        with self.assertRaises(vtc.PathListError):
            vtc._validate_path_list([""], "test")

    def test_c08_absolute_path_rejected(self):
        with self.assertRaises(vtc.PathListError):
            vtc._validate_path_list(["/etc/passwd"], "test")
        with self.assertRaises(vtc.PathListError):
            vtc._validate_path_list(["C:/Windows/System32"], "test")

    def test_c09_dotdot_rejected(self):
        with self.assertRaises(vtc.PathListError):
            vtc._validate_path_list(["../etc"], "test")
        with self.assertRaises(vtc.PathListError):
            vtc._validate_path_list(["a/../../b"], "test")

    def test_c10_load_context_rejects_bad_paths(self):
        bad_ctx = {
            "schema_version": 1,
            "task_id": "T",
            "repository_full_name": "foo/bar",
            "worktree_path": "/tmp",
            "branch": "main",
            "expected_head": "a" * 40,
            "base_branch": "main",
            "base_sha": "a" * 40,
            "pr_number": None,
            "pr_head_branch": "main",
            "allowed_modified_paths": [],
            "allowed_untracked_paths": [],
            "forbidden_paths": ["../escape"],
        }
        with self.assertRaises(vtc.PathListError):
            vtc._load_context_from_dict(bad_ctx)


# ============================================================================
# Category D — Windows path tests (host-agnostic)
# ============================================================================
class WindowsPathTests(unittest.TestCase):

    def test_d01_equivalent_windows_paths(self):
        a = vtc._normalize_path("C:\\Users\\Test\\repo")
        b = vtc._normalize_path("C:/Users/Test/repo")
        c = vtc._normalize_path("c:\\users\\test\\repo")
        self.assertEqual(a, b)
        self.assertEqual(b, c)

    def test_d02_different_drives_not_equal(self):
        c = vtc._normalize_path("C:/Users/Test/repo")
        d = vtc._normalize_path("D:/Users/Test/repo")
        self.assertNotEqual(c, d)

    def test_d03_different_dirs_not_equal(self):
        c = vtc._normalize_path("C:/Users/Test/repo")
        e = vtc._normalize_path("C:/Users/Test/other")
        self.assertNotEqual(c, e)

    def test_d04_unc_distinct(self):
        u = vtc._normalize_path("\\\\server\\share\\repo")
        c = vtc._normalize_path("C:/server/share/repo")
        self.assertNotEqual(u, c)


# ============================================================================
# Category E — Output / rc contract
# ============================================================================
class OutputContractTests(unittest.TestCase):

    def test_e01_normal_mode_last_line_is_fixed_status(self):
        tmp, head = _init_tmp_repo()
        ctx_dir = tempfile.mkdtemp(prefix="vtc_e01_ctx_")
        try:
            ctx = _base_context(tmp, head)
            ctx_path = os.path.join(ctx_dir, "task_context.json")
            with open(ctx_path, "w") as f:
                json.dump(ctx, f)
            import io
            from contextlib import redirect_stdout
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = vtc.main(["--context", ctx_path, "--cwd", tmp])
            out = buf.getvalue()
            self.assertEqual(rc, vtc.RC_VALID, out)
            lines = [l for l in out.splitlines() if l.strip()]
            self.assertTrue(lines, "no stdout")
            self.assertIn(lines[-1], (
                vtc.STATUS_VALID_CLEAN,
                vtc.STATUS_VALID_AUTHORIZED_DIRTY,
                vtc.STATUS_INVALID,
            ))
        finally:
            shutil.rmtree(ctx_dir, ignore_errors=True)
            _cleanup_tmp_repo(tmp)

    def test_e02_json_mode_stdout_is_single_json(self):
        tmp, head = _init_tmp_repo()
        ctx_dir = tempfile.mkdtemp(prefix="vtc_e02_ctx_")
        try:
            ctx = _base_context(tmp, head)
            ctx_path = os.path.join(ctx_dir, "task_context.json")
            with open(ctx_path, "w") as f:
                json.dump(ctx, f)
            import io
            from contextlib import redirect_stdout
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = vtc.main(["--context", ctx_path, "--cwd", tmp,
                               "--json"])
            out = buf.getvalue()
            # Parse the entire stdout as a single JSON object
            obj = json.loads(out)
            self.assertIn("status", obj)
            self.assertEqual(rc, vtc.RC_VALID)
        finally:
            shutil.rmtree(ctx_dir, ignore_errors=True)
            _cleanup_tmp_repo(tmp)

    def test_e03_mismatch_rc2(self):
        tmp, head = _init_tmp_repo()
        try:
            ctx = _base_context(tmp, head, branch="WRONG")
            ctx_path = os.path.join(tmp, "ctx.json")
            with open(ctx_path, "w") as f:
                json.dump(ctx, f)
            rc = vtc.main(["--context", ctx_path, "--cwd", tmp])
            self.assertEqual(rc, vtc.RC_INVALID)
        finally:
            _cleanup_tmp_repo(tmp)

    def test_e04_dependency_unavailable_rc3(self):
        tmp, head = _init_tmp_repo()
        try:
            ctx = _base_context(tmp, head)
            ctx_path = os.path.join(tmp, "ctx.json")
            with open(ctx_path, "w") as f:
                json.dump(ctx, f)
            # Force git failure by monkey-patching _git_toplevel
            with mock.patch.object(vtc, "_git_toplevel",
                                   side_effect=vtc._GitUnavailable(
                                       "not a git repository")):
                rc = vtc.main(["--context", ctx_path, "--cwd", tmp])
            self.assertEqual(rc, vtc.RC_UNAVAILABLE)
        finally:
            _cleanup_tmp_repo(tmp)


# ============================================================================
# Category F — Final micro-patch tests
#   (UnicodeDecodeError P1, real rename direction, real merge, UNC,
#    detached rc=2)
# ============================================================================
class FinalMicroPatchTests(unittest.TestCase):

    # ---- F-1: _git() converts UnicodeDecodeError to _GitUnavailable ----
    def test_f01_unicode_decode_error_in_status_query(self):
        tmp, head = _init_tmp_repo()
        try:
            ctx = _base_context(tmp, head)
            real_run = subprocess.run

            def fake_run(args, **kwargs):
                # _git() calls subprocess.run(["git", *args], ...).
                # Only fail the status query; let other git calls
                # pass through to the real subprocess.
                if (isinstance(args, (list, tuple)) and len(args) >= 2
                        and args[0] == "git" and args[1] == "status"):
                    raise UnicodeDecodeError("utf-8", b"\xff\xfe", 0, 1,
                                             "invalid start byte")
                return real_run(args, **kwargs)

            with mock.patch("verify_task_context.subprocess.run",
                            side_effect=fake_run):
                s = vtc.run_checks(ctx, cwd=tmp)
            # No traceback escape, status invalid, dep unavailable,
            # NOT valid clean (no empty-dirty-set silently returned).
            self.assertEqual(s["status"], vtc.STATUS_INVALID, s)
            self.assertTrue(s["dependency_unavailable"], s)
            self.assertTrue(any("decode" in v.lower()
                                for v in s["violations"]), s)
            self.assertNotEqual(s["status"], vtc.STATUS_VALID_CLEAN)
            self.assertNotEqual(s["status"], vtc.STATUS_VALID_AUTHORIZED_DIRTY)
        finally:
            _cleanup_tmp_repo(tmp)

    # ---- F-1b: _git() directly converts UnicodeDecodeError ----
    def test_f01b_git_catches_unicode_decode_error(self):
        real_run = subprocess.run
        def fake_run(args, **kwargs):
            raise UnicodeDecodeError("utf-8", b"\xff\xfe", 0, 1,
                                     "invalid start byte")
        with mock.patch("verify_task_context.subprocess.run",
                        side_effect=fake_run):
            with self.assertRaises(vtc._GitUnavailable) as cm:
                vtc._git("status", cwd=".")
            self.assertIn("decode", str(cm.exception).lower())

    # ---- F-2: UnicodeDecodeError normal output mode ----
    def test_f02_unicode_decode_error_normal_mode_last_line(self):
        tmp, head = _init_tmp_repo()
        ctx_dir = tempfile.mkdtemp(prefix="vtc_f02_ctx_")
        try:
            ctx = _base_context(tmp, head)
            ctx_path = os.path.join(ctx_dir, "task_context.json")
            with open(ctx_path, "w") as f:
                json.dump(ctx, f)
            real_run = subprocess.run

            def fake_run(args, **kwargs):
                if (isinstance(args, (list, tuple)) and len(args) >= 2
                        and args[0] == "git" and args[1] == "status"):
                    raise UnicodeDecodeError("utf-8", b"\xff\xfe", 0, 1,
                                             "invalid start byte")
                return real_run(args, **kwargs)

            with mock.patch("verify_task_context.subprocess.run",
                            side_effect=fake_run):
                import io
                from contextlib import redirect_stdout
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = vtc.main(["--context", ctx_path, "--cwd", tmp])
            self.assertEqual(rc, vtc.RC_UNAVAILABLE)
            out = buf.getvalue()
            lines = [l for l in out.splitlines() if l.strip()]
            self.assertTrue(lines, "no stdout")
            self.assertEqual(lines[-1], vtc.STATUS_INVALID)
        finally:
            shutil.rmtree(ctx_dir, ignore_errors=True)
            _cleanup_tmp_repo(tmp)

    # ---- F-3: UnicodeDecodeError --json mode ----
    def test_f03_unicode_decode_error_json_mode_single_json(self):
        tmp, head = _init_tmp_repo()
        ctx_dir = tempfile.mkdtemp(prefix="vtc_f03_ctx_")
        try:
            ctx = _base_context(tmp, head)
            ctx_path = os.path.join(ctx_dir, "task_context.json")
            with open(ctx_path, "w") as f:
                json.dump(ctx, f)
            real_run = subprocess.run

            def fake_run(args, **kwargs):
                if (isinstance(args, (list, tuple)) and len(args) >= 2
                        and args[0] == "git" and args[1] == "status"):
                    raise UnicodeDecodeError("utf-8", b"\xff\xfe", 0, 1,
                                             "invalid start byte")
                return real_run(args, **kwargs)

            with mock.patch("verify_task_context.subprocess.run",
                            side_effect=fake_run):
                import io
                from contextlib import redirect_stdout
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = vtc.main(["--context", ctx_path, "--cwd", tmp,
                                   "--json"])
            self.assertEqual(rc, vtc.RC_UNAVAILABLE)
            out = buf.getvalue()
            obj = json.loads(out)
            self.assertEqual(obj["status"], vtc.STATUS_INVALID)
            self.assertTrue(obj["dependency_unavailable"])
        finally:
            shutil.rmtree(ctx_dir, ignore_errors=True)
            _cleanup_tmp_repo(tmp)

    # ---- F-4: real staged rename — destination\0source, summary = source -> destination ----
    def test_f04_real_staged_rename_with_space(self):
        tmp, head = _init_tmp_repo()
        try:
            # Create a file with space in name, commit, rename, stage
            old = os.path.join(tmp, "old name.md")
            with open(old, "w") as f:
                f.write("x\n")
            _run_git("add", "old name.md", cwd=tmp)
            _run_git("commit", "-q", "-m", "add", cwd=tmp)
            new_head = _run_git("rev-parse", "HEAD", cwd=tmp).stdout.strip()
            _run_git("push", "-q", "origin", "main", cwd=tmp)
            _run_git("branch", "--set-upstream-to=origin/main", cwd=tmp)
            new = os.path.join(tmp, "new name.md")
            os.rename(old, new)
            _run_git("add", "-A", cwd=tmp)
            # Verify the raw porcelain -z shape: first record is
            # "R  new name.md", second is "old name.md"
            r = _run_git("status", "--porcelain", "-z", cwd=tmp)
            self.assertIn("R  new name.md", r.stdout, r.stdout)
            ctx = _base_context(tmp, new_head)
            s = vtc.run_checks(ctx, cwd=tmp)
            self.assertEqual(s["status"], vtc.STATUS_INVALID, s)
            # Summary records the rename as source -> destination
            self.assertTrue(any("old name.md -> new name.md" in p
                                for p in s["renamed_paths"]), s)
            # Staged is still unconditionally rejected
            self.assertTrue(any("staged" in v
                                for v in s["violations"]), s)
        finally:
            _cleanup_tmp_repo(tmp)

    def test_f04b_real_staged_rename_with_unicode(self):
        tmp, head = _init_tmp_repo()
        try:
            old = os.path.join(tmp, "原文件.md")
            with open(old, "w", encoding="utf-8") as f:
                f.write("x\n")
            _run_git("add", "原文件.md", cwd=tmp)
            _run_git("commit", "-q", "-m", "add", cwd=tmp)
            new_head = _run_git("rev-parse", "HEAD", cwd=tmp).stdout.strip()
            _run_git("push", "-q", "origin", "main", cwd=tmp)
            _run_git("branch", "--set-upstream-to=origin/main", cwd=tmp)
            new = os.path.join(tmp, "新文件.md")
            os.rename(old, new)
            _run_git("add", "-A", cwd=tmp)
            r = _run_git("status", "--porcelain", "-z", cwd=tmp)
            self.assertIn("R  ", r.stdout, r.stdout)
            ctx = _base_context(tmp, new_head)
            s = vtc.run_checks(ctx, cwd=tmp)
            self.assertEqual(s["status"], vtc.STATUS_INVALID, s)
            # The source ("原文件.md") and destination ("新文件.md")
            # are recorded as 'source -> destination' in the summary.
            joined = " | ".join(s["renamed_paths"])
            self.assertIn("原文件.md", joined)
            self.assertIn("新文件.md", joined)
            self.assertIn(" -> ", joined)
        finally:
            _cleanup_tmp_repo(tmp)

    # ---- F-5: real git merge conflict producing UU index ----
    def test_f05_real_merge_conflict_uu_index(self):
        tmp, head = _init_tmp_repo()
        try:
            _run_git("checkout", "-q", "-b", "feat", cwd=tmp)
            with open(os.path.join(tmp, "README.md"), "w") as f:
                f.write("feature line\n")
            _run_git("commit", "-q", "-am", "feat", cwd=tmp)
            _run_git("checkout", "-q", "main", cwd=tmp)
            with open(os.path.join(tmp, "README.md"), "w") as f:
                f.write("main line\n")
            _run_git("commit", "-q", "-am", "main", cwd=tmp)
            # Real merge — produces UU in the index and conflict
            # markers in the working tree (does NOT call git add).
            r = _run_git("merge", "--no-commit", "--no-ff", "feat",
                         cwd=tmp)
            self.assertNotEqual(r.returncode, 0,
                                "merge should have conflicted")
            # Confirm the actual UU is in the porcelain -z output.
            r2 = _run_git("status", "--porcelain", "-z", cwd=tmp)
            self.assertIn("UU", r2.stdout, r2.stdout)
            ctx = _base_context(tmp, head)
            s = vtc.run_checks(ctx, cwd=tmp)
            self.assertEqual(s["status"], vtc.STATUS_INVALID, s)
            self.assertIn("README.md", s["conflict_paths"], s)
            self.assertTrue(any("unmerged/conflict" in v
                                for v in s["violations"]), s)
        finally:
            _cleanup_tmp_repo(tmp)

    # ---- F-6: UNC path equivalence ----
    def test_f06_unc_path_equivalence(self):
        a = vtc._normalize_path("\\\\SERVER\\Share\\repo")
        b = vtc._normalize_path("//server/share/repo")
        c = vtc._normalize_path("\\\\SERVER\\Share\\other")
        d = vtc._normalize_path("\\\\SERVER\\Other\\repo")
        # Same share/repo must be equivalent regardless of slash style
        self.assertEqual(a, b)
        # Different subdirectory
        self.assertNotEqual(a, c)
        # Different share
        self.assertNotEqual(a, d)
        # Subfile under UNC must be 'under' the UNC root
        self.assertTrue(vtc._is_path_under(
            vtc._normalize_path("\\\\SERVER\\Share\\repo\\sub\\file.txt"),
            vtc._normalize_path("//server/share/repo"),
        ))
        self.assertFalse(vtc._is_path_under(
            vtc._normalize_path("\\\\SERVER\\Share\\other\\file.txt"),
            vtc._normalize_path("//server/share/repo"),
        ))

    # ---- F-7: detached HEAD is identity mismatch (rc=2, dep_unavailable=False) ----
    def test_f07_detached_head_rc2_not_rc3(self):
        tmp, head = _init_tmp_repo()
        ctx_dir = tempfile.mkdtemp(prefix="vtc_f07_ctx_")
        try:
            _run_git("checkout", "--detach", "-q", head, cwd=tmp)
            ctx = _base_context(tmp, head)
            ctx_path = os.path.join(ctx_dir, "task_context.json")
            with open(ctx_path, "w") as f:
                json.dump(ctx, f)
            s = vtc.run_checks(ctx, cwd=tmp)
            self.assertEqual(s["status"], vtc.STATUS_INVALID, s)
            self.assertFalse(s["dependency_unavailable"], s)
            self.assertTrue(any("detached" in v
                                for v in s["violations"]), s)
            # main() must return rc=2, NOT rc=3
            import io
            from contextlib import redirect_stdout
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = vtc.main(["--context", ctx_path, "--cwd", tmp])
            self.assertEqual(rc, vtc.RC_INVALID, buf.getvalue())
        finally:
            shutil.rmtree(ctx_dir, ignore_errors=True)
            _cleanup_tmp_repo(tmp)


# ============================================================================
# Category G — Strict-decode final closure
#   errors="replace" removed; encoding="utf-8", errors="strict" pinned.
# ============================================================================
class StrictDecodeTests(unittest.TestCase):

    # ---- G-1: subprocess.run kwargs are encoding=utf-8 and errors=strict ----
    def test_g01_git_subprocess_kwargs_are_strict_utf8(self):
        captured = {}

        real_run = subprocess.run

        def fake_run(args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = dict(kwargs)
            return real_run(args, **kwargs)

        with mock.patch("verify_task_context.subprocess.run",
                        side_effect=fake_run):
            vtc._git("status", "--porcelain", cwd=".")
        kwargs = captured["kwargs"]
        # STRICT-DECODE: must use utf-8 + strict, never replace.
        self.assertEqual(kwargs.get("encoding"), "utf-8")
        self.assertEqual(kwargs.get("errors"), "strict")
        # Regression guard: errors must NOT be "replace".
        self.assertNotEqual(kwargs.get("errors"), "replace")

    # ---- G-2: _git() converts UnicodeDecodeError to _GitUnavailable ----
    def test_g02_git_unicode_decode_error_to_unavailable(self):
        def fake_run(args, **kwargs):
            raise UnicodeDecodeError("utf-8", b"\xff\xfe", 0, 1,
                                     "invalid start byte")
        with mock.patch("verify_task_context.subprocess.run",
                        side_effect=fake_run):
            with self.assertRaises(vtc._GitUnavailable) as cm:
                vtc._git("status", cwd=".")
            self.assertIn("decode", str(cm.exception).lower())

    # ---- G-3: run_checks returns INVALID + dep_unavailable=True, NOT VALID ----
    def test_g03_run_checks_status_query_decode_failure(self):
        tmp, head = _init_tmp_repo()
        try:
            ctx = _base_context(tmp, head)
            real_run = subprocess.run

            def fake_run(args, **kwargs):
                # confirm strict kwargs are present on the failing call
                self.assertEqual(kwargs.get("encoding"), "utf-8")
                self.assertEqual(kwargs.get("errors"), "strict")
                self.assertNotEqual(kwargs.get("errors"), "replace")
                if (isinstance(args, (list, tuple)) and len(args) >= 2
                        and args[0] == "git" and args[1] == "status"):
                    raise UnicodeDecodeError("utf-8", b"\xff\xfe", 0, 1,
                                             "invalid start byte")
                return real_run(args, **kwargs)

            with mock.patch("verify_task_context.subprocess.run",
                            side_effect=fake_run):
                s = vtc.run_checks(ctx, cwd=tmp)
            self.assertEqual(s["status"], vtc.STATUS_INVALID, s)
            self.assertTrue(s["dependency_unavailable"], s)
            # MUST NOT silently return a clean / authorized-dirty verdict.
            self.assertNotEqual(s["status"], vtc.STATUS_VALID_CLEAN)
            self.assertNotEqual(s["status"], vtc.STATUS_VALID_AUTHORIZED_DIRTY)
        finally:
            _cleanup_tmp_repo(tmp)

    # ---- G-4: normal mode — last line = CONTEXT_INVALID, rc=3 ----
    def test_g04_normal_mode_last_line_invalid_rc3(self):
        tmp, head = _init_tmp_repo()
        ctx_dir = tempfile.mkdtemp(prefix="vtc_g04_ctx_")
        try:
            ctx = _base_context(tmp, head)
            ctx_path = os.path.join(ctx_dir, "task_context.json")
            with open(ctx_path, "w") as f:
                json.dump(ctx, f)
            real_run = subprocess.run

            def fake_run(args, **kwargs):
                if (isinstance(args, (list, tuple)) and len(args) >= 2
                        and args[0] == "git" and args[1] == "status"):
                    raise UnicodeDecodeError("utf-8", b"\xff\xfe", 0, 1,
                                             "invalid start byte")
                return real_run(args, **kwargs)

            with mock.patch("verify_task_context.subprocess.run",
                            side_effect=fake_run):
                import io
                from contextlib import redirect_stdout
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = vtc.main(["--context", ctx_path, "--cwd", tmp])
            self.assertEqual(rc, vtc.RC_UNAVAILABLE)
            out = buf.getvalue()
            lines = [l for l in out.splitlines() if l.strip()]
            self.assertTrue(lines, "no stdout")
            self.assertEqual(lines[-1], vtc.STATUS_INVALID)
        finally:
            shutil.rmtree(ctx_dir, ignore_errors=True)
            _cleanup_tmp_repo(tmp)

    # ---- G-5: --json mode — single JSON, status=INVALID, dep_unavailable=true, rc=3 ----
    def test_g05_json_mode_single_json_invalid_rc3(self):
        tmp, head = _init_tmp_repo()
        ctx_dir = tempfile.mkdtemp(prefix="vtc_g05_ctx_")
        try:
            ctx = _base_context(tmp, head)
            ctx_path = os.path.join(ctx_dir, "task_context.json")
            with open(ctx_path, "w") as f:
                json.dump(ctx, f)
            real_run = subprocess.run

            def fake_run(args, **kwargs):
                if (isinstance(args, (list, tuple)) and len(args) >= 2
                        and args[0] == "git" and args[1] == "status"):
                    raise UnicodeDecodeError("utf-8", b"\xff\xfe", 0, 1,
                                             "invalid start byte")
                return real_run(args, **kwargs)

            with mock.patch("verify_task_context.subprocess.run",
                            side_effect=fake_run):
                import io
                from contextlib import redirect_stdout
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = vtc.main(["--context", ctx_path, "--cwd", tmp,
                                   "--json"])
            self.assertEqual(rc, vtc.RC_UNAVAILABLE)
            out = buf.getvalue()
            obj = json.loads(out)
            self.assertEqual(obj["status"], vtc.STATUS_INVALID)
            self.assertTrue(obj["dependency_unavailable"])
        finally:
            shutil.rmtree(ctx_dir, ignore_errors=True)
            _cleanup_tmp_repo(tmp)


if __name__ == "__main__":
    unittest.main()
