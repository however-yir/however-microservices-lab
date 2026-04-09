#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR"

CHANGELOG_FILE="CHANGELOG.md"
DATE_STR="$(date '+%Y-%m-%d')"
TMP_FILE="$(mktemp)"

if [[ ! -f "$CHANGELOG_FILE" ]]; then
  cat > "$CHANGELOG_FILE" <<EOF
# Changelog

All notable changes to this project will be documented in this file.
EOF
fi

{
  echo "## ${DATE_STR}"
  git log --no-merges --pretty='- %h %s' -n 20
  echo
} > "$TMP_FILE"

if grep -q "## ${DATE_STR}" "$CHANGELOG_FILE"; then
  echo "Changelog already updated for ${DATE_STR}, skip."
  rm -f "$TMP_FILE"
  exit 0
fi

cat "$TMP_FILE" "$CHANGELOG_FILE" > "${CHANGELOG_FILE}.new"
mv "${CHANGELOG_FILE}.new" "$CHANGELOG_FILE"
rm -f "$TMP_FILE"

echo "Changelog updated."
