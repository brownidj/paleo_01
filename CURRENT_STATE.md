

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

- **Architecture**: Planning-phase Trip desktop app only (legacy field-recorder track removed).
  - **Infrastructure/Init**: `scripts/db_bootstrap.py`, `scripts/init_db.py`.
  - **Repository**: `trip_repository.py` (`Trips` CRUD + active `Users` lookups).
  - **UI Entrypoints**: `main.py` and `planning_phase_main.py` both launch planning-phase UI.
  - **UI Modules**:
    - `ui/planning_phase_window.py` (Trips list + orchestration).
    - `ui/trip_form_dialog.py` (Trip form modal, duplicate flow).
    - `ui/team_editor_dialog.py` (active-user multi-select team editor).
  - **Seeding**: `scripts/seed_users.py`, `scripts/seed_trips.py`.
- **Planning Database**: `paleo_trips_01.db` with:
  - `Users(id, name, phone_number, active)` where `active` is boolean-like (`0/1`).
  - `Trips(trip_code, trip_name, start_date, end_date, team, region, notes)`.
- **Entrypoint Rule**: `main.py` is thin and contains no domain/infrastructure wiring.
- **Error Handling**: UI operations catch explicit `sqlite3`/`ValueError` paths and show targeted dialogs.
- **Constraints**: source file size checks currently pass with `scripts/check_file_sizes.sh`.

## Test run report

- **2026-03-20 14:01**: Legacy field-recorder track removal + planning-track validation.
    - Removed legacy files:
      - `app_composition.py`
      - `database_manager.py`, `database_schema.py`
      - `demo_db.py`
      - `ui/main_window.py`, `ui/mission_views.py`, `ui/locality_views.py`, `ui/specimen_views.py`, `ui/photo_viewer.py`, `ui/ui_services.py`
      - `tests/test_database_manager.py`, `tests/test_ui_services.py`
    - Added planning-track tests:
      - `tests/test_trip_repository.py`
    - `./scripts/check_file_sizes.sh .`: PASSED
    - `python3 -m unittest -v`: PASSED
    - Total tests: 3 passed (planning repository tests)
- **2026-03-20 13:53**: Reassessment against CURRENT_STATE prompt.
    - `./scripts/check_file_sizes.sh .`: FAILED
      - `ui/planning_phase_window.py` at 325 lines (over 300-line limit)
    - `python3 -m unittest -v`: PASSED
    - Total tests: 16 passed
    - Notes:
      - Current tests validate legacy DB/service layers.
      - Planning-phase UI/repository flows currently rely on manual testing.
- **2026-03-19 13:39**: Hardening pass verification.
    - `./scripts/check_file_sizes.sh .`: PASSED
    - `python3 -m unittest -v`: PASSED
    - Total tests: 16 passed
    - Added coverage:
      - invalid update-field rejection (`DatabaseManager`)
      - invalid `photo.parent_type` rejection (`DatabaseManager`)
      - sqlite error wrapping to `UIServiceError` (`UIService`)
- **2026-03-19 13:27**: Ran file size checker and unit tests after architecture fixes.
    - `./scripts/check_file_sizes.sh .`: PASSED
    - `python3 -m unittest -v`: PASSED
    - Total tests: 13 passed (`tests/test_database_manager.py` + `tests/test_ui_services.py`)
- **2026-03-19 13:25**: Refactor and bug fix pass.
    - Fixed broken specimen back-navigation call signature in `ui/specimen_views.py`
    - Removed direct `ui_service.db` access from UI views (adapter methods in `UIService`)
    - Moved app wiring to `app_composition.py`; `main.py` now delegates composition
    - Added `scripts/check_file_sizes.sh` for regular file length validation
- **2026-03-19 12:40**: Connected `coelo_01.jpg` and `coelo_02.jpg` to Ghost Ranch localities in `paleo_field.db`.
- **2026-03-19 12:35**: Migrated locality `c5597bb3-d5a8-4d0d-830a-f50422ba1641` from `demo_paleo.db` to `paleo_field.db`.
- **2026-03-19 11:40**: Migrated two existing localities from `demo_paleo.db` to `Coelo_01` mission in `paleo_field.db`.
- **2026-03-19 11:30**: Added UI warning when viewing localities without mission selection.
- **2026-03-19 11:35**: Updated `demo_db.py` to be mission-aware.
- **2026-03-19 10:30**: Ran unit tests in `tests/test_database_manager.py` after adding Missions.
    - Database initialization (inc. mission table): PASSED
    - Mission CRUD: PASSED
    - Locality CRUD (mission-aware): PASSED
    - Specimen CRUD: PASSED
    - Foreign key enforcement: PASSED
    - Photo CRUD: PASSED
    - Soft delete logic: PASSED
    - Migration to "Initial Mission": VERIFIED
