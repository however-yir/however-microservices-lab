#!/usr/bin/env bash
set -euo pipefail

# Repository contract tests: protect baseline repo quality from regressions.
required_files=(
  "README.md"
  "LICENSE"
  "CONTRIBUTING.md"
  ".github/SECURITY.md"
  ".github/dependabot.yml"
  ".github/workflows/codeql.yml"
  ".github/workflows/repo-contract-ci.yml"
  "docs/ENGINEERING_QUALITY.md"
)

failures=0
for f in "${required_files[@]}"; do
  if [[ ! -e "$f" ]]; then
    echo "[FAIL] missing required file: $f"
    failures=$((failures + 1))
  else
    echo "[PASS] found: $f"
  fi
done

if [[ ! -d tests ]]; then
  echo "[FAIL] tests/ directory is required"
  failures=$((failures + 1))
else
  echo "[PASS] tests/ directory exists"
fi

if [[ ! -d docs ]]; then
  echo "[FAIL] docs/ directory is required"
  failures=$((failures + 1))
else
  echo "[PASS] docs/ directory exists"
fi

if [[ "$failures" -gt 0 ]]; then
  echo "Repository contract check failed with $failures issue(s)."
  exit 1
fi

echo "Repository contract checks passed."