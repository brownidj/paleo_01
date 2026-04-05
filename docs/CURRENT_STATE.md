

# CURRENT_STATE

## Code prompt

### Architecture & Separation of Concerns
- Establish an architecture that sets explicit boundaries between UI, domain, and infrastructure layers. This should be reflected in the directory structure.
- Avoid dumping new files in the project root; just keep main.py there.
- `main.py` or `main.dart` must not contain any wiring, domain logic, or infrastructure.
- Keep UI wiring, domain logic, and infrastructure separated. Domain must not import infra or UI.
- Prefer thin orchestrators and small, focused services. Use explicit service helpers for UI side effects.
- Avoid direct dialog/widget mutations across layers; use adapters/services (for example, `CategoryManagerUIService`, `AddEditStateService`).
- Keep init/builders as composition roots; do not leak logic into UI builders.
- Prefer explicit dependencies via small dataclasses/services rather than hidden attribute reach-through.

### Readability & Maintainability
- Use clear, short functions with a single responsibility. Extract helpers when logic grows.
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
- Avoid leaving brittle wrappers behind when refactoring code.
- Always start major refactoring in a new branch.

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

- **Architecture**: Planning-phase desktop app (Tkinter) with dual data backends:
  - SQLite via `TripRepository` (legacy/local workflows and tests)
  - PostgreSQL via `PostgresTripRepository` (primary runtime path)
  - Optional backend API auth (`/v1/auth/*`) with JWT access/refresh tokens
  - Tabs: `Trips`, `Collection Plan`, `Location`, `Collection Events`, `Finds`, `Team Members`, `Geology`
  - **Infrastructure/Init**:
    - `scripts/db/bootstrap.py`: thin bootstrap/orchestration + API re-export layer for seed/init scripts.
      - Uses explicit stepwise schema migrations via `PRAGMA user_version` (`SCHEMA_VERSION = 7`).
    - `scripts/db/schema_helpers.py`: schema creation helpers (`Team_members`, `Trips`, `Locations`, `Finds`) and field normalization.
    - `scripts/db/migration_helpers.py`: legacy migration/rebuild helpers for trips/locations/trip-locations.
    - `scripts/checks/ci_checks.sh`: strict local/CI quality gate (import-boundary check + `PYTHONWARNINGS=error::ResourceWarning` tests + file-size check).
    - `scripts/checks/check_import_boundaries.py`: lightweight AST-based import-boundary enforcement.
      - Rules are config-driven via `scripts/checks/import_boundary_rules.json` for easier evolution as modules/layers change.
    - `scripts/checks/check_types.sh` + `config/mypy.ini`: expanded static typing gate covering backend/runtime, repository, UI controllers/windows, and scripts (`db`, `checks`, `accounts`, `data_ops`, `dev_seed`).
    - `docs/adr/0001-architecture-boundaries.md`: architecture boundary decision record.
    - `scripts/README.md`: scripts layout guide (`db/`, `checks/`, `backend/`, `dev_seed/`, `accounts/`, `data_ops/`).
    - `scripts/db/init_db.py`: CLI initializer.
    - Deployment/runtime files moved out of project root:
      - `deploy/docker/docker-compose.yml`
      - `deploy/docker/docker-compose.internet.yml`
      - `deploy/docker/docker-compose.dbtool.yml`
      - `deploy/caddy/Caddyfile`
      - `deploy/caddy/Caddyfile.internet`
      - `config/env/local.env(.example)`, `config/env/staging.env(.example)`, `config/env/prod.env(.example)`
  - **Repository**:
    - `repository/trip_repository.py`: thin façade that composes focused modules; external `TripRepository` API remains unchanged.
    - `repository/trip_crud.py`: trip and user CRUD/list domain surface.
    - `repository/location_geology.py`: location + geology data access surface.
    - `repository/finds_collection_events.py`: finds and collection-event query surface.
    - `repository/migrations_schema.py`: schema setup and legacy migration surface.
    - Supporting internal modules:
      - `repository/repository_base.py`: connection/transaction lifecycle (`commit`/`rollback` + guaranteed `close`) and shared constants.
      - `repository/repository_trip_user.py`, `repository/repository_location.py`, `repository/repository_finds.py`, `repository/repository_geology_schema.py`, `repository/repository_geology_data.py`, `repository/repository_migrations.py`.
    - `repository/domain_types.py`: typed payload/row structures for core entities (Trip, Location/CollectionEvent, Find, Geology).
  - **UI Entrypoints**:
    - `main.py` at project root is the canonical executable entrypoint and launches login + `PlanningPhaseWindow`.
    - Shared IDE run config points to `$PROJECT_DIR$/main.py`.
  - **UI Modules**:
    - `ui/planning_phase_window.py`: composition root for tabs, dialog controller, navigation coordinator, and app palette.
    - `ui/planning_phase_window_palette.py`: palette/theme application extracted from `planning_phase_window`.
    - `ui/planning_phase_window_selection.py`: trip selection persistence/toast/path helpers extracted from `planning_phase_window`.
    - `ui/planning_tabs_controller.py`: notebook tab construction and initial tab-data loading.
    - `ui/trip_navigation_coordinator.py`: Trips ↔ Collection Events/Finds/Team Members handoff, tab-change loading, hidden dialog restore, trip row reselection.
    - `ui/trip_dialog_controller.py`: trip dialog orchestration (new/edit/copy and open-dialog lifecycle).
    - `ui/trip_form_dialog.py`: Trip edit form with guarded edit mode (`Edit` toggle), icon chip actions, and cross-tab handoff hooks for `Collection Events`, `Finds`, and `Team`.
    - `ui/trip_form_dialog_pickers.py`: team/location picker helpers extracted from `trip_form_dialog`.
    - `ui/geology_tab.py`, `ui/geology_form_dialog.py`: geology listing/details and edit dialog.
    - `ui/trip_filter_tree_tab.py`: shared base for list tabs with `Trip filter` radio behavior + tree population.
    - `ui/collection_events_tab.py`: collection event listing; now uses shared trip-filter/tree base.
    - `ui/finds_tab.py`: finds listing; now uses shared trip-filter/tree base.
    - `ui/team_editor_dialog.py`: active-user selector for team assignment.
    - `ui/location_picker_dialog.py`: location selector for trip location list.
    - `ui/location_tab.py`, `ui/location_form_dialog.py`: location CRUD + collection-events editing.
    - `ui/team_members_tab.py`, `ui/team_member_form_dialog.py`: team-members CRUD (no delete in UI flow) with optional trip-scoped filter mode.
  - **Seeding**:
    - `scripts/dev_seed/seed_users.py`: development-only synthetic team-member seeding (fixed AU phone + active split).
    - `scripts/dev_seed/seed_locations.py`: development-only synthetic location seeding; supports `--truncate`; optional one-time cardinal variants from first-pass records.
    - `scripts/dev_seed/seed_trips.py`: development-only synthetic trip seeding from existing locations; writes `TripLocations`; optional second-pass multi-location trip generation.
    - `scripts/accounts/seed_user_accounts_from_team_members.py`: creates/updates `User_Accounts` from `Team_members`.
  - **Migration/Sync**:
    - `scripts/db/migrate_sqlite_to_postgres.py`: bulk migration from SQLite to PostgreSQL with schema prep and identity sync.
    - `scripts/db/migrate_sqlite_to_postgres_schema_helpers.py`: schema/truncate/upsert/sequence helpers extracted from migrate script.
    - `scripts/db/sync_postgres_to_sqlite.py`: one-way mirror sync (PostgreSQL -> SQLite) with null/default coercion and column mapping.
  - **Postgres Repository Split**:
    - `repository/postgres_trip_repository.py`: connection + trip/team core surface.
    - `repository/postgres_trip_repository_domain.py`: location/finds/geology/collection-event domain operations.
  - **Auth Split**:
    - `backend/app/auth.py`: auth endpoints and token/database orchestration.
    - `backend/app/auth_models.py`: auth request/response/dataclass models.
  - **Bootstrap Imports**:
    - `scripts/db/*` modules now use stable package imports (`scripts.db.*`) with fallback import branches removed.
- **Planning Database (`data/paleo_trips_01.db`)**:
  - `Team_members(id, name, phone_number, institution, recruitment_date, retirement_date, active)`
  - `Trips(id, trip_name, start_date, end_date, team, location, notes)` (`region` removed)
  - `Locations(id, name, latitude, longitude, altitude_value, altitude_unit, country_code, state, lga, basin, proterozoic_province, orogen, geogscale, geography_comments, geology_id)`
  - `CollectionEvents(id, trip_id, location_id, collection_name, collection_subset, event_year)` (0..many per location, trip-linked, single-year events)
  - `TripLocations(id, location_id)` (many-to-many between trips and locations)
  - `GeologyContext(id, location_id, location_name, source_system, source_reference_no, early_interval, late_interval, max_ma, min_ma, environment, geogscale, geology_comments, formation, stratigraphy_group, member, stratscale, stratigraphy_comments, geoplate, paleomodel, paleolat, paleolng, created_at, updated_at)`
  - `Lithology(id, geology_context_id, slot, lithology, lithification, minor_lithology, lithology_adjectives, fossils_from, created_at, updated_at)`
  - `Finds(id, location_id, collection_event_id, source_system, source_occurrence_no, identified_name, accepted_name, identified_rank, accepted_rank, difference, identified_no, accepted_no, phylum, class_name, taxon_order, family, genus, abund_value, abund_unit, reference_no, taxonomy_comments, occurrence_comments, research_group, notes, collection_year_latest_estimate, created_at, updated_at)`
- **Behavioral Notes**:
  - Trips use integer `id` auto-increment; no `trip_code`.
  - `team` and `location` list values are semicolon-separated.
  - `region -> location` migration exists; `region` column is removed in migration rebuild.
  - UI palette/theme is applied centrally in `PlanningPhaseWindow`.
  - Trip Record editability is gated by `Edit` (off by default): with `Edit` off, fields are read-only and team/location editor chips are disabled.
  - Closing Trip Record auto-saves changed fields; turning `Edit` from on to off also auto-saves changed fields.
  - From Trip Record, `Collection Events`/`Finds` chips switch tabs, turn trip filter on, and apply trip-specific filtering; returning to `Trips` restores the hidden Trip Record and reselects that trip.
  - From Trip Record, `Team` chip switches to `Team Members`, turns Trip filter on, and filters members to names listed in that trip’s `team` value.
  - Trip filtering in `Collection Events`/`Finds` is now event-owned: trip context is derived via `CollectionEvents.trip_id` (legacy `Finds.trip_id` removed).
  - Full PBDB re-import is currently loaded in the working DB (`Finds = 2068`) with all finds linked to `Locations` and `CollectionEvents`.
  - `collection_year_latest_estimate` is populated from inferred publication year minus a random 2..6 year offset.
  - Team-member bulk population from `data/team_members_from_pbdb_data-2_publication_enriched.csv` is currently loaded (`Team_members = 142`), with recruitment/retirement date rules applied and later date-window widening for mandatory trip assignments.
  - Team-member assignment to trips has been generated from publication authors plus random eligible additions; no trips are currently left without `team` members.
  - Publication-mandatory team assignments are now date-consistent after widening affected team-member recruitment/retirement windows (`mandatory_assignments_outside_date_window = 0`).
  - QLD structural framework backfill has been applied for location context fields using point-in-polygon attribution from the official Queensland structural framework layer.
    - `Locations.basin`, `Locations.proterozoic_province`, `Locations.orogen` now populated where coverage intersects framework polygons.
  - Finds UI now supports both `New Find` and `Edit Find` flows:
    - New find requires an existing Collection Event.
    - New/Edit dialogs are trip-scoped for Collection Event choices based on currently selected trip.
    - Double-click on a find opens edit dialog.
    - Find dialog edit semantics now align with Trip dialog semantics:
      - `Edit` defaults off.
      - turning `Edit` off performs save-if-changed.
      - closing performs save-if-changed.
      - system fields remain read-only.
  - Generated initial trip candidates from grouped collection-event CSV and inserted ~50 historical trips with date-derived naming conventions.
  - Reassigned a subset of finds to generated trips using strict location + year-window matching (`trip start_year` in `[estimated_year-6, estimated_year-1]`).
  - Collection events carry `trip_id` and `event_year`; trip->collection-events and trip->finds listing/count are wired via `CollectionEvents.trip_id`.
  - Applied location+date-proximity event ownership reassignment (`same location`, `event_year within ±5 years of trip year`): 33 event-owner changes; orphan trips reduced from 36 to 16.
  - Added auto-hiding list scrollbars for all tab list panels; scrollbars appear only when rows/columns overflow.
  - Collection Plan tab now supports:
    - Trip filter default-on behavior.
    - One row per Collection Event (grouped by Trip).
    - Team column in list view (currently sourced from `Trips.team`).
    - Event-bound boundary editing flow with explicit active-event tracking.
  - Collection Events tab now supports `Duplicate Event`:
    - visible only when Trip filter is on
    - enabled only when a Collection Event row is selected
    - duplicate excludes vertices (`boundary_geojson` reset/null)
    - Save remains disabled until name is changed.
  - **Fallbacks and Workarounds to be aware of**:
    - Collection Plan boundary persistence is capability-checked (`getattr(self.repo, "update_collection_event_boundary", None)`); if unavailable, boundary save is skipped without crashing.
    - Collection Events duplication is capability-checked (`getattr(self.repo, "duplicate_collection_event", None)`); if unavailable, the UI raises a controlled error.
    - Collection Plan map UI degrades gracefully when map dependencies/coordinates are unavailable (`tkintermapview` missing or no resolved location coordinates).
    - Collection Plan dialog close uses a safe fallback path (`locals().get("_close_dialog_safe", dialog.destroy)`) to avoid stale-canvas teardown crashes.
    - Trip-filter views fall back to broader datasets when no active provider trip id is available.
    - Type-gate enforcement is intentionally incremental: `check_types.sh` is green for enforced files, while broader full-repo mypy still surfaces issues in non-gated modules.
    - Team-assignment identity quality remains source-constrained; stronger canonical alias/provenance quality is unlikely without additional publicly available sources.
  - Type-gate widening and tightening pass (2026-03-30):
    - `scripts/checks/check_types.sh` scope increased from 51 to 61 files to include additional split UI modules (`planning_phase_window_selection`, `planning_phase_window_palette`, `trip_filter_tree_tab`, `trip_form_dialog`, `trip_form_dialog_pickers`, `collection_events_tab`, `finds_tab`, `location_tab`, `geology_tab`, `team_members_tab`).
    - targeted mypy overrides were reduced by removing per-module suppressions for `ui.collection_events_tab` and `ui.finds_tab` after code-level typing fixes.
  - **Prompt Compliance Snapshot (2026-04-05, updated)**:
  - Architecture boundaries (UI/domain/infra separation): **mostly compliant**.
  - Root clutter minimization (`main.py` only at root): **partially compliant** (major infra/env files moved; IDE artifacts still present).
  - `main.py` thin/no wiring rule: **compliant** (`main.py` now delegates to `app/bootstrap_runtime.py`).
  - DB safety (parameterized SQL + safe connection handling): **compliant**.
  - Type gate (`bash scripts/checks/check_types.sh`): **compliant** as of 2026-04-05 after remediation (`Success: no issues found in 61 source files`).
  - File size <= 300 lines: **not compliant** (current notable oversize files include `ui/planning_tabs_controller.py` (881), `repository/repository_finds.py` (865), `ui/location_form_dialog.py` (832), `repository/postgres_trip_repository_domain.py` (750), `ui/find_form_dialog.py` (687), plus several others).

## Codebase Goodness Assessment (vs prompt)

- **Overall rating**: **Strong (about 9.1/10)** for runtime behavior, DB safety, and refactor progress.
  - Non-target legacy modules/tests over 300 lines are explicitly excluded from this score.
  - **Strong areas**:
  - Postgres-first runtime with SQLite compatibility/mirroring is in place and operational.
  - Core DB work is pragmatic and robust (parameterized SQL, explicit transaction/close handling, schema/migration separation).
  - High-change UI behavior is now isolated via dedicated controllers/coordinator and covered by regression tests.
  - Recent targeted test runs are stable and now include a broader New/Edit Find full-window journey.
  - Internal repository/controller interfaces now use typed payload structures, reducing `dict[str, Any]` usage.
  - Deployment/env layout is cleaner (`deploy/` + `config/env/`) and bootstrap scripts were updated accordingly.
  - Mypy coverage remains broad and useful; enforced gate is currently green for 61 files.
- **Weak areas / debt**:
  - Full-repo mypy run remains intentionally broader than enforced gate and still reports issues outside strict enforcement scope.
  - Mypy remains policy-scoped by command selection (tests are still out of scope).
  - Team-member publication-name matching is currently heuristic/string-based; further meaningful identity-quality improvement is unlikely without additional publicly available source data.

## Recommendations

1. Keep event-owned integrity checks mandatory.
2. Continue incremental type tightening and widen mypy scope for newly split modules with targeted overrides reduced over time.
3. Maintain canonical author-alias + provenance fields, but treat identity-quality lift as data-source constrained unless new public sources become available.

## ToDo

1. Add a reusable `--dry-run/--apply` script for event-ownership normalization with CSV diff output.
2. Add an explicit team-assignment rebuild script (`--dry-run/--apply`) that can regenerate `Trips.team` deterministically from publication + date-window rules.
3. Implement Search + partial/fuzzy matching for location resolution (for example when trip location text and `Locations.name` are close but not exact).
4. Type-coverage next slice: consider bringing selected test modules into a separate `mypy` target once cost/benefit is clear.

## ToDo: Immediate Type-Gate Remediation (2026-04-05)

Status: **completed** on 2026-04-05.

1. `ui/find_taxonomy_dialog.py`
   - Resolve mixed `Text`/`Entry` assignment typing.
   - Tighten widget type for `transient(parent)` argument.
   - Ensure `.get()` calls are only on correctly typed widgets.
2. `ui/find_field_observations_dialog.py`
   - Resolve mixed `Text`/`Entry` assignment typing.
   - Tighten widget type for `transient(parent)` argument.
   - Ensure `.get()` calls are only on correctly typed widgets.
3. `ui/maintenance_dialog.py`
   - Correct `subprocess.run()` typing consistency (`bytes` vs `str` mode).
   - Remove invalid `.decode()` calls when `text=True` result is used.
4. `ui/finds_tab.py`
  - Fix `FindFormDialog` call signatures (duplicate keyword and missing/shifted args).
  - Reconcile `team_member_choices_by_event` and `on_save` argument ordering/types.

## ToDo: Team Institution Backfill

1. Schema field changes for `Team_members`:
   - rename `institution` -> `institution_name`
   - add `institution_source`
   - add `institution_confidence`
   - add `institution_verified_date`
   - add `notes`
2. Backfill source order (strict priority):
   - Official institutional profile page
   - ORCID record
   - Google Scholar profile
   - Recent paper affiliations / Crossref metadata
   - Manual review when still ambiguous
3. Backfill workflow per team member:
   - Start from `team_member_name`
   - Check official lab/university/museum page first
   - Use ORCID to confirm current employment/affiliation
   - Use Google Scholar only as supporting evidence
   - Use most recent paper affiliation only when stronger sources are unavailable
   - Persist `institution_name`, `institution_source`, `institution_confidence`, `institution_verified_date`, `notes`
4. Confidence rubric:
   - `high`: official institution page or ORCID employment/affiliation
   - `medium`: public Google Scholar profile or recent consistent paper affiliations
   - `low`: inferred from publication history only
5. Implementation notes:
   - Add migration script for rename/add columns and backward-compatible reads during rollout.
   - Add deterministic backfill script with `--dry-run` and `--apply`.
   - Record provenance URL/text in `institution_source` and audit notes in `notes`.

## Test run report

- **2026-04-05 (current audit run)**:
  - `python3 scripts/checks/check_import_boundaries.py`: **PASSED**.
  - `python3 scripts/checks/check_trip_event_integrity.py`: **PASSED**.
  - `pytest -q tests/test_collection_plan_tab_behavior.py tests/test_tab_filter_regression.py`: **PASSED** (`13 passed`).
  - `bash scripts/checks/check_types.sh`: **FAILED** (`17` mypy errors in 4 files).
  - `bash scripts/checks/check_file_sizes.sh .`: **FAILED** (multiple files >300 lines; includes `ui/planning_tabs_controller.py` (881), `repository/repository_finds.py` (865), `ui/location_form_dialog.py` (832), `repository/postgres_trip_repository_domain.py` (750), `ui/find_form_dialog.py` (687), `ui/maintenance_dialog.py` (518), `ui/finds_tab.py` (469), and others).

- **2026-04-05 (type remediation run)**:
  - `bash scripts/checks/check_types.sh`: **PASSED** (`Success: no issues found in 61 source files`).
  - Remediated files:
    - `ui/find_taxonomy_dialog.py`
    - `ui/find_field_observations_dialog.py`
    - `ui/maintenance_dialog.py`
    - `ui/finds_tab.py`

- **2026-03-26 (latest full local gate run)**:
  - `bash scripts/checks/ci_checks.sh`: **FAILED at file-size gate**.
    - Checks before file-size gate: import boundaries, canonical DB path, trip/event integrity, mypy, and unittest suite all **PASSED**.
  - `python3 -m unittest -v` (via `ci_checks.sh`): **PASSED** (`75 passed`).
  - `bash scripts/checks/check_file_sizes.sh .`: **FAILED** with current oversized files:
    - `repository/repository_finds.py` (379)
    - `repository/repository_geology_data.py` (320)
    - `tests/test_collection_plan_tab_behavior.py` (330)
    - `tests/test_trip_repository_location_finds.py` (411)
- **2026-03-26 (targeted verification)**:
  - `pytest -q tests/test_db_bootstrap.py tests/test_trip_event_integrity_check.py tests/test_ui_user_flow_integration.py`: **PASSED** (`9 passed`).
  - `bash scripts/checks/check_types.sh`: **PASSED** (`Success: no issues found in 51 source files`).
  - `python3 -m mypy --config-file config/mypy.ini --explicit-package-bases app backend/app repository ui scripts/db scripts/checks scripts/accounts scripts/data_ops scripts/dev_seed`: **PASSED** (`Success: no issues found in 74 source files`).
- **2026-03-30 (targeted UI regression check, after test alignment)**:
  - `pytest -q tests/test_collection_plan_tab_behavior.py tests/test_tab_filter_regression.py`: **PASSED** (`11 passed`).
- **2026-03-30 (type-gate tightening pass)**:
  - `bash scripts/checks/check_types.sh`: **PASSED** (`Success: no issues found in 61 source files`).
  - Expanded scope and override reduction were applied incrementally in this pass (see architecture/behavior notes above).
