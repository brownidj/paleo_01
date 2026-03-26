#!/usr/bin/env bash
set -euo pipefail

root_path_refs="$(rg -n --hidden --glob '!.git' --glob '!.venv' \
  '\$PROJECT_DIR\$/paleo_trips_01\.db\b' \
  .idea/runConfigurations .idea/dataSources.xml .idea/workspace.xml 2>/dev/null || true)"

if [[ -n "${root_path_refs}" ]]; then
  echo "Found disallowed root DB path references (use data/paleo_trips_01.db instead):"
  echo "${root_path_refs}"
  exit 1
fi

required_refs="$(rg -n --hidden --glob '!.git' --glob '!.venv' \
  'data/paleo_trips_01\.db' .idea/runConfigurations .idea/dataSources.xml .idea/workspace.xml 2>/dev/null || true)"
required_ref_count="$(printf '%s\n' "${required_refs}" | sed '/^$/d' | wc -l | tr -d ' ')"

if [[ "${required_ref_count}" -eq 0 ]]; then
  echo "No canonical DB path reference found in IDE/shared configs (expected data/paleo_trips_01.db)."
  exit 1
fi

echo "Canonical DB path check passed."
