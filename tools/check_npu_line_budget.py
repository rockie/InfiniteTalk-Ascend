#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NPU line budget enforcer (NFR-02 hard gate).

Purpose
-------
Enforce a per-file ≤80-line "added" budget on the 5 main-path files pinned by
PRD § NFR-02, measured against a frozen upstream baseline commit. This is the
single source of truth invoked by both:

  1. CI workflow:   .github/workflows/npu-line-budget.yml
  2. pre-commit:    tools/pre-commit-npu-line-budget.sh

(AC-7: DRY — both entry points MUST call this same script. No duplicated
budget-calculation logic anywhere else.)

Algorithm
---------
For each tracked file F in TRACKED_FILES (and not in the ignore-list):

    added = column-1 of `git diff --numstat <BASELINE_COMMIT> -- F`

If `added > 80` for any tracked file, exit non-zero and list every offender.

Why `git diff <baseline> -- F` (working-tree form), not `<baseline>..HEAD`
-------------------------------------------------------------------------
AC-1 phrases the rule as `git diff --numstat <baseline_commit>..HEAD`. We
use the working-tree form (`git diff --numstat <baseline>`) instead because
it is a *strict superset* that satisfies AC-1 in CI and AC-2 at pre-commit
time:

  - In CI, the working tree is identical to HEAD (no staged or unstaged
    edits during a fresh checkout), so `git diff <baseline>` collapses to
    `git diff <baseline>..HEAD` — AC-1's literal expression — verbatim.
  - At pre-commit time, the change about to be committed is already staged
    but not yet in HEAD. AC-2 demands "cumulative additions on that file
    vs upstream baseline" — that's the working-tree form, by construction.
    Using `<baseline>..HEAD` here would *miss* the staged change, defeating
    the hook (AC-2 would silently fail).

Using one form for both entry points is what makes AC-7 (DRY, single
script) physically possible. Using `<baseline>..HEAD` would force a second
diff branch for pre-commit — exactly what AC-7 forbids.

Why "added" only (not "added + deleted")
----------------------------------------
`git diff --numstat` emits exactly two columns: `<added>\\t<deleted>`. There is
no "modified" column; a modification of an existing line shows up as
`1 added + 1 deleted`. Per PRD § NFR-02 § 行数计量规则, deleted lines do NOT
consume budget — therefore the "added" column alone covers both pure additions
and modifications (the deletion half of any modification is correctly ignored).

Blank lines and comment lines DO count toward budget (conservative — prevents
cosmetic "delete-then-add as comment" tricks from gaming the gate).

Baseline anchoring
------------------
BASELINE_COMMIT is **pinned** (literal hash, not `origin/main`). Bumping is
restricted to Story 5.2 (J4 Upstream Sync Drill) — see Dev Notes in
_gomad-output/implementation-artifacts/1-1-npu-branch-infrastructure.md.

If you hit this gate, the architecturally-sanctioned fix paths are:
    (a) Externalize the new NPU code into a dedicated wrapper / monkey-patch
        file outside the 5-file main-path list (NFR-03 dual constraint —
        adapter layer must be revertable as a coherent set).
    (b) Add the file to tools/npu-line-budget-ignore.txt with explicit
        rationale, and obtain PR review approval.

Output format (machine-parseable, per NFR-10 弱依赖)
----------------------------------------------------
Per offending file, one line on stderr:
    [NPU LINE BUDGET] <file>: <N> lines exceed 80-line budget vs <baseline>

Per file (offending or not), one line on stdout:
    <file>:<added_count>

This dual-stream format lets J5 acceptance scripts grep stdout while CI logs
surface the human-readable error on stderr.

Exit codes
----------
    0  — all tracked files within budget
    1  — at least one tracked file exceeds budget
    2  — environment error (not a git repo, baseline missing, etc.)
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

# ---------------------------------------------------------------------------
# Pinned constants (DO NOT change casually — see module docstring)
# ---------------------------------------------------------------------------

# Initial baseline = upstream main HEAD at PRD authoring time (commit fd63149).
# Bump only via Story 5.2 J4 rebase drill; record old→new in CHANGELOG-NPU.md.
BASELINE_COMMIT: str = "fd631497254e065777f2b2d0642de3600d674e24"

# 5 main-path files pinned by PRD § NFR-02. Order is irrelevant for the
# algorithm; this list is the *single source of truth* for which files
# participate in the 80-line budget.
TRACKED_FILES: Tuple[str, ...] = (
    "wan/modules/attention.py",
    "wan/multitalk.py",
    "wan/distributed/xdit_context_parallel.py",
    "generate_infinitetalk.py",
    "app.py",
)

LINE_BUDGET: int = 80

# Ignore-list path is pinned per AC-4 / Task 2.1.
IGNORE_LIST_PATH: str = "tools/npu-line-budget-ignore.txt"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _repo_root() -> Path:
    """Return the git repo root (where .git lives), via `git rev-parse`."""
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            stderr=subprocess.PIPE,
            text=True,
        )
        return Path(out.strip())
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(
            f"[NPU LINE BUDGET] FATAL: not inside a git repo ({exc})",
            file=sys.stderr,
        )
        sys.exit(2)


def _baseline_exists(repo_root: Path) -> bool:
    """Return True if BASELINE_COMMIT is reachable in this clone."""
    try:
        subprocess.check_output(
            ["git", "cat-file", "-e", f"{BASELINE_COMMIT}^{{commit}}"],
            stderr=subprocess.PIPE,
            cwd=repo_root,
            text=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def _read_ignore_list(repo_root: Path) -> List[str]:
    """Parse ignore-list. Each line: '<file_path> # <reason>'.

    Empty lines and bare '#' comment lines are skipped. The reason is
    informational only (not consumed here — it's for human reviewers).
    """
    path = repo_root / IGNORE_LIST_PATH
    if not path.is_file():
        return []
    ignored: List[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # Strip trailing '# reason'.
        file_path = line.split("#", 1)[0].strip()
        if file_path:
            ignored.append(file_path)
    return ignored


def _added_lines(repo_root: Path, file_path: str) -> int:
    """Return the 'added' column from `git diff --numstat <baseline> -- F`.

    Working-tree form (no `..HEAD`) — see module docstring for the AC-1/AC-2
    rationale. Returns 0 if the file matches baseline. Binary files (numstat
    shows '-') are treated as 0 added (binary changes do not consume the
    line budget — they are out of scope for this gate).
    """
    try:
        out = subprocess.check_output(
            [
                "git",
                "diff",
                "--numstat",
                BASELINE_COMMIT,
                "--",
                file_path,
            ],
            stderr=subprocess.PIPE,
            cwd=repo_root,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        print(
            f"[NPU LINE BUDGET] FATAL: git diff failed for {file_path}: "
            f"{exc.stderr.strip() if exc.stderr else exc}",
            file=sys.stderr,
        )
        sys.exit(2)

    out = out.strip()
    if not out:
        return 0
    # numstat may emit multiple lines if the path matched a directory; with
    # an explicit `-- <file>` we expect at most one line, but be defensive.
    total = 0
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        added_col = parts[0]
        if added_col == "-":  # binary
            continue
        try:
            total += int(added_col)
        except ValueError:
            continue
    return total


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    repo_root = _repo_root()

    if not _baseline_exists(repo_root):
        print(
            f"[NPU LINE BUDGET] FATAL: baseline commit {BASELINE_COMMIT} "
            "is not reachable. Did you `git fetch` enough history? "
            "(CI must use fetch-depth: 0 or unshallow.)",
            file=sys.stderr,
        )
        return 2

    ignored = set(_read_ignore_list(repo_root))
    effective_tracked = [f for f in TRACKED_FILES if f not in ignored]

    offenders: List[Tuple[str, int]] = []

    for file_path in effective_tracked:
        added = _added_lines(repo_root, file_path)
        # Machine-parseable stdout line (NFR-10 弱依赖).
        print(f"{file_path}:{added}")
        if added > LINE_BUDGET:
            offenders.append((file_path, added))

    if offenders:
        for file_path, added in offenders:
            print(
                f"[NPU LINE BUDGET] {file_path}: {added} lines exceed "
                f"{LINE_BUDGET}-line budget vs {BASELINE_COMMIT[:7]}",
                file=sys.stderr,
            )
        print(
            "[NPU LINE BUDGET] Fix paths: (a) externalize code into a "
            "wrapper/monkey-patch file off the main-path list, or (b) add "
            f"the file to {IGNORE_LIST_PATH} with explicit rationale + PR "
            "review.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
