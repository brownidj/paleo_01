# Scripts Layout

- `scripts/db/`: database lifecycle scripts (bootstrap, init, SQLite->Postgres migration, Postgres->SQLite sync, schema helpers).
- `scripts/checks/`: quality and policy checks used locally and in CI.
- `scripts/backend/`: Docker/Caddy backend stack bootstrap helpers.
- `scripts/dev_seed/`: development-only synthetic seed data tools.
- `scripts/accounts/`: account maintenance scripts.
- `scripts/data_ops/`: one-off and batch data maintenance/import/enrichment scripts.

Run scripts from the repository root so relative paths resolve consistently.
