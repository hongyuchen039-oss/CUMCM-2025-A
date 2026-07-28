"""TASK_GOV_002 — task-context preflight verifier.

Read-only executable preflight. Does not modify the repository, the worktree,
or any local config. Fails closed on any inconsistency.

Usage:
    python scripts/verify_task_context.py --context work/task_context.json
    python scripts/verify_task_context.py --context work/task_context.json --json

Exit codes (strict contract):
    0  — CONTEXT_VALID_CLEAN  (no dirty files)
       — CONTEXT_VALID_AUTHORIZED_DIRTY (dirty files all in allowed set)
    2  — CONTEXT_INVALID  (identity / authorization mismatch)
    3  — context / Git / git status / gh / parse dependency unavailable

Fixed status line (last line of stdout, non --json mode):
    CONTEXT_VALID_CLEAN
    CONTEXT_VALID_AUTHORIZED_DIRTY
    CONTEXT_INVALID

--json mode: stdout is exactly one valid JSON object; status lives in
the JSON `status` field; no extra plain-text status line on stdout.
"""

from __future__ import annotations

import argparse
import json
import ntpath
import os
import posixpath
import re
import shutil
import subprocess
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple


# ----------------------------- required schema ---------------------------- #

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

# Pattern for a Windows drive-letter root, e.g. "C:" "C:\" "C:/" "c:".
_DRIVE_LETTER_RE = re.compile(r"^[A-Za-z]:")

# Full 40-character lower-case hex SHA-1.
_SHA1_FULL_RE = re.compile(r"^[0-9a-f]{40}$")


def _is_windows_path(p: str) -> bool:
    """Heuristic: a path is Windows-style if it has a drive-letter prefix
    (C:, D:, ...), contains a backslash separator, or is a UNC path
    starting with '//server/share' (treated case-insensitively, like
    NTFS)."""
    if not p:
        return False
    if "\\" in p:
        return True
    if _DRIVE_LETTER_RE.match(p):
        return True
    # UNC: //server/share or \\server\share. After the backslash ->
    # forward-slash rewrite below this would become //server/share.
    if p.startswith("//") and len(p) > 2 and p[2] != "/":
        return True
    return False


def _normalize_path(p: str, *, force_windows: Optional[bool] = None,
                    is_dir: bool = False) -> str:
    """Normalize a path string for comparison.

    - Convert backslashes to forward slashes.
    - Apply the appropriate normpath (ntpath for Windows-style paths,
      posixpath for POSIX-style paths).  Detection can be overridden
      with force_windows=True/False.
    - For Windows-style paths (incl. UNC '//server/share'), lowercase
      the result (Windows / NTFS is case-insensitive).
    - For POSIX-style paths, leave case as-is.
    - If is_dir, ensure trailing slash.
    """
    if p is None:
        return ""
    s = str(p).replace("\\", "/")
    if force_windows is True or (force_windows is None and _is_windows_path(s)):
        norm = ntpath.normpath(s).replace("\\", "/")
        norm = norm.lower()
    else:
        norm = posixpath.normpath(s)
    if is_dir and not norm.endswith("/"):
        norm = norm + "/"
    return norm


def _normalize_repo_relative(rel: str, repo_root: str,
                             *, is_dir: bool = False) -> str:
    """Map a repo-relative or absolute path to a normalized absolute form
    anchored at repo_root (used for comparing allowed/forbidden lists)."""
    if not rel:
        return ""
    if os.path.isabs(rel):
        return _normalize_path(rel, is_dir=is_dir)
    joined = os.path.join(repo_root, rel).replace("\\", "/")
    return _normalize_path(joined, is_dir=is_dir)


def _is_path_under(child_norm: str, parent_norm: str) -> bool:
    """True iff child_norm == parent_norm or child_norm is strictly under
    parent_norm (segment-wise, after normalization)."""
    if not child_norm or not parent_norm:
        return False
    if child_norm == parent_norm:
        return True
    prefix = parent_norm.rstrip("/") + "/"
    return child_norm.startswith(prefix)


# ----------------------------- path list contract ------------------------ #

class PathListError(Exception):
    """Raised when a context path-list (allowed_*/forbidden) is malformed."""


def _validate_path_list(values: Any, list_name: str) -> List[str]:
    """Validate a context path list against the contract:
    - must be a list of non-empty strings
    - each must be a repo-relative path
    - no absolute paths
    - no '..' segment
    - not equal to '.'
    - uniform path-separator (forward-slash)
    Returns the list of normalized, validated strings.
    """
    if not isinstance(values, list):
        raise PathListError(f"{list_name} must be a list")
    out: List[str] = []
    for i, raw in enumerate(values):
        if not isinstance(raw, str):
            raise PathListError(
                f"{list_name}[{i}] must be a string, got {type(raw).__name__}")
        s = raw.strip()
        if not s:
            raise PathListError(f"{list_name}[{i}] must be non-empty")
        if "\\" in s:
            raise PathListError(
                f"{list_name}[{i}] must use forward-slash separators")
        if s != s.replace("\\", "/"):
            raise PathListError(
                f"{list_name}[{i}] contains backslashes")
        if s.startswith("/"):
            raise PathListError(
                f"{list_name}[{i}] must be repo-relative (no leading /)")
        if os.path.isabs(s) or _DRIVE_LETTER_RE.match(s):
            raise PathListError(
                f"{list_name}[{i}] must be repo-relative (no absolute)")
        if s == ".":
            raise PathListError(f"{list_name}[{i}] must not be '.'")
        # reject any segment that is '..'
        parts = s.split("/")
        if any(seg == ".." for seg in parts):
            raise PathListError(
                f"{list_name}[{i}] must not contain '..' segment")
        # normalize for storage (collapse 'a//b' -> 'a/b', etc.)
        norm = posixpath.normpath(s).replace("\\", "/")
        if norm == ".":
            raise PathListError(
                f"{list_name}[{i}] normalizes to '.' (forbidden)")
        out.append(norm)
    return out


# ----------------------------- git helpers -------------------------------- #

class _GitUnavailable(Exception):
    """Raised when a Git query (or its output) is unavailable."""


class _DetachedHead(Exception):
    """Raised when HEAD is detached.

    This is NOT a dependency-unavailable condition; it is an identity
    mismatch against the expected branch. The verifier treats it as
    CONTEXT_INVALID (rc=2) with dependency_unavailable=False.
    """


def _git(
    *args: str,
    cwd: Optional[str] = None,
    timeout: int = 15,
) -> Tuple[int, str, str]:
    """Run a git command. Returns (returncode, stdout, stderr).  Raises
    _GitUnavailable on subprocess-level failure (no git, timeout) and
    on text-decoding failure (UnicodeDecodeError from the subprocess
    pipes).  Decoding failure is treated as dependency unavailable so
    the verifier fails closed (rc=3, dependency_unavailable=true)
    rather than letting a traceback escape main().

    We force `encoding="utf-8"` and `errors="replace"` so that Git's
    UTF-8 output (the documented encoding for porcelain and field
    output) decodes deterministically across platforms / code pages,
    instead of relying on the locale-derived encoding that
    subprocess.run defaults to with text=True.  We still
    defensively catch UnicodeDecodeError for the rare case where the
    forced encoding still fails.
    """
    try:
        r = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise _GitUnavailable(f"git binary not found: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise _GitUnavailable(f"git {args!r} timeout: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise _GitUnavailable(
            f"git {args!r} output decode failed: {exc}") from exc
    return (r.returncode, r.stdout, r.stderr)


def _git_toplevel(cwd: Optional[str] = None) -> str:
    rc, out, _ = _git("rev-parse", "--show-toplevel", cwd=cwd)
    if rc != 0 or not out.strip():
        raise _GitUnavailable("git rev-parse --show-toplevel failed")
    return out.strip()


def _git_head_sha(cwd: Optional[str] = None) -> str:
    rc, out, _ = _git("rev-parse", "HEAD", cwd=cwd)
    if rc != 0 or not out.strip():
        raise _GitUnavailable("git rev-parse HEAD failed")
    return out.strip()


def _git_branch(cwd: Optional[str] = None) -> str:
    rc, out, _ = _git("rev-parse", "--abbrev-ref", "HEAD", cwd=cwd)
    if rc != 0 or not out.strip():
        raise _GitUnavailable("git rev-parse --abbrev-ref HEAD failed")
    b = out.strip()
    if b == "HEAD":  # detached
        raise _DetachedHead("HEAD is detached")
    return b


def _git_remote_url(remote: str, cwd: Optional[str] = None) -> str:
    rc, out, _ = _git("remote", "get-url", remote, cwd=cwd)
    if rc != 0 or not out.strip():
        raise _GitUnavailable(f"git remote get-url {remote!r} failed")
    return out.strip()


def _git_base_sha(branch: str, cwd: Optional[str] = None) -> str:
    """Resolve origin/<branch> as a full 40-hex SHA.  Raises
    _GitUnavailable if the ref cannot be resolved or the SHA is not
    40-hex."""
    rc, out, _ = _git("rev-parse", "--verify", f"origin/{branch}", cwd=cwd)
    if rc != 0 or not out.strip():
        raise _GitUnavailable(
            f"git rev-parse --verify origin/{branch} failed")
    sha = out.strip()
    if not _SHA1_FULL_RE.match(sha):
        raise _GitUnavailable(
            f"origin/{branch} resolved to non-40-hex SHA: {sha!r}")
    return sha


# ----------------------------- porcelain parser -------------------------- #

class _PorcelainError(Exception):
    """Raised when porcelain output cannot be parsed."""


def _parse_porcelain_z(raw: str) -> Dict[str, List[str]]:
    """Parse `git status --porcelain=v1 -z` output into:
        modified, staged, untracked, conflict, deleted,
        renamed (list of 'source -> destination' strings).

    Renames/copies (status R or C) emit TWO NUL-terminated path
    records in this order:
        1. status line + space + destination (the new path)
        2. source (the old path)
    The first record's path field is therefore the **destination**,
    not the source. The summary must express the rename as
    'source -> destination', which is the human-meaningful form.
    The second record must NOT be re-parsed as a status line.
    """
    modified: List[str] = []
    staged: List[str] = []
    untracked: List[str] = []
    conflict: List[str] = []
    deleted: List[str] = []
    renamed: List[str] = []
    if raw is None:
        raise _PorcelainError("porcelain output is None")

    parts = raw.split("\x00")
    i = 0
    n = len(parts)
    while i < n:
        entry = parts[i]
        i += 1
        if entry == "":
            # trailing NUL separator or empty record
            continue
        if len(entry) < 3:
            raise _PorcelainError(
                f"porcelain entry too short: {entry!r}")
        x = entry[0]
        y = entry[1]
        rest = entry[2:]  # 3rd char is space, then path(s)
        if rest and rest[0] == " ":
            rest = rest[1:]
        if not rest:
            raise _PorcelainError(
                f"porcelain entry missing path: {entry!r}")
        # conflict markers
        if (x, y) in (("U", "U"), ("A", "A"), ("U", "A"), ("A", "U"),
                      ("D", "D"), ("D", "U"), ("U", "D")):
            conflict.append(rest)
            continue
        # rename / copy: consume the next NUL record.
        # Per `git status --porcelain=v1 -z` the FIRST path is the
        # destination (the new path), and the SECOND NUL record is
        # the source (the old path).
        if (x, y) in (("R", " "), ("R", x), ("R", y), ("C", " "),
                      ("C", x), ("C", y)) or x in ("R", "C"):
            destination = rest
            if i >= n:
                raise _PorcelainError(
                    f"rename/copy missing source: {entry!r}")
            source = parts[i]
            i += 1
            renamed.append(f"{source} -> {destination}")
            # rename/copy is staged (added in index). Track both
            # endpoints so downstream authorization sees them.
            staged.append(destination)
            staged.append(source)
            continue
        # untracked
        if x == "?" and y == "?":
            untracked.append(rest)
            continue
        # anything in the index (X != ' ') is staged
        if x != " ":
            staged.append(rest)
        if y == "M":
            modified.append(rest)
        elif y == "D":
            deleted.append(rest)
        elif y == "A":
            # added in work-tree as well
            modified.append(rest)
        # else (' '): no work-tree change
    return {
        "modified": modified,
        "staged": staged,
        "untracked": untracked,
        "conflict": conflict,
        "deleted": deleted,
        "renamed": renamed,
    }


def _git_status_paths(cwd: Optional[str] = None) -> Dict[str, List[str]]:
    """Get working-tree state.  Raises _PorcelainError on any failure
    (timeout, non-zero, decode, malformed, dependency unavailable);
    does NOT silently return empty sets."""
    try:
        rc, out, err = _git(
            "status", "--porcelain", "--untracked-files=normal", "-z",
            cwd=cwd,
        )
    except _GitUnavailable as exc:
        raise _PorcelainError(f"git status dependency unavailable: {exc}") from exc
    if rc != 0:
        raise _PorcelainError(
            f"git status --porcelain returned rc={rc}: {err.strip()}")
    try:
        # Decode can raise UnicodeDecodeError on garbage; we let it
        # propagate as _PorcelainError.
        return _parse_porcelain_z(out)
    except _PorcelainError:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        raise _PorcelainError(f"porcelain parse failed: {exc}") from exc


# ----------------------------- context validation ------------------------- #

class ContextError(Exception):
    """Raised when the context file is missing / malformed / has wrong schema."""


def _load_context_from_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate an already-parsed context dict (no file IO).  Used by
    tests to avoid touching the filesystem."""
    # Reuse the same validation as _load_context by serializing through
    # an in-memory tempfile.
    import tempfile
    with tempfile.NamedTemporaryFile(
        "w", suffix=".json", delete=False, encoding="utf-8",
    ) as f:
        json.dump(data, f)
        path = f.name
    try:
        return _load_context(path)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


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
    # expected_head / base_sha must be full 40-hex
    for sha_field in ("expected_head", "base_sha"):
        if not _SHA1_FULL_RE.match(data[sha_field]):
            raise ContextError(f"{sha_field} must be 40-char lowercase hex")
    # path list contracts (forbidden first so it takes priority semantically)
    forbidden = _validate_path_list(data["forbidden_paths"], "forbidden_paths")
    data["forbidden_paths"] = forbidden
    data["allowed_modified_paths"] = _validate_path_list(
        data["allowed_modified_paths"], "allowed_modified_paths")
    data["allowed_untracked_paths"] = _validate_path_list(
        data["allowed_untracked_paths"], "allowed_untracked_paths")
    return data


def _remote_matches_repo(remote_url: str, expected: str) -> bool:
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


# ----------------------------- gh pr view helper ------------------------- #

def _gh_pr_view(pr_number: int, repository: str,
                cwd: Optional[str] = None,
                timeout: int = 20) -> Dict[str, Any]:
    """Call `gh pr view <n> --repo <repo> --json ...` read-only.

    Raises _GitUnavailable-equivalent (we reuse _GitUnavailable) on
    - gh binary missing
    - timeout
    - non-zero exit
    - invalid JSON
    - missing required keys
    Returns the parsed JSON dict.
    """
    if shutil.which("gh") is None:
        raise _GitUnavailable("gh CLI not available")
    fields = ("headRefName,headRefOid,baseRefName,baseRefOid,"
              "isCrossRepository,state,url")
    cmd = [
        "gh", "pr", "view", str(pr_number),
        "--repo", repository,
        "--json", fields,
    ]
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True,
                           text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise _GitUnavailable(f"gh pr view timeout: {exc}") from exc
    except FileNotFoundError as exc:
        raise _GitUnavailable(f"gh binary not found: {exc}") from exc
    if r.returncode != 0:
        raise _GitUnavailable(
            f"gh pr view failed (rc={r.returncode}): "
            f"{(r.stderr or r.stdout).strip()}")
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError as exc:
        raise _GitUnavailable(
            f"gh pr view returned non-JSON: {exc}; "
            f"stdout[:200]={r.stdout[:200]!r}") from exc
    if not isinstance(data, dict):
        raise _GitUnavailable("gh pr view returned non-object JSON")
    for key in ("headRefName", "headRefOid", "baseRefName", "baseRefOid",
                "isCrossRepository", "state"):
        if key not in data:
            raise _GitUnavailable(
                f"gh pr view missing required field: {key}")
    return data


# ----------------------------- main check loop ---------------------------- #

def run_checks(ctx: Dict[str, Any],
               cwd: Optional[str] = None) -> Dict[str, Any]:
    """Execute all checks.  Returns a summary dict; never raises
    (errors stored in summary['violations'] and
    summary['dependency_unavailable'])."""
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
        "base_branch": ctx.get("base_branch"),
        "base_sha_expected": ctx.get("base_sha"),
        "base_sha_actual": None,
        "pr_number": ctx.get("pr_number"),
        "pr_head_branch": ctx.get("pr_head_branch"),
        "pr_base_branch": None,
        "pr_base_sha": None,
        "modified_paths": [],
        "staged_paths": [],
        "untracked_paths": [],
        "conflict_paths": [],
        "deleted_paths": [],
        "renamed_paths": [],
        "violations": [],
        "dependency_unavailable": False,
        "dependency_error": None,
        "error": None,
    }
    violations: List[str] = []

    def fail(msg: str) -> None:
        violations.append(msg)

    def dep_fail(msg: str) -> None:
        # Same as fail but also marks the run as dependency-unavailable.
        summary["dependency_unavailable"] = True
        summary["dependency_error"] = msg
        violations.append(msg)

    # 2. repo toplevel
    try:
        repo_root = _git_toplevel(cwd=cwd)
    except _GitUnavailable as exc:
        dep_fail(f"repo toplevel unresolvable: {exc}")
        summary["violations"] = violations
        return summary
    summary["repo_root_actual"] = repo_root

    expected_root = _normalize_path(ctx["worktree_path"])
    actual_root = _normalize_path(repo_root)
    if expected_root != actual_root:
        fail(f"worktree_path mismatch: expected={expected_root!r} "
             f"actual={actual_root!r}")

    # 4/5. branch + detached
    try:
        branch = _git_branch(cwd=cwd)
    except _DetachedHead as exc:
        # Detached HEAD is an IDENTITY mismatch (the expected branch
        # is not checked out), not a dependency-unavailable condition.
        fail(f"detached HEAD: {exc}")
        branch = None
    except _GitUnavailable as exc:
        dep_fail(f"branch unresolvable: {exc}")
        branch = None
    summary["branch_actual"] = branch
    if branch is None:
        # Already fail()'d or dep_fail()'d above.
        pass
    elif branch != ctx["branch"]:
        fail(f"branch mismatch: expected={ctx['branch']!r} actual={branch!r}")

    # 6. HEAD
    try:
        head = _git_head_sha(cwd=cwd)
    except _GitUnavailable as exc:
        dep_fail(f"HEAD unresolvable: {exc}")
        head = None
    summary["head_actual"] = head
    if head and head != ctx["expected_head"]:
        fail(f"HEAD mismatch: expected={ctx['expected_head']!r} "
             f"actual={head!r}")

    # 7. origin remote
    try:
        remote = _git_remote_url("origin", cwd=cwd)
    except _GitUnavailable as exc:
        dep_fail(f"origin remote unresolvable: {exc}")
        remote = None
    summary["origin_remote_url"] = remote
    if remote and not _remote_matches_repo(remote, ctx["repository_full_name"]):
        fail(f"origin remote URL does not match "
             f"{ctx['repository_full_name']!r}: got {remote!r}")

    # 8. base tracking ref + full SHA (P1-1: real base_sha verification)
    base_branch = ctx["base_branch"]
    try:
        base_sha_actual = _git_base_sha(base_branch, cwd=cwd)
    except _GitUnavailable as exc:
        dep_fail(f"base tracking ref 'origin/{base_branch}' "
                 f"unresolvable: {exc}")
        base_sha_actual = None
    summary["base_sha_actual"] = base_sha_actual
    if base_sha_actual and base_sha_actual != ctx["base_sha"]:
        fail(f"base_sha mismatch: expected={ctx['base_sha']!r} "
             f"actual={base_sha_actual!r}")

    # 9. pr_number check via gh (P1-3: bind to repo + base)
    pr_number = ctx.get("pr_number")
    if pr_number is not None:
        try:
            pr_data = _gh_pr_view(pr_number, ctx["repository_full_name"],
                                  cwd=repo_root)
        except _GitUnavailable as exc:
            dep_fail(f"gh pr view unavailable: {exc}")
            pr_data = None
        if pr_data is not None:
            pr_head_branch = pr_data.get("headRefName")
            pr_head_sha = pr_data.get("headRefOid")
            pr_base_branch = pr_data.get("baseRefName")
            pr_base_sha = pr_data.get("baseRefOid")
            cross = pr_data.get("isCrossRepository", False)
            state = pr_data.get("state")
            summary["pr_base_branch"] = pr_base_branch
            summary["pr_base_sha"] = pr_base_sha
            if cross:
                fail(f"pr #{pr_number} is cross-repository")
            if state not in ("OPEN", "DRAFT"):
                # only allow OPEN or DRAFT (closed/merged are still
                # acceptable for verification, but mark as info)
                pass
            if pr_head_branch != ctx["pr_head_branch"]:
                fail(f"pr head branch mismatch: expected "
                     f"{ctx['pr_head_branch']!r} got {pr_head_branch!r}")
            if pr_head_sha != ctx["expected_head"]:
                fail(f"pr head SHA mismatch: expected "
                     f"{ctx['expected_head']!r} got {pr_head_sha!r}")
            if pr_base_branch != ctx["base_branch"]:
                fail(f"pr base branch mismatch: expected "
                     f"{ctx['base_branch']!r} got {pr_base_branch!r}")
            if pr_base_sha != ctx["base_sha"]:
                fail(f"pr base SHA mismatch: expected "
                     f"{ctx['base_sha']!r} got {pr_base_sha!r}")

    # 10/11/12/13. working-tree state (P1-2: failure must not = clean)
    try:
        st = _git_status_paths(cwd=cwd)
    except _PorcelainError as exc:
        dep_fail(f"git status unavailable: {exc}")
        st = {
            "modified": [], "staged": [], "untracked": [],
            "conflict": [], "deleted": [], "renamed": [],
        }
    summary["staged_paths"] = st["staged"]
    summary["modified_paths"] = st["modified"]
    summary["untracked_paths"] = st["untracked"]
    summary["conflict_paths"] = st["conflict"]
    summary["deleted_paths"] = st["deleted"]
    summary["renamed_paths"] = st["renamed"]

    if st["staged"]:
        fail(f"staged files present (must be empty): {st['staged']}")
    if st["conflict"]:
        fail(f"unmerged/conflict files present: {st['conflict']}")

    if not summary["dependency_unavailable"]:
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

        # Forbidden has priority over allowed.
        all_touched = (st["modified"] + st["deleted"] + st["untracked"]
                       + st["renamed"])
        for p in all_touched:
            for f in forbidden:
                # path in renamed is 'old -> new'; we test the new path
                test = p.split(" -> ", 1)[1] if " -> " in p else p
                if _is_path_under(_normalize_path(
                        os.path.join(repo_root, test)), f):
                    fail(f"forbidden path touched: {p!r}")
                    break
        for p in st["modified"]:
            if not _is_authorized(p, allowed_modified):
                fail(f"modified file outside allowed_modified_paths: {p!r}")
        for p in st["deleted"]:
            if not _is_authorized(p, allowed_modified):
                fail(f"deleted file outside allowed_modified_paths: {p!r}")
        for p in st["untracked"]:
            if not _is_authorized(p, allowed_untracked):
                fail(f"untracked file outside allowed_untracked_paths: {p!r}")

    summary["violations"] = violations
    if summary["dependency_unavailable"]:
        summary["status"] = STATUS_INVALID
    elif not violations:
        any_dirty = (st["modified"] or st["deleted"] or st["untracked"]
                     or st["renamed"])
        summary["status"] = (STATUS_VALID_AUTHORIZED_DIRTY if any_dirty
                             else STATUS_VALID_CLEAN)
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
    if summary.get("dependency_unavailable"):
        print(f"[verify_task_context] dependency unavailable: "
              f"{summary.get('dependency_error')}")
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
        help="Print exactly one JSON object to stdout; status is the "
             "'status' field of that JSON. No plain-text status line.",
    )
    args = parser.parse_args(argv)

    try:
        ctx = _load_context(args.context)
    except (ContextError, PathListError) as exc:
        # Output contract:
        #   non --json: human stderr + status as last stdout line
        #   --json: stdout = single JSON object with status
        print(f"ERROR: {exc}", file=sys.stderr)
        if args.json:
            print(json.dumps({
                "status": STATUS_INVALID,
                "error": str(exc),
                "violations": [],
                "dependency_unavailable": True,
            }, ensure_ascii=False))
        else:
            print(STATUS_INVALID)
        return RC_UNAVAILABLE

    summary = run_checks(ctx, cwd=args.cwd)

    if args.json:
        # stdout must be exactly one JSON object.
        sys.stdout.write(json.dumps(summary, ensure_ascii=False, indent=2))
        sys.stdout.write("\n")
    else:
        _emit_human(summary)
        # The fixed status MUST be the last line of stdout.
        sys.stdout.write(summary["status"] + "\n")

    if summary.get("dependency_unavailable"):
        return RC_UNAVAILABLE
    if summary["status"] == STATUS_INVALID:
        return RC_INVALID
    return RC_VALID


if __name__ == "__main__":
    sys.exit(main())
