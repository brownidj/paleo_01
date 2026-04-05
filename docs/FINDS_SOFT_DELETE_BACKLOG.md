# FINDS_SOFT_DELETE_BACKLOG

## Location
This backlog is recorded in-repo at:
- `docs/FINDS_SOFT_DELETE_BACKLOG.md`

Related documents:
- `docs/MOBILE_OFFLINE_IMPLEMENTATION_BACKLOG.md`
- `docs/MOBILE_OFFLINE_SYNC_PLAN.md`

## Objective
Introduce consistent soft-delete behavior for finds across backend, desktop, and mobile so that:
- Deletions never hard-remove rows.
- Deleted finds do not show in normal desktop/mobile views.
- Mobile cannot delete finds after they have synced.

## Assumptions
- Backend remains the system of record.
- Mobile stays API-based with local cache/sync queue.
- Existing local/offline queue architecture remains in place.

## Estimation scale
- `S` = 0.5-1 day
- `M` = 2-3 days
- `L` = 4-6 days

## Milestone 1: Server and desktop soft-delete baseline
Target outcome:
- Server supports soft-delete semantics.
- Desktop marks finds deleted (not removed) and hides them by default.

### Epic A: Server data model and API semantics
1. SD-01 Add server soft-delete schema fields.
- Size: `M`
- Depends on: none
- Scope:
  - Add `deleted_at` (`TIMESTAMPTZ NULL`) and `deleted_by` (`INTEGER NULL`) to finds.
  - Add index for active filtering (`deleted_at IS NULL` queries).
- Acceptance:
  - Migration is reversible.
  - Existing records remain active (`deleted_at IS NULL`).
  - Query plans use index on active-list paths.

2. SD-02 Implement soft-delete endpoint behavior.
- Size: `M`
- Depends on: SD-01
- Scope:
  - `DELETE /v1/finds/{id}` (or equivalent `PATCH`) sets `deleted_at`/`deleted_by`.
  - No hard delete in application code paths.
- Acceptance:
  - Endpoint is idempotent.
  - Repeated delete calls do not error.
  - Response includes deleted state metadata.

3. SD-03 Add API default filtering and include-deleted override.
- Size: `M`
- Depends on: SD-02
- Scope:
  - Find list/read endpoints exclude deleted finds by default.
  - Optional `include_deleted=true` (or equivalent) for admin/desktop audit views.
- Acceptance:
  - Default API payloads omit deleted finds.
  - Override returns deleted finds as expected.
  - API contract docs updated.

### Epic B: Desktop integration
4. SD-04 Replace hard delete with mark-deleted flow in desktop app.
- Size: `M`
- Depends on: SD-02, SD-03
- Scope:
  - UI action becomes "Mark deleted".
  - Repository calls soft-delete API semantics.
- Acceptance:
  - Deleted find remains in DB.
  - Active desktop views no longer show it.
  - User sees confirmation feedback.

5. SD-05 Add optional desktop "Show deleted" mode.
- Size: `S`
- Depends on: SD-04
- Scope:
  - Toggle/filter for deleted records.
  - Deleted rows visually differentiated.
- Acceptance:
  - Toggle defaults OFF.
  - Deleted finds appear only when enabled.
  - Read-only presentation for deleted rows in first release.

## Milestone 2: Mobile reconciliation with server-deleted finds
Target outcome:
- Mobile stops showing finds deleted on desktop/server.
- Mobile enforces delete restrictions after sync.

### Epic C: Mobile local model + pull behavior
6. SD-06 Extend mobile local schema for deletion state.
- Size: `M`
- Depends on: SD-01
- Scope:
  - Add local tombstone tracking fields (`deleted_at_device`, optional `deleted_at_server`).
  - Preserve existing local rows through migration.
- Acceptance:
  - Migration is idempotent.
  - Active local queries exclude tombstoned rows.
  - Existing unsynced queue logic still works.

7. SD-07 Apply server deletion state during mobile refresh/sync.
- Size: `M`
- Depends on: SD-03, SD-06
- Scope:
  - When server returns deleted find metadata, local view must hide it.
  - Keep record for audit/sync bookkeeping where needed.
- Acceptance:
  - Desktop-deleted finds disappear from mobile active UI after sync/refresh.
  - No accidental hard delete required.
  - Regression tests for merge behavior pass.

### Epic D: Mobile delete policy and queue semantics
8. SD-08 Enforce "synced finds cannot be deleted on mobile".
- Size: `S`
- Depends on: SD-06
- Scope:
  - Disable delete action when `sync_status='synced'`.
  - Provide explicit UI message explaining restriction.
- Acceptance:
  - Synced finds are not deletable from mobile UI.
  - Guard also exists at repository/service layer.

9. SD-09 Define unsynced mobile delete behavior.
- Size: `M`
- Depends on: SD-08
- Scope:
  - For unsynced finds, choose one path:
    - Option A: allow local cancel/delete (queue cleanup), or
    - Option B: disallow all mobile deletes initially.
  - Implement selected policy consistently.
- Acceptance:
  - Policy documented.
  - Queue behavior deterministic.
  - No orphaned photos/queue rows after delete/cancel path.

10. SD-10 Conflict and retry policy for delete-related sync.
- Size: `M`
- Depends on: SD-07, SD-09
- Scope:
  - Define precedence for:
    - server-deleted vs local unsynced edit,
    - local tombstone vs server update.
  - Implement deterministic resolution + retry behavior.
- Acceptance:
  - Conflict matrix documented.
  - Automated tests for all conflict branches.
  - User-facing status remains accurate (`Needs attention` on unresolved conflict).

## Milestone 3: Hardening and rollout
Target outcome:
- Safe production rollout with observability and clear operations.

### Epic E: Observability, testing, release controls
11. SD-11 Add delete-state observability and diagnostics.
- Size: `S`
- Depends on: SD-10
- Scope:
  - Counters/logging for active/deleted/pending-delete records.
  - Admin/developer diagnostic queries.
- Acceptance:
  - Troubleshooting path documented.
  - Logs avoid sensitive data leakage.

12. SD-12 End-to-end test pack and staged rollout.
- Size: `M`
- Depends on: SD-11
- Scope:
  - Unit/integration/manual tests for desktop/API/mobile soft-delete flows.
  - Migration dry-run and rollback checks.
- Acceptance:
  - Test checklist completed.
  - Rollout guide includes fallback/rollback steps.
  - No hard-delete regressions in release candidate.

## Suggested delivery order
Week 1:
- SD-01, SD-02

Week 2:
- SD-03, SD-04

Week 3:
- SD-05, SD-06

Week 4:
- SD-07, SD-08

Week 5:
- SD-09, SD-10

Week 6:
- SD-11, SD-12

## Definition of done (cross-cutting)
- No application path hard-deletes finds.
- Deleted finds excluded from normal desktop/mobile views.
- Mobile blocks delete for synced finds.
- Server/desktop/mobile behavior is consistent under retries and reconnects.
- Documentation and runbooks updated.
