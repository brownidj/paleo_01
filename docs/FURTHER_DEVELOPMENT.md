# FURTHER_DEVELOPMENT

## Strategy For Continuing Development

Best next step is an API-first, server-authoritative architecture so both desktop and mobile apps use one controlled backend.

### Target architecture
1. Use a single server-side source of truth (database + backend service).
2. Prevent direct desktop/mobile database access; route all reads/writes through API.
3. Enforce role-based permissions server-side (`planner`, `reviewer`, `field_member`, `admin`).
4. Migrate to PostgreSQL (+ PostGIS if feasible) for concurrency and geospatial support.
5. Make Flutter mobile app offline-capable with queued writes and sync.

### Data/API approach
1. Stabilize domain boundaries: `Trips`, `Locations`, `CollectionEvents`, `Finds`, `TeamMembers`, `Geology`.
2. Define OpenAPI contracts first; generate typed clients for desktop/mobile.
3. Provide mobile-safe endpoints:
   - list visible/assigned trips, locations, collection events
   - create/update finds (GPS + timestamp + device metadata)
   - optional media upload for field evidence
4. Keep derived/system fields server-controlled (for example `location_id` from `collection_event_id`).
5. Add audit metadata (`created_by`, `updated_by`, `created_at`, `updated_at`, `device_id`, sync version).

### Execution sequence
1. Build backend API from current repository/domain behavior.
2. Add desktop API adapter (feature flag for DB mode vs API mode during transition).
3. Add authentication + RBAC before broad client rollout.
4. Build Flutter field MVP with offline queue and sync.
5. Add integration and sync-conflict tests.
6. Set up staging/prod, migrations, backups, monitoring.

### Design rules to lock now
1. Server is policy authority; client restrictions are UX only.
2. Use client-generated UUIDs for offline-created finds.
3. Use idempotent writes (`Idempotency-Key`) for retry-safe sync.
4. Version API from day one (`/v1`).

## Concrete Backlog (Next 2 Sprints)

## Sprint 1 (Foundation: API + Auth + Desktop Transition Start)

### Epic A: Backend service and contracts
- Issue A1: Create backend service scaffold with `/v1` routing and health endpoints.
  - Acceptance: service runs in dev/staging, `/health` returns DB + migration status.
- Issue A2: Publish OpenAPI spec for core read/write resources.
  - Acceptance: OpenAPI includes `Trips`, `CollectionEvents`, `Finds`, auth endpoints, error model.
- Issue A3: Implement core endpoints:
  - `GET /v1/trips`
  - `GET /v1/trips/{id}`
  - `GET /v1/collection-events?trip_id=...`
  - `GET /v1/finds?trip_id=...`
  - `POST /v1/finds`
  - `PATCH /v1/finds/{id}`
  - Acceptance: endpoint tests pass; constraints enforced server-side.

### Epic B: Identity, auth, permissions
- Issue B1: Implement JWT-based auth with refresh token flow.
  - Acceptance: login/refresh/logout endpoints and token expiry checks.
- Issue B2: Add RBAC policy middleware.
  - Acceptance: `field_member` denied trip creation; planner/admin allowed per policy.
- Issue B3: Add per-endpoint authorization tests.
  - Acceptance: unauthorized/forbidden matrix covered in automated tests.

### Epic C: Data model hardening + migrations
- Issue C1: Introduce server migration framework and schema versioning.
  - Acceptance: reproducible migrate up/down on staging clone.
- Issue C2: Add audit columns and backfill defaults.
  - Acceptance: all write paths populate audit fields.
- Issue C3: Add integrity checks (find-event-trip consistency) in CI and server startup check.
  - Acceptance: CI fails on integrity violations.

### Epic D: Desktop adapter (phase 1)
- Issue D1: Create API repository adapter in desktop app for read-only trip/event/find flows.
  - Acceptance: desktop can load core tabs via API feature flag.
- Issue D2: Keep parity mode with fallback DB adapter for transition.
  - Acceptance: switch via config; both modes tested.

## Sprint 2 (Mobile MVP + Sync + End-to-End Confidence)

### Epic E: Flutter field app MVP
- Issue E1: Flutter app scaffold with authenticated session.
  - Acceptance: login persists secure session and role claims.
- Issue E2: Read flows for assigned trips/events/finds.
  - Acceptance: list/detail screens for trip-scoped collection events and finds.
- Issue E3: New/Edit Find form with GPS capture.
  - Acceptance: captures coordinates/time/device id; validates required fields.

### Epic F: Offline-first sync
- Issue F1: Local persistence for pending writes (SQLite/Drift).
  - Acceptance: queued create/update survives app restarts.
- Issue F2: Sync engine with retry, backoff, and idempotency key.
  - Acceptance: duplicate retries do not duplicate records server-side.
- Issue F3: Conflict handling policy (`last-write-wins` or explicit conflict state).
  - Acceptance: conflict scenarios tested and user-visible outcome defined.

### Epic G: Media and field evidence (optional MVP+)
- Issue G1: Add photo attachment upload flow for finds.
  - Acceptance: upload endpoint + mobile capture + record linkage.
- Issue G2: Add lightweight metadata extraction (timestamp/GPS from image where available).
  - Acceptance: metadata persisted and shown in find detail.

### Epic H: End-to-end quality gate and release readiness
- Issue H1: Add end-to-end integration tests across desktop/API/mobile contract fixtures.
  - Acceptance: CI job runs API contract + sync + permission tests.
- Issue H2: Observability baseline.
  - Acceptance: structured logs, error reporting, request tracing in staging.
- Issue H3: Deployment and rollback playbook.
  - Acceptance: documented cutover plan, backup/restore, and rollback steps.

## Definition Of Done For This 2-Sprint Plan
1. Desktop can run core read/write Find workflows against server API in staging.
2. Mobile MVP can create/edit finds in field mode (online/offline with eventual sync).
3. Role restrictions are enforced server-side (not just in client UI).
4. Data integrity checks and migration pipeline are running in CI/staging.
