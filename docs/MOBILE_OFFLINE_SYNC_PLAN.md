# MOBILE_OFFLINE_SYNC_PLAN

## Goal
Support reliable field use of the Flutter app when there is no network, while preserving the current server-authoritative API model.

Primary objective:
- Users can view planned trips and create finds offline.
- Data syncs safely to backend when connectivity returns.
- The app never connects directly to Postgres.

## Current baseline
Mobile currently depends on live API for:
- `POST /v1/auth/login`
- `POST /v1/auth/refresh`
- `GET /v1/auth/me`
- `GET /v1/trips`
- `GET /v1/trips/{id}`
- `POST /v1/finds`

This means field workflows fail without network.

## Target architecture
Adopt **offline-first with local persistence + sync queue**.

Design principles:
- Local DB is source of truth for UI reads.
- User writes are first committed locally.
- Sync engine pushes/pulls in background when online.
- Server remains source of global consistency.

## Mobile data layer design

### Local database (Flutter)
Use `sqflite` (or Drift on top of SQLite) with these tables:

1. `trips`
- `id INTEGER PRIMARY KEY` (server id)
- `trip_name TEXT NOT NULL`
- `start_date TEXT`
- `end_date TEXT`
- `location TEXT`
- `notes TEXT`
- `team TEXT`
- `updated_at_server TEXT NOT NULL`

2. `trip_details_cache`
- `trip_id INTEGER PRIMARY KEY`
- `payload_json TEXT NOT NULL` (full detail payload from `/v1/trips/{id}`)
- `updated_at_server TEXT NOT NULL`

3. `finds_local`
- `local_id TEXT PRIMARY KEY` (UUID v4)
- `server_id INTEGER` (nullable until synced)
- `collection_event_id INTEGER NOT NULL`
- `source TEXT NOT NULL`
- `accepted_name TEXT NOT NULL`
- `created_at_device TEXT NOT NULL`
- `updated_at_device TEXT NOT NULL`
- `deleted_at_device TEXT` (nullable for soft delete support)
- `sync_status TEXT NOT NULL` (`pending`, `syncing`, `synced`, `failed`, `conflict`)
- `last_error TEXT`

4. `sync_queue`
- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `entity_type TEXT NOT NULL` (`find`)
- `entity_local_id TEXT NOT NULL`
- `operation TEXT NOT NULL` (`create`, later `update`/`delete`)
- `idempotency_key TEXT NOT NULL UNIQUE`
- `payload_json TEXT NOT NULL`
- `attempt_count INTEGER NOT NULL DEFAULT 0`
- `next_attempt_at TEXT NOT NULL`
- `created_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`

5. `sync_state`
- `key TEXT PRIMARY KEY`
- `value TEXT NOT NULL`

Keys in `sync_state`:
- `last_trips_sync_at`
- `last_trip_detail_sync_at:<trip_id>`
- `last_successful_sync_at`

### Repository shape
Introduce an app repository interface used by UI:
- `loadTrips()`
- `loadTripDetail(tripId)`
- `createFind(...)`
- `observeSyncStatus()`

Implementation behavior:
- Reads return local cache immediately.
- Refresh methods fetch remote and upsert local.
- Write methods create local record + enqueue sync job.

## Sync protocol

### Push (mobile -> API)
For each queued item:
1. Mark queue item + entity as `syncing`.
2. Call API with idempotency key header:
   - `POST /v1/finds`
   - Header: `Idempotency-Key: <uuid>`
3. On success:
   - store `server_id` (if returned)
   - mark `finds_local.sync_status = synced`
   - remove queue item.
4. On transient failure:
   - increment `attempt_count`
   - exponential backoff (`2^n`, capped, e.g. max 15 min)
   - mark `failed` but retryable.
5. On conflict/validation failure:
   - mark `conflict` with `last_error`.

### Pull (API -> mobile)
Initial scope:
- Trips list and trip details for selected/downloaded trips.

Mechanics:
- Use incremental endpoints with `updated_since` cursor (see API additions).
- Upsert to local tables inside a transaction.
- Preserve unsynced local finds.

### Sync triggers
- App launch.
- Manual pull-to-refresh.
- Connectivity restored.
- Periodic foreground interval (e.g. every 2-5 min while app active).

## API additions required

### 1. Idempotent create for finds
Enhance `POST /v1/finds`:
- Accept `Idempotency-Key` header.
- Return stable response for duplicate key.

Recommended response body:
- `id` (server id)
- `client_request_id` (optional echo)
- `created_at` / `updated_at`

### 2. Incremental sync endpoints
Add:
- `GET /v1/mobile/sync/trips?updated_since=<iso8601>`
- `GET /v1/mobile/sync/trips/{id}?updated_since=<iso8601>` (or reuse detail endpoint with sync metadata)
- `GET /v1/mobile/sync/finds?trip_id=<id>&updated_since=<iso8601>` (if find editing/view needs caching)

Each response should include:
- `items: [...]`
- `next_cursor` (timestamp or opaque token)

### 3. Optional prefetch package endpoint
For field prep:
- `POST /v1/mobile/sync/package`
- Request: trip ids
- Response: bundled trips/details/team/events needed for offline.

## Conflict and validation policy

Initial policy (phase 1):
- Finds are create-only from mobile.
- Server validation errors become `conflict` and require user action.
- No automatic merge needed yet.

Phase 2 (if find edits/deletes added):
- Use per-record `version` or `updated_at` precondition.
- If mismatch, return `409 Conflict` with server snapshot.
- App shows “Resolve conflict” UI.

## Authentication and security
- Continue using secure token storage (`flutter_secure_storage` behavior via existing `TokenStore` abstraction).
- Keep access token short-lived, refresh token longer-lived.
- Queue sync pauses on auth failure; resume after re-login.
- Encrypt sensitive local DB if policy requires it (evaluate `sqlcipher` wrapper).

## UX requirements
- Global sync indicator: `Offline`, `Syncing`, `Synced`, `Action required`.
- Unsynced item badge/count in relevant screens.
- Offline actions should never block on network.
- Clear retry option for failed/conflict items.

## Rollout plan

### Phase 1: Core offline create
Scope:
- Offline cache for trips/trip details.
- Offline create-find queue with retry + idempotency.
- Sync status UI basics.

Exit criteria:
- User can create finds with airplane mode on.
- Finds sync automatically when back online.
- No duplicate finds from retries.

### Phase 2: Field hardening
Scope:
- Prefetch package flow.
- Better failure diagnostics and retry controls.
- Background sync tuning and telemetry.

Exit criteria:
- Multi-day offline use remains stable.
- Sync recovery works after app restarts and token refreshes.

### Phase 3: Extended sync
Scope:
- Optional offline edits/deletes for finds.
- Conflict resolution UI.

Exit criteria:
- Conflicts are detectable, visible, and resolvable in app.

## Testing plan
- Unit tests:
  - queue enqueue/dequeue logic
  - backoff calculation
  - idempotency behavior in client
- Integration tests:
  - create finds offline -> reconnect -> synced
  - token expiry during sync -> refresh/relogin recovery
  - duplicated network retries produce one server record
- Field simulation:
  - airplane mode for extended period
  - app kill/restart with pending queue
  - intermittent connectivity flapping

## Implementation checklist (next step)
1. Add local DB layer and schemas in mobile app.
2. Refactor API client usage behind repository abstraction.
3. Implement write queue + retry worker.
4. Add minimal sync status UI.
5. Add backend idempotency support for `POST /v1/finds`.
6. Add incremental trips sync endpoint(s).
7. Add automated tests for offline -> online replay.

