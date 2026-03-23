# Development-Only Seed Scripts

These scripts generate synthetic data for local demos and manual UI testing.

- They are not part of the production PBDB import/reconciliation pipeline.
- Canonical usage is via:
  - `python3 scripts/dev_seed/seed_locations.py`
  - `python3 scripts/dev_seed/seed_trips.py`
  - `python3 scripts/dev_seed/seed_users.py`
- Legacy wrapper entrypoints remain at:
  - `scripts/seed_locations.py`
  - `scripts/seed_trips.py`
  - `scripts/seed_users.py`
