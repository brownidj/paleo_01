# ADR 0001: Architecture Boundaries

## Status
Accepted

## Context
The project has recently been decomposed into focused repository, UI controller/coordinator, and bootstrap modules.
Without explicit boundaries, import coupling can regress over time and blur responsibilities.

## Decision
We enforce lightweight import boundaries:

1. UI layer (`ui/**`) must not import migration/bootstrap internals or repository implementation modules directly.
UI should use the façade (`trip_repository`) and UI modules only.
2. Repository layer (`trip_repository.py`, `repository_*.py`, `trip_crud.py`, `location_geology.py`, `finds_collection_events.py`, `migrations_schema.py`) must not import UI modules or Tkinter.
3. Boundaries are defined in `scripts/import_boundary_rules.json` and enforced by `scripts/check_import_boundaries.py`.
4. Boundary checks are part of `scripts/ci_checks.sh`.

## Rule Evolution Protocol
When introducing a new module or layer:

1. Decide which layer it belongs to and which imports are allowed.
2. Update `scripts/import_boundary_rules.json`:
- Add file/path match patterns to an existing rule, or add a new rule block for the new layer.
- Add/adjust forbidden import prefixes and message text.
3. Re-run `python3 scripts/check_import_boundaries.py`.
4. Update this ADR if the architectural boundary model itself changes (not just file lists).

## Consequences
- Improves maintainability by preserving separation of concerns.
- Prevents accidental dependency cycles and framework leakage into data/domain code.
- Adds a small maintenance cost for boundary rule updates when architecture evolves.
