# MOBILE_OFFLINE_IMPLEMENTATION_BACKLOG

## Location
This backlog is recorded in-repo at:
- `docs/MOBILE_OFFLINE_IMPLEMENTATION_BACKLOG.md`

Related plan:
- `docs/MOBILE_OFFLINE_SYNC_PLAN.md`

## Assumptions
- Mobile remains API-based (no direct DB access).
- Current mobile scope is login, trips list/detail, create find.
- First release target is offline create-find reliability.

## Estimation scale
- `S` = 0.5-1 day
- `M` = 2-3 days
- `L` = 4-6 days

## Milestone 1: Offline Core (MVP)
Target outcome:
- User can load prepared trip data and create finds fully offline.
- Pending finds sync automatically when network returns.

### Epic A: Local persistence foundation
1. Add local DB package + migration scaffolding (`sqflite`/Drift).
- Size: `M`
- Depends on: none
- Acceptance:
  - App starts with local DB initialized.
  - Schema versioning and migration runner exist.

2. Create local tables: `trips`, `trip_details_cache`, `finds_local`, `sync_queue`, `sync_state`.
- Size: `M`
- Depends on: A1
- Acceptance:
  - Tables created idempotently.
  - Basic CRUD covered by unit tests.

3. Add repository abstraction (`MobileDataRepository`) and route UI reads through it.
- Size: `L`
- Depends on: A2
- Acceptance:
  - Trips/detail screens read from repository (not raw API calls).
  - Existing online behavior preserved.

### Epic B: Write queue + sync engine
4. Implement local-first `createFind` path (save local + enqueue).
- Size: `M`
- Depends on: A2, A3
- Acceptance:
  - Works in airplane mode with visible local result.
  - Queue row created with `pending` status.

5. Build sync worker (manual trigger + app launch + connectivity restore).
- Size: `L`
- Depends on: B4
- Acceptance:
  - Queue transitions through `pending -> syncing -> synced/failed`.
  - Retries with exponential backoff.

6. Add idempotency key generation and send on `POST /v1/finds`.
- Size: `S`
- Depends on: B5
- Acceptance:
  - Every queued create uses a stable idempotency key.
  - Retries reuse same key.

### Epic C: API support for sync safety
7. Backend support for `Idempotency-Key` on `POST /v1/finds`.
- Size: `L`
- Depends on: none
- Acceptance:
  - Duplicate requests with same key do not create duplicate finds.
  - Response returns stable created record id.

8. Add/update API contract docs for idempotent find create.
- Size: `S`
- Depends on: C7
- Acceptance:
  - Endpoint behavior and error codes documented.

### Epic D: Sync UX and observability
9. Add global sync state indicator in app shell.
- Size: `M`
- Depends on: B5
- Acceptance:
  - User sees `Offline/Syncing/Synced/Needs attention`.

10. Add pending/failed count and retry action.
- Size: `M`
- Depends on: D9
- Acceptance:
  - Failed items can be retried manually.
  - Error message visible per failed item.

### Milestone 1 exit criteria
- Airplane mode test: create finds succeeds without network.
- Reconnect test: pending finds sync automatically.
- Retry test: repeated retries do not duplicate records server-side.

## Milestone 2: Field hardening
Target outcome:
- Better offline prep and resilience for multi-day field use.

### Epic E: Incremental pull sync
11. Add backend `updated_since` trips sync endpoint(s).
- Size: `L`
- Depends on: none
- Acceptance:
  - API returns incremental trip/trip-detail changes with cursor.

12. Implement pull sync in mobile repository with cursor in `sync_state`.
- Size: `L`
- Depends on: E11, A3
- Acceptance:
  - Pull updates local cache transactionally.
  - Cursor persists across restarts.

### Epic F: Prefetch and readiness
13. Add “prepare trip for offline” flow (prefetch details, team, events).
- Size: `M`
- Depends on: E12
- Acceptance:
  - Selected trips are usable offline immediately.

14. Add stale-data warnings and last-sync timestamp.
- Size: `S`
- Depends on: E12
- Acceptance:
  - User can see cache age and stale status.

### Epic G: Reliability improvements
15. Persist and resume in-progress sync safely after app restart.
- Size: `M`
- Depends on: B5
- Acceptance:
  - No queue loss or duplication after force close.

16. Add telemetry/logging for sync outcomes (success/failure/conflict counts).
- Size: `S`
- Depends on: B5
- Acceptance:
  - Basic metrics available in logs for diagnostics.

### Milestone 2 exit criteria
- Offline prep works for selected trips.
- Queue survives app restarts and poor connectivity.
- Operators can diagnose sync issues from logs/UI.

## Milestone 3: Conflict-capable sync (optional extension)
Target outcome:
- Support offline edits/deletes with conflict detection.

### Epic H: Model extension
17. Extend `finds_local` for edit/delete operations and server version fields.
- Size: `M`
- Depends on: Milestone 1 complete
- Acceptance:
  - Queue supports `update` and `delete`.

18. Add backend conditional update/delete with `version` or `updated_at` preconditions.
- Size: `L`
- Depends on: H17
- Acceptance:
  - Conflicting update returns `409` with server snapshot.

### Epic I: Conflict resolution UX
19. Add conflict list and resolution UI.
- Size: `L`
- Depends on: H18
- Acceptance:
  - User can compare local vs server and choose resolution path.

### Milestone 3 exit criteria
- Conflicts are detected deterministically.
- User can resolve and complete sync without data loss.

## Suggested delivery order (first 6 weeks)
Week 1:
- A1, A2

Week 2:
- A3, B4

Week 3:
- B5, B6

Week 4:
- C7, C8

Week 5:
- D9, D10

Week 6:
- E11 kickoff + test hardening for Milestone 1

## Definition of done (cross-cutting)
- Unit tests for repositories/queue logic.
- Integration tests for offline->online replay.
- No duplicate find creation under retries.
- Documentation updated (`README` + sync plan/backlog docs).
- Feature flag or rollout toggle in place for controlled release.

