

# CURRENT_STATE

## Code prompt

### Architecture & Separation of Concerns
- `main.py` or `main.dart` must not contain any wiring, domain logic, or infrastructure.
- Keep UI wiring, domain logic, and infrastructure separated. Domain must not import infra or UI.
- Prefer thin orchestrators and small, focused services. Use explicit service helpers for UI side effects.
- Avoid direct dialog/widget mutations across layers; use adapters/services (for example, `CategoryManagerUIService`, `AddEditStateService`).
- Keep init/builders as composition roots; do not leak logic into UI builders.
- Prefer explicit dependencies via small dataclasses/services rather than hidden attribute reach-through.

### Readability & Maintainability
- Use clear, short functions with single responsibility. Extract helpers when logic grows.
- Avoid `getattr`/duck typing in production flow unless truly necessary; prefer adapters/registries.
- Write defensive UI code (best-effort; never crash), but keep error handling narrow and intentional.
- Keep naming consistent with existing patterns: `*Service`, `*Controller`, `*Coordinator`, `*Effects`, `*Rules`.
- Always add explicit error types in try/catch.

### File Size Constraint
- Keep each file under 300 lines. If a file approaches 300, split it into focused modules.
- Make a script to do this at regular intervals, adjusted for the local project.

Example:

```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="${1:-.}"
if ! command -v rg >/dev/null 2>&1; then
  echo "rg (ripgrep) is required." >&2
  exit 1
fi
rg --files "$ROOT_DIR" \
  | rg -v "^${ROOT_DIR}/assets/" \
  | rg -v "^${ROOT_DIR}/pubspec.lock$" \
  | rg -v "^${ROOT_DIR}/ios/Runner.xcodeproj/project.pbxproj$" \
  | rg -v "^${ROOT_DIR}/macos/Runner.xcodeproj/project.pbxproj$" \
  | xargs wc -l \
  | awk '$2 != "total" && $1 > 300 {print $1, $2; found=1} END{exit found?1:0}'
```

### Testing & Refactors
- Always consider adding new tests, even small ones, and always make appropriate suggestions.
- Add small pure tests for new services/helpers when behavior might regress.
- Preserve behavior; refactors should be test-driven and avoid hidden side effects.
- Add Flutter integration tests to test the UI, especially for iOS.
- Consider using Patrol for Android UI tests.
- Remind me to run tests when appropriate.
- Remind me to run manual tests when appropriate.

### Coding Style
- Prefer explicit imports. Avoid large inline logic inside UI event handlers.
- Keep log noise low; log failures only in hot paths.

### Output
- Make changes in one pass; keep diffs minimal and focused.
- Maintain a `CURRENT_STATE.md` file that contains this prompt at the top of the file, then the state of the code base architecture, then a report of running any tests.

### Debugging
- Add a debugging code system that allows all debug code to be turned off.
- When debug code is added, make sure it complies with this prerequisite.

### Git
- Remind me to commit and push when appropriate.
- Before doing large-scale refactoring, remind me to change to a refactoring branch.

## If a database is required

### Database requirements
- Use the built-in `sqlite3` library unless there is a strong reason otherwise.
- Organize the code clearly, with separation between:
  1. database connection/setup
  2. schema creation
  3. CRUD operations
  4. utility/helper functions
- Include clear comments throughout.
- Use parameterized queries everywhere to prevent SQL injection.
- Use context managers or another safe pattern to ensure connections and transactions are handled correctly.
- Include proper error handling for database operations.
- Design the code so it can be reused in a larger application.

### Database expectations
- Create the database file if it does not already exist.
- Define a schema using `CREATE TABLE IF NOT EXISTS`.
- Include a primary key for each table.
- Add appropriate foreign keys, unique constraints, default values, and indexes where sensible.
- Enable foreign key enforcement.
- Include a function to initialize the database schema.

### Database coding expectations
- Use classes or well-structured functions, whichever is more appropriate for clarity and maintainability.
- Include type hints where reasonable.
- Avoid overly clever abstractions; prefer readable, practical code.
- Make the design easy to extend with additional tables later.
- Return query results in a convenient format, such as tuples, dictionaries, or lightweight objects, and be consistent.

### Database functionality to include
- Connect to the SQLite database.
- Initialize schema.
- Insert records.
- Fetch one record.
- Fetch multiple records.
- Update records.
- Delete records.
- Optionally search/filter records.
- Optionally support soft delete if appropriate.

### Database testing/demo expectations
- Include a short example showing how to initialize the database and perform basic CRUD operations.
- Include sample table definitions and example usage data.

### Database output expectations
- After the code, briefly explain the structure and design decisions.
- Do not omit important implementation details.

## Code base architecture state

- **Architecture**: Planning-phase desktop app only (Tkinter + SQLite), with `Trips`, `Location`, `Geology`, `Collection Events`, `Finds`, `Collection Plan`, and `Team Members` tabs.
  - **Infrastructure/Init**:
    - `scripts/db_bootstrap.py`: thin bootstrap/orchestration + API re-export layer for seed/init scripts.
      - Uses explicit stepwise schema migrations via `PRAGMA user_version` (`SCHEMA_VERSION = 2`).
    - `scripts/db_schema_helpers.py`: schema creation helpers (`Users`, `Trips`, `Locations`, `Finds`) and field normalization.
    - `scripts/db_migration_helpers.py`: legacy migration/rebuild helpers for trips/locations/trip-locations.
    - `scripts/ci_checks.sh`: strict local/CI quality gate (import-boundary check + `PYTHONWARNINGS=error::ResourceWarning` tests + file-size check).
    - `scripts/check_import_boundaries.py`: lightweight AST-based import-boundary enforcement.
      - Rules are config-driven via `scripts/import_boundary_rules.json` for easier evolution as modules/layers change.
    - `scripts/check_types.sh` + `mypy.ini`: scoped static typing gate for repository + UI-controller modules.
    - `docs/adr/0001-architecture-boundaries.md`: architecture boundary decision record.
    - `scripts/init_db.py`: CLI initializer.
  - **Repository**:
    - `trip_repository.py`: thin façade that composes focused modules; external `TripRepository` API remains unchanged.
    - `trip_crud.py`: trip and user CRUD/list domain surface.
    - `location_geology.py`: location + geology data access surface.
    - `finds_collection_events.py`: finds and collection-event query surface.
    - `migrations_schema.py`: schema setup and legacy migration surface.
    - Supporting internal modules:
      - `repository_base.py`: connection/transaction lifecycle (`commit`/`rollback` + guaranteed `close`) and shared constants.
      - `repository_trip_user.py`, `repository_location.py`, `repository_finds.py`, `repository_geology_schema.py`, `repository_geology_data.py`, `repository_migrations.py`.
    - `domain_types.py`: typed payload/row structures for core entities (Trip, Location/CollectionEvent, Find, Geology).
  - **UI Entrypoints**:
    - `main.py` and `planning_phase_main.py` launch `PlanningPhaseWindow` only (thin entrypoints).
  - **UI Modules**:
    - `ui/planning_phase_window.py`: composition root for tabs, dialog controller, navigation coordinator, and app palette.
    - `ui/planning_tabs_controller.py`: notebook tab construction and initial tab-data loading.
    - `ui/trip_navigation_coordinator.py`: Trips ↔ Collection Events/Finds handoff, tab-change loading, hidden dialog restore, trip row reselection.
    - `ui/trip_dialog_controller.py`: trip dialog orchestration (new/edit/copy and open-dialog lifecycle).
    - `ui/trip_form_dialog.py`: Trip edit form with guarded edit mode (`Edit` toggle), icon chip actions, and cross-tab handoff hooks for `Collection Events` and `Finds`.
    - `ui/geology_tab.py`, `ui/geology_form_dialog.py`: geology listing/details and edit dialog.
    - `ui/trip_filter_tree_tab.py`: shared base for list tabs with `Trip filter` radio behavior + tree population.
    - `ui/collection_events_tab.py`: collection event listing; now uses shared trip-filter/tree base.
    - `ui/finds_tab.py`: finds listing; now uses shared trip-filter/tree base.
    - `ui/team_editor_dialog.py`: active-user selector for team assignment.
    - `ui/location_picker_dialog.py`: location selector for trip location list.
    - `ui/location_tab.py`, `ui/location_form_dialog.py`: location CRUD + collection-events editing.
    - `ui/users_tab.py`, `ui/user_form_dialog.py`: users CRUD (no delete in UI flow).
  - **Seeding**:
    - `scripts/seed_users.py`: users with fixed AU phone and active split.
    - `scripts/seed_locations.py`: fake locations; supports `--truncate`; optional one-time cardinal variants from first-pass records.
    - `scripts/seed_trips.py`: trips seeded from existing locations, writes `TripLocations`, supports second-pass multi-location trip generation via random boolean on similar-location matches.
- **Planning Database (`paleo_trips_01.db`)**:
  - `Users(id, name, phone_number, active)`
  - `Trips(id, trip_name, start_date, end_date, team, location, notes)` (`region` removed)
  - `Locations(id, name, latitude, longitude, altitude_value, altitude_unit, country_code, state, lga, basin, geogscale, geography_comments, geology_id)`
  - `CollectionEvents(id, location_id, collection_name, collection_subset)` (0..many per location)
  - `TripLocations(id, location_id)` (many-to-many between trips and locations)
  - `GeologyContext(id, location_id, location_name, source_system, source_reference_no, early_interval, late_interval, max_ma, min_ma, environment, geogscale, geology_comments, formation, stratigraphy_group, member, stratscale, stratigraphy_comments, geoplate, paleomodel, paleolat, paleolng, created_at, updated_at)`
  - `Lithology(id, geology_context_id, slot, lithology, lithification, minor_lithology, lithology_adjectives, fossils_from, created_at, updated_at)`
  - `Finds(id, trip_id, location_id, collection_event_id, source_system, source_occurrence_no, identified_name, accepted_name, identified_rank, accepted_rank, difference, identified_no, accepted_no, phylum, class_name, taxon_order, family, genus, abund_value, abund_unit, reference_no, taxonomy_comments, occurrence_comments, research_group, notes, created_at, updated_at)`
- **Behavioral Notes**:
  - Trips use integer `id` auto-increment; no `trip_code`.
  - `team` and `location` list values are semicolon-separated.
  - `region -> location` migration exists; `region` column is removed in migration rebuild.
  - UI palette/theme is applied centrally in `PlanningPhaseWindow`.
  - Trip Record editability is gated by `Edit` (off by default): with `Edit` off, fields are read-only and team/location editor chips are disabled.
  - Closing Trip Record auto-saves changed fields; turning `Edit` from on to off also auto-saves changed fields.
  - From Trip Record, `Collection Events`/`Finds` chips switch tabs, turn trip filter on, and apply trip-specific filtering; returning to `Trips` restores the hidden Trip Record and reselects that trip.
  - Trip filtering in `Collection Events` is now strict to finds explicitly assigned to that trip (via `Finds.trip_id`), not broad location-level membership.
  - **Prompt Compliance Snapshot**:
  - `main.py` remains thin: **compliant**.
  - DB layer uses parameterized queries and context managers: **compliant**.
  - File size <= 300 rule: **compliant**.
    - `trip_repository.py` and `ui/planning_phase_window.py` are now compliant.
    - `scripts/db_bootstrap.py` is now compliant.

## Codebase Goodness Assessment (vs prompt)

- **Overall rating**: **Strong (about 8.5/10)** for behavior stability, DB safety, and architecture clarity after repository/UI/bootstrap/test decomposition.
- **Strong areas**:
  - Thin entrypoints and clear app bootstrap flow are intact.
  - Core DB work is pragmatic and robust (parameterized SQL, explicit transaction/close handling, schema/migration separation).
  - High-change UI behavior is now isolated via dedicated controllers/coordinator and covered by regression tests.
  - Current automated suite is stable (all tests passing) and test modules are domain-focused.
  - File-size constraint is now satisfied across the codebase.
  - Internal repository/controller interfaces now use typed payload structures, reducing `dict[str, Any]` usage.
- **Weak areas / debt**:
  - Legacy migration coverage is now exhaustive across currently known trip/location/trip-location historical schema permutations; risk now shifts to truly unknown future-discovered legacy variants.
  - UI flow coverage now includes smoke plus a higher-level handoff/filter-toggle/restore path; additional edge-case UI journeys can still be expanded over time.
  - Mypy is now enforced for a scoped module set; broader project-wide typing coverage is still incremental.

## Recommendations

1. Keep quality-gate execution centralized.
Use `scripts/ci_checks.sh` as the default local/CI check entrypoint for all refactor batches.
2. Keep `docs/CURRENT_STATE.md` synced after each refactor batch.
Update architecture, schema, and test totals whenever meaningful codebase changes land.
3. Continue widening typed coverage.
Expand mypy scope module-by-module beyond current repository/UI-controller targets as annotations mature.
4. Keep exhaustive migration matrix current.
When new historical variants are discovered, add them to the exhaustive permutation tests and keep stepwise migrations idempotent.
5. Add one or two additional edge-path UI integration scenarios.
Build on current smoke + handoff/filter-toggle coverage with cases such as edit-mode transition persistence and validation-failure journeys.

## Test run report

- **2026-03-23 (current reassessment)**:
  - `python3 -m unittest -v`: **PASSED**
    - Total: **33 passed**
  - `bash scripts/ci_checks.sh`: **PASSED**
    - Includes: import-boundary check + mypy (`scripts/check_types.sh`) + warnings-as-errors unittest + file-size check
  - `./scripts/check_file_sizes.sh .`: **PASSED**
