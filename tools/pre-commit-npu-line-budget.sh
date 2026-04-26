#!/usr/bin/env bash
# tools/pre-commit-npu-line-budget.sh
# ===================================
# Pre-commit hook: enforce PRD § NFR-02 ≤80-line budget on the 5 main-path
# files BEFORE the commit lands locally. Companion to the CI gate at
# .github/workflows/npu-line-budget.yml.
#
# AC-7 (DRY hard constraint): this hook MUST invoke the same Python script
# used by CI — tools/check_npu_line_budget.py. Do NOT duplicate budget logic
# here. This wrapper exists only to (a) bridge the git-hook contract and (b)
# emit a friendly hint about --no-verify on block.
#
# Mode (AC-2):
#   - Default = BLOCK. Exits non-zero if any main-path file is over budget;
#     git aborts the commit.
#   - Emergency bypass = `git commit --no-verify`. CI gate still catches it,
#     so a hook-bypassed commit will fail the PR build (AC-2 second clause).
#
# Installation (one-time, per developer clone):
#
#     # Option A (zero deps): symlink into .git/hooks
#     ln -sf ../../tools/pre-commit-npu-line-budget.sh .git/hooks/pre-commit
#
#     # Option B (pre-commit framework, if .pre-commit-config.yaml is wired):
#     pre-commit install
#
# Note: README-NPU.md is intentionally NOT created by Story 1.1 — that's
# Story 1.7's deliverable. Install instructions live here (and in the CI
# workflow) until then to avoid stub-then-extend drag on Story 1.7.

set -euo pipefail

# Resolve repo root robustly even if the hook is invoked from a sub-dir.
REPO_ROOT="$(git rev-parse --show-toplevel)"

# Invoke the shared script (AC-7 DRY).
if ! python3 "${REPO_ROOT}/tools/check_npu_line_budget.py"; then
  echo ""
  echo "[NPU LINE BUDGET] Commit blocked by pre-commit hook (NFR-02)."
  echo "Emergency bypass: git commit --no-verify  (CI gate will still run.)"
  exit 1
fi

exit 0
