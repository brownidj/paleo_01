#!/usr/bin/env bash
set -euo pipefail

python3 scripts/check_import_boundaries.py
bash scripts/check_canonical_db_path.sh
python3 scripts/check_trip_event_integrity.py --db data/paleo_trips_01.db
bash scripts/check_types.sh
PYTHONWARNINGS=error::ResourceWarning python3 -m unittest -v
./scripts/check_file_sizes.sh .
