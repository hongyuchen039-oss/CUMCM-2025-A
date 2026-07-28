"""TASK_GOV_002 — task-context preflight verifier.

Read-only executable preflight. Does not modify the repository, the worktree,
or any local config. Fails closed on any inconsistency.

Usage:
    python scripts/verify_task_context.py --context work/task_context.json

Exit codes:
    0  — CONTEXT_VALID_CLEAN  (no dirty files)
       — CONTEXT_VALID_AUTHORIZED_DIRTY (dirty files all in allowed set)
    2  — CONTEXT_INVALID  (any check failed)
    3  — context / dependency / gh query unavailable

Fixed output lines (last line of stdout):
    CONTEXT_VALID_CLEAN
    CONTEXT_VALID_AUTHORIZED_DIRTY
    CONTEXT_INVALID
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple


# ----------------------------- required schema ----------------------------- #

REQUIRED_CONTEXT_FIELDS: Tuple[str, ...] = (
    "schema_version",
    "task_id",
    "repository_full_name",
    "worktree_path",
    "branch",
    "expected_head",
    "base_branch",
    "base_sha",
    "pr_number",
    "pr_head_branch",
    "allowed_modified_paths",
    "allowed_untracked_paths",
    "forbidden_paths",
)


# ----------------------------- fixed-status outputs ------------------------ #

STATUS_VALID_CLEAN = "CONTEXT_VALID_CLEAN"
STATUS_VALID_AUTHORIZED_DIRTY = "CONTEXT_VALID_AUTHORIZED_DIRTY"
STATUS_INVALID = "CONTEXT_INVALID"

RC_VALID = 0
RC_INVALID = 2
RC_UNAVAILABLE = 3


# ----------------------------- path normalization ------------------------- #

def _normalize_path(p: str) -> str:
    """Windows-aware path normalization for comparison.

    - resolve to absolute,
    - normcase (lowercase on Windows),
    - normalize separators to forward slash.
    """
    if p is None:
        return ""
    p = os.path.abspath(p)
    p = os.path.normcase(os.path.normpath(p))
    p = p.replace(os.sep, "/")
    return p


def _normalize_repo_relative(rel: str, repo_root: str) -> str:
    """Map a repo-relative or absolute path to a normalized absolute form
    anchored at repo_root. Used for comparing allowed/forbidden lists."""
    if not rel:
        return ""
    if os.path.isabs(rel):
        return _normalize_path(rel)
    return _normalize_path(os.path.join(repo_root, rel))


def _is_path_under(child_norm: str, parent_norm: str) -> bool:
    """True iff child_norm == parent_norm or child_norm is strictly under
    parent_norm (segment-wise, after normalization)."""
    if not child_norm or not parent_norm:
        return False
    if child_norm == parent_norm:
        return True
    prefix = parent_norm.rstrip("/") + "/"
    return child_norm.startswith(prefix)


# ----------------------------- git helpers -------------------------------- #

def _git(
    *args: str,
    cwd: Optional[str] = None,
    check: bool = False,
) -> Tuple[int, str, str]:
    """Run a git command. Returns (returncode, stdout, stderr)."""
    try:
        r = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return (127, "", f"git unavailable: {exc}")
    return (r.returncode, r.stdout, r.stderr)


def _git_toplevel(cwd: Optional[str] = None) -> Optional[str]:
    rc, out, _ = _git("rev-parse", "--show-toplevel", cwd=cwd)
    if rc != 0:
        return None
    return out.strip()


def _git_head_sha(cwd: Optional[str] = None) -> Optional[str]:
    rc, out, _ = _git("rev-parse", "HEAD", cwd=cwd)
    if rc != 0:
        return None
    return out.strip()


def _git_branch(cwd: Optional[str] = None) -> Optional[str]:
    rc, out, _ = _git("rev-parse", "--abbrev-ref", "HEAD", cwd=cwd)
    if rc != 0:
        return None
    b = out.strip()
    if b == "HEAD":  # detached
        return None
    return b


def _git_remote_url(remote: str, cwd: Optional[str] = None) -> Optional[str]:
    rc, out, _ = _git("remote", "get-url", remote, cwd=cwd)
    if rc != 0:
        return None
    return out.strip()


def _git_tracking_remote(cwd: Optional[str] = None) -> Optional[str]:
    """Return upstream tracking remote of current branch, or None."""
    rc, out, _ = _git(
        "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}", cwd=cwd,
    )
    if rc != 0:
        return None
    return out.strip()  # e.g. origin/main


def _git_tracking_remote_for(branch: str,
                             cwd: Optional[str] = None) -> Optional[str]:
    """Resolve origin/<branch> as a remote-tracking ref. Returns the SHA
    if resolvable, else None."""
    rc, out, _ = _git("rev-parse", "--verify",
                      f"origin/{branch}", cwd=cwd)
    if rc != 0:
        return None
    return out.strip()


def _git_status_paths(cwd: Optional[str] = None) -> Dict[str, List[str]]:
    """Return dict with keys: modified, staged, untracked, conflict, deleted.

    Each value is a list of repo-relative paths.
    """
    rc, out, _ = _git("status", "--porcelain", "--untracked-files=normal",
                      "-z", cwd=cwd)
    if rc != 0:
        return {"modified": [], "staged": [], "untracked": [],
                "conflict": [], "deleted": []}
    modified: List[str] = []
    staged: List[str] = []
    untracked: List[str] = []
    conflict: List[str] = []
    deleted: List[str] = []
    # -z separates entries with NUL, paths within an entry with spaces.
    for entry in out.split("\x00"):
        if not entry:
            continue
        # Format: XY PATH  (two chars, space, path); with rename XY PATH -> NEW
        if len(entry) < 4:
            continue
        x = entry[0]
        y = entry[1]
        # path part begins at index 3
        path = entry[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        # Conflict markers
        if x in ("U", "A") and y in ("U", "A"):
            conflict.append(path)
            continue
        if x == "U" or y == "U" or x == "A" and y == "A":
            conflict.append(path)
            continue
        if x == "?" and y == "?":
            untracked.append(path)
            continue
        if x != " " and x != "?":
            staged.append(path)
        if y == "M":
            modified.append(path)
        elif y == "D":
            deleted.append(path)
        elif y == "A":
            # added in index, treat as staged only
            pass
    return {
        "modified": modified,
        "staged": staged,
        "untracked": untracked,
        "conflict": conflict,
        "deleted": deleted,
    }


# ----------------------------- context validation ------------------------- #

class ContextError(Exception):
    """Raised when the context file is missing / malformed / has wrong schema."""


def _load_context(path: str) -> Dict[str, Any]:
    if not os.path.isfile(path):
        raise ContextError(f"context file not found: {path}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        raise ContextError(f"context JSON load failed: {exc}") from exc
    if not isinstance(data, dict):
        raise ContextError("context root must be a JSON object")
    for field in REQUIRED_CONTEXT_FIELDS:
        if field not in data:
            raise ContextError(f"context missing required field: {field}")
    # Type sanity
    sv = data["schema_version"]
    if not isinstance(sv, int) or sv != 1:
        raise ContextError(f"schema_version must be 1, got {sv!r}")
    for list_field in ("allowed_modified_paths", "allowed_untracked_paths",
                       "forbidden_paths"):
        if not isinstance(data[list_field], list):
            raise ContextError(f"{list_field} must be a list")
    for str_field in ("task_id", "repository_full_name", "worktree_path",
                      "branch", "expected_head", "base_branch", "base_sha",
                      "pr_head_branch"):
        if not isinstance(data[str_field], str):
            raise ContextError(f"{str_field} must be a string")
    if data["pr_number"] is not None and not isinstance(data["pr_number"], int):
        raise ContextError("pr_number must be null or int")
    return data


def _remote_matches_repo(remote_url: str, expected: str) -> bool:
    """Match https://github.com/<owner>/<repo>.git or git@github.com:<owner>/<repo>.git
    to 'owner/repo'."""
    if not remote_url or not expected:
        return False
    s = remote_url.strip()
    for prefix in ("https://github.com/", "http://github.com/",
                   "git@github.com:", "ssh://git@github.com/"):
        if s.startswith(prefix):
            s = s[len(prefix):]
            break
    else:
        return False
    if s.endswith(".git"):
        s = s[:-4]
    return s.lower() == expected.lower()


# ----------------------------- main check loop ---------------------------- #

def run_checks(ctx: Dict[str, Any], cwd: Optional[str] = None) -> Dict[str, Any]:
    """Execute all checks. Returns a summary dict; never raises (errors stored
    in 'violations' and 'error')."""
    summary: Dict[str, Any] = {
        "status": STATUS_INVALID,
        "task_id": ctx.get("task_id"),
        "repo_root_expected": ctx.get("worktree_path"),
        "repo_root_actual": None,
        "branch_expected": ctx.get("branch"),
        "branch_actual": None,
        "head_expected": ctx.get("expected_head"),
        "head_actual": None,
        "origin_remote_url": None,
        "tracking_ref": None,
        "pr_number": ctx.get("pr_number"),
        "pr_head_branch": ctx.get("pr_head_branch"),
        "modified_paths": [],
        "staged_paths": [],
        "untracked_paths": [],
        "conflict_paths": [],
        "deleted_paths": [],
        "violations": [],
        "error": None,
    }
    violations: List[str] = []

    def fail(msg: str) -> None:
        violations.append(msg)

    # 2. repo toplevel
    repo_root = _git_toplevel(cwd=cwd)
    if not repo_root:
        summary["error"] = "not a git repository"
        return summary
    summary["repo_root_actual"] = repo_root

    expected_root = _normalize_path(ctx["worktree_path"])
    actual_root = _normalize_path(repo_root)
    if expected_root != actual_root:
        fail(f"worktree_path mismatch: expected={expected_root!r} "
             f"actual={actual_root!r}")

    # 4/5. branch + detached
    branch = _git_branch(cwd=cwd)
    summary["branch_actual"] = branch
    if branch is None:
        fail("detached HEAD or branch unresolvable")
    elif branch != ctx["branch"]:
        fail(f"branch mismatch: expected={ctx['branch']!r} actual={branch!r}")

    # 6. HEAD
    head = _git_head_sha(cwd=cwd)
    summary["head_actual"] = head
    if not head:
        fail("HEAD unresolvable")
    elif head != ctx["expected_head"]:
        fail(f"HEAD mismatch: expected={ctx['expected_head']!r} "
             f"actual={head!r}")

    # 7. origin remote
    remote = _git_remote_url("origin", cwd=cwd)
    summary["origin_remote_url"] = remote
    if not remote:
        fail("origin remote missing or unresolvable")
    elif not _remote_matches_repo(remote, ctx["repository_full_name"]):
        fail(f"origin remote URL does not match "
             f"{ctx['repository_full_name']!r}: got {remote!r}")

    # 8. base tracking ref (resolves origin/<base_branch>)
    base_branch = ctx["base_branch"]
    tracking = _git_tracking_remote_for(base_branch, cwd=cwd)
    summary["tracking_ref"] = tracking
    if not tracking:
        fail(f"base tracking ref 'origin/{base_branch}' unresolvable")

    # 9. pr_number check via gh
    pr_number = ctx.get("pr_number")
    if pr_number is not None:
        if shutil.which("gh") is None:
            fail("gh CLI not available but pr_number is set")
        else:
            try:
                r = subprocess.run(
                    ["gh", "pr", "view", str(pr_number),
                     "--json", "headRefName,headRefOid,state,isCrossRepository"],
                    capture_output=True, text=True, timeout=20,
                )
            except subprocess.TimeoutExpired as exc:
                fail(f"gh pr view timeout: {exc}")
                r = None  # type: ignore
            if r is not None and r.returncode != 0:
                fail(f"gh pr view failed (rc={r.returncode}): "
                     f"{r.stderr.strip()}")
            elif r is not None:
                try:
                    pr_data = json.loads(r.stdout)
                except json.JSONDecodeError as exc:
                    fail(f"gh pr view returned non-JSON: {exc}")
                else:
                    pr_branch = pr_data.get("headRefName")
                    pr_sha = pr_data.get("headRefOid")
                    cross = pr_data.get("isCrossRepository", False)
                    if cross:
                        fail(f"pr #{pr_number} is cross-repository")
                    if pr_branch != ctx["pr_head_branch"]:
                        fail(f"pr head branch mismatch: expected "
                             f"{ctx['pr_head_branch']!r} got {pr_branch!r}")
                    if pr_sha != ctx["expected_head"]:
                        fail(f"pr head SHA mismatch: expected "
                             f"{ctx['expected_head']!r} got {pr_sha!r}")

    # 10/11/12/13. working-tree state
    st = _git_status_paths(cwd=cwd)
    summary["staged_paths"] = st["staged"]
    summary["modified_paths"] = st["modified"]
    summary["untracked_paths"] = st["untracked"]
    summary["conflict_paths"] = st["conflict"]
    summary["deleted_paths"] = st["deleted"]

    if st["staged"]:
        fail(f"staged files present (must be empty): {st['staged']}")
    if st["conflict"]:
        fail(f"unmerged/conflict files present: {st['conflict']}")

    allowed_modified = [_normalize_repo_relative(p, repo_root)
                        for p in ctx.get("allowed_modified_paths", [])]
    allowed_untracked = [_normalize_repo_relative(p, repo_root)
                         for p in ctx.get("allowed_untracked_paths", [])]
    forbidden = [_normalize_repo_relative(p, repo_root)
                 for p in ctx.get("forbidden_paths", [])]

    def _is_authorized(path: str, allowed: List[str]) -> bool:
        norm = _normalize_path(os.path.join(repo_root, path))
        for a in allowed:
            if _is_path_under(norm, a):
                return True
        return False

    for p in st["modified"]:
        if not _is_authorized(p, allowed_modified):
            fail(f"modified file outside allowed_modified_paths: {p!r}")
    for p in st["deleted"]:
        if not _is_authorized(p, allowed_modified):
            fail(f"deleted file outside allowed_modified_paths: {p!r}")
    for p in st["untracked"]:
        if not _is_authorized(p, allowed_untracked):
            fail(f"untracked file outside allowed_untracked_paths: {p!r}")

    for p in st["modified"] + st["deleted"] + st["untracked"]:
        for f in forbidden:
            if _is_path_under(
                _normalize_path(os.path.join(repo_root, p)), f,
            ):
                fail(f"forbidden path touched: {p!r}")
                break

    summary["violations"] = violations
    if not violations:
        if (st["modified"] or st["deleted"] or st["untracked"]):
            summary["status"] = STATUS_VALID_AUTHORIZED_DIRTY
        else:
            summary["status"] = STATUS_VALID_CLEAN
    else:
        summary["status"] = STATUS_INVALID
    return summary


# ----------------------------- entry point -------------------------------- #

def _emit_human(summary: Dict[str, Any]) -> None:
    status = summary["status"]
    print(f"[verify_task_context] status: {status}")
    print(f"[verify_task_context] task_id: {summary.get('task_id')}")
    if summary.get("violations"):
        print("[verify_task_context] violations:")
        for v in summary["violations"]:
            print(f"  - {v}")
    if summary.get("error"):
        print(f"[verify_task_context] error: {summary['error']}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="verify_task_context",
        description="TASK_GOV_002 task-context preflight verifier (read-only).",
    )
    parser.add_argument(
        "--context", required=True,
        help="Path to task_context JSON (e.g. work/task_context.json)",
    )
    parser.add_argument(
        "--cwd", default=None,
        help="Working directory for git commands (default: current dir)",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Print only the JSON summary to stdout",
    )
    args = parser.parse_args(argv)

    try:
        ctx = _load_context(args.context)
    except ContextError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print(STATUS_INVALID)
        if args.json:
            print(json.dumps({
                "status": STATUS_INVALID,
                "error": str(exc),
                "violations": [],
            }, ensure_ascii=False))
        return RC_UNAVAILABLE

    summary = run_checks(ctx, cwd=args.cwd)

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        _emit_human(summary)
        # Always print the fixed status as the last non-empty stdout line
        print(summary["status"])

    if summary["status"] == STATUS_INVALID:
        return RC_INVALID
    return RC_VALID


if __name__ == "__main__":
    sys.exit(main())
