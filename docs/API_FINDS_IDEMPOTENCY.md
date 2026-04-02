# API_FINDS_IDEMPOTENCY

## Endpoint
`POST /v1/finds`

## Purpose
Support safe client retries (especially mobile offline sync replay) without creating duplicate server-side operations for the same user request.

## Request
Headers:
- `Authorization: Bearer <access_token>` (required)
- `Idempotency-Key: <client_generated_unique_key>` (optional but strongly recommended for retryable clients)

Body:
```json
{
  "collection_event_id": 123,
  "team_member_id": 10,
  "source": "Field",
  "accepted_name": "Taxon A"
}
```

`team_member_id` behavior:
- Optional in request.
- If omitted, server defaults to the authenticated user's `team_member_id`.
- If provided, it must be assigned to the trip that owns the target collection event.

## Idempotency behavior
- Idempotency scope is per `(username, idempotency_key)`.
- If a request arrives with a key that has already been processed for that user:
  - the server returns the same stored response payload as the original request.
- If the key is new:
  - server processes the request and stores the response for future duplicate-key retries.
- If no key is provided:
  - server processes the request normally with no idempotency replay guarantee.

## Current response model
```json
{
  "status": "accepted",
  "message": "Find create scaffold accepted for user '<username>'."
}
```

Status codes:
- `200 OK` for accepted create and idempotent replay.
- Existing auth/validation failures remain unchanged (`401`, `403`, `422`, etc.).

## Client guidance
- Generate a new idempotency key per logical create operation.
- Reuse the same key for all retries of that same operation.
- Do not reuse a key for different create intents.

## Implementation notes
- Storage table: `api_idempotency_keys`
- Uniqueness constraint: `(username, idempotency_key)`
- Indexed by `created_at` for maintenance and retention jobs.
