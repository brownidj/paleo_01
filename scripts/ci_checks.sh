#!/usr/bin/env bash
set -euo pipefail

python3 scripts/check_import_boundaries.py
bash scripts/check_types.sh
PYTHONWARNINGS=error::ResourceWarning python3 -m unittest -v
./scripts/check_file_sizes.sh .
