#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

python3 scripts/checks/check_import_boundaries.py
python3 scripts/checks/check_no_tracked_secrets.py
bash scripts/checks/check_canonical_db_path.sh
python3 scripts/checks/check_trip_event_integrity.py --db data/paleo_trips_01.db
bash scripts/checks/check_types.sh
PYTHONWARNINGS=error::ResourceWarning python3 -m unittest -v
./scripts/checks/check_file_sizes.sh .
