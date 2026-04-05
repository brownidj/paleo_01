# BACKEND_SERVER

Set it up as a small, stable Linux-style service host on macOS with Docker, reverse proxy, TLS, and backups.

## Current execution mode
- Build and run the full backend stack on **this current machine first**.
- Treat this machine as `local-staging` for architecture, API, auth/RBAC, and data/sync testing.
- Move to the MacBook host later by migrating config/secrets/backups and redeploying the same Docker stack.

## 1. Base machine setup (this machine first)
- **Apply all of these to this current machine now.**
- Create a dedicated macOS user (for server processes only).
- Give this machine a static DHCP reservation on your router.
- Set a local DNS name (for example `paleo-server.local`) or fixed IP for this machine.
- Disable sleep while plugged in; keep lid open or use clamshell + power/external display.
- Enable auto-restart after power failure.
- **MacBook note**: do not do this on the MacBook yet; repeat this same section there only during migration/cutover.

### ASUS router: step-by-step (this machine first)

#### A) Create static DHCP reservation
1. Open router admin:
   - `http://router.asus.com` (or `192.168.50.1` on your network)
2. Go to:
   - `LAN` -> `DHCP Server`
3. Turn on:
   - `Enable Manual Assignment` = `Yes`
4. Add this Mac entry:
   - `Client Name (MAC Address)`: use the MAC this Mac is actually using on that SSID
     - if Private Wi-Fi Address is enabled, use that private MAC
   - `IP Address`: fixed IP, for example `192.168.50.30`
   - `DNS Server`: blank
   - click `+`
5. Click `Apply`.
6. Renew lease on this Mac:
   - `sudo ipconfig set en1 DHCP`
   - `ipconfig getifaddr en1`
   - expected: `192.168.50.30`

#### B) Set local DNS name (optional but recommended)
1. In ASUS UI, go to:
   - `LAN` -> `DHCP Server`
2. In `RT-AC59U V2's Domain Name`, enter a local suffix, for example:
   - `lan`
3. Click `Apply`.
4. Ensure static DHCP entry has hostname set (for example `paleo-server`).
5. Access server as:
   - `paleo-server.lan`
   - or continue with fixed IP only.

#### C) If reservation does not apply
1. Check Wi-Fi address in macOS network details.
   - if `Private Wi-Fi Address` is enabled, reservation must match that private MAC.
2. Reconnect Wi-Fi:
   - `networksetup -setairportpower en1 off`
   - `networksetup -setairportpower en1 on`
3. Re-check IP:
   - `ipconfig getifaddr en1`

#### D) Router login blocked ("logout another user first")
1. Try private/incognito browser window.
2. Wait 3-5 minutes for session timeout.
3. If still blocked, power-cycle router (10 seconds off/on), then log in first.

#### E) Quick verification checklist
- Manual assignment enabled: `Yes`
- MAC in reservation matches MAC currently used by this machine
- Reserved IP is not already in use
- This machine receives reserved IP after reconnect
- Router/admin reachable and hostname resolves (if local DNS configured)

## 2. Install runtime stack
- Install Docker Desktop (or Colima + Docker CLI).
- Install `git`, `make`, `uv`/`python`, and `sqlite3`/`psql` client tools.
- Use Docker Compose for:
  - API service
  - PostgreSQL (+ PostGIS optional)
  - Reverse proxy (Caddy recommended)

### Local runtime quick start (implemented in this repo)
- Stack files:
  - `deploy/docker/docker-compose.yml`
  - `deploy/docker/docker-compose.internet.yml` (internet override profile)
  - `deploy/caddy/Caddyfile`
  - `deploy/caddy/Caddyfile.internet` (public DNS + Let's Encrypt)
  - `config/env/local.env.example`
  - `config/env/prod.env.example`
  - `backend/` (FastAPI app with `/v1/health`)
  - `scripts/backend/bootstrap_local_backend.sh`
  - `scripts/backend/bootstrap_internet_backend.sh`
- First run:
  - `cp config/env/local.env.example config/env/local.env` (if not already present)
  - Update `config/env/local.env` secrets and, if needed, set `SERVER_HOST`
  - `scripts/backend/bootstrap_local_backend.sh`
- Verify:
  - `docker compose --env-file config/env/local.env -f deploy/docker/docker-compose.yml ps`
  - `curl -v http://davids-mac-mini.tail850882.ts.net/v1/health`

## 3. Network and security
- Expose only `443` (and optionally `80` for redirect) on LAN.
- Keep DB port private (not exposed outside Docker network).
- Use long random secrets in env files under `config/env/` (JWT secret, DB password).
- Create separate staging and prod env files even on one machine.
- Restrict inbound access to your LAN subnet via macOS firewall/router rules.
- Secret guardrails in repo:
  - `python3 scripts/checks/check_no_tracked_secrets.py`
  - included in `bash scripts/checks/ci_checks.sh`
  - optional local commit gate via `pre-commit install`

### Section 3 implementation status in this repo
- Compose stack now lives under `deploy/docker/`, and Caddy config under `deploy/caddy/`.
- Env templates now exist for separation:
  - `config/env/local.env.example` (local)
  - `config/env/staging.env.example`
  - `config/env/prod.env.example`
- `scripts/backend/bootstrap_local_backend.sh` supports `ENV_FILE=...` and warns on placeholder secrets.

### Section 3 runbook (this machine)
1. Create local env file:
   - `cp config/env/staging.env.example config/env/staging.env`
   - set strong `POSTGRES_PASSWORD`, `JWT_SECRET`, `JWT_REFRESH_SECRET`
   - set `SERVER_HOST=paleo-server.local`
2. Start stack with explicit env:
   - `ENV_FILE=config/env/staging.env scripts/backend/bootstrap_local_backend.sh`
3. Verify DB is not host-exposed:
   - `docker compose --env-file config/env/staging.env -f deploy/docker/docker-compose.yml ps`
   - confirm no `0.0.0.0:5432` or `127.0.0.1:5432` mapping for `postgres`
4. Verify API via reverse proxy:
   - add host mapping on each client machine:
     - `echo "192.168.50.30 paleo-server.local" | sudo tee -a /etc/hosts`
   - then verify:
     - `curl -k https://paleo-server.local/v1/health`
5. Optional local firewall tightening:
   - macOS `System Settings` -> `Network` -> `Firewall` = On
   - router: permit only your LAN subnet to this host for `443`/`80`

## 4. TLS and identity
- If LAN-only, use:
  - Caddy with internal CA, or
  - self-signed cert distributed to client trust stores.
- If internet-accessed, use proper public DNS + Let’s Encrypt.
- Add API auth from day one (JWT + refresh).

### Internet-accessed runbook (implemented profile)
1. DNS and WAN prerequisites
   - Choose a public hostname (for example `api.yourdomain.com`).
   - Create an `A` record to your router WAN IP (or DDNS hostname via CNAME).
   - On ASUS router, configure port forwarding:
     - WAN `80` -> this machine `80`
     - WAN `443` -> this machine `443`
2. Prepare production env
   - `cp config/env/prod.env.example config/env/prod.env`
   - set:
     - `SERVER_HOST` to your public hostname
     - `ACME_EMAIL` to your ops email
     - strong `POSTGRES_PASSWORD`, `JWT_SECRET`, `JWT_REFRESH_SECRET`
3. Start internet profile
   - `ENV_FILE=config/env/prod.env scripts/backend/bootstrap_internet_backend.sh`
4. Verify from outside LAN (mobile data or external host)
   - `curl https://<your-public-host>/v1/health`
   - expected: `{"status":"ok","database":"up","env":"prod"}`
5. Security notes
   - Keep DB private (no host mapping for Postgres).
   - Never expose Postgres port on router.
   - Keep API auth/RBAC enabled before broader access.

## 5. Data and backups
- Use Postgres volume on local SSD.
- Nightly `pg_dump` backups to:
  - local backup dir, and
  - second destination (external drive or cloud bucket).
- Keep at least 14 daily + 8 weekly backups.
- Test restore monthly.

## 6. Service operations
- Run API with systemd-like behavior via Docker restart policies.
- Add health checks and simple uptime monitoring.
- Centralize logs (at least JSON logs + rotation).
- Add a one-command deploy (`git pull && docker compose up -d --build`).

## 7. Desktop/mobile client config
- Desktop API URL resolution:
  - `PALEO_API_BASE_URL` (if set)
  - otherwise `PALEO_API_PRIMARY_BASE_URL` if reachable (default `http://davids-mac-mini.tail850882.ts.net`)
  - otherwise `PALEO_API_FALLBACK_BASE_URL` (default `https://localhost`)
- Flutter app uses the Tailscale host as default on iOS/macOS with localhost fallback. Use `PALEO_API_BASE_URL` and optional `PALEO_API_FALLBACK_BASE_URL` to override.
- Never allow clients to connect directly to DB.

## 8. First deployment checklist
- Bring up DB + API + proxy.
- Run migrations.
- Create initial admin user.
- Verify:
  - auth
  - role enforcement (mobile cannot create trips)
  - find create/update
  - backup job success

## 9. Secret incident response
1. Rotate exposed credentials immediately:
   - `POSTGRES_PASSWORD`
   - `JWT_SECRET`
   - `JWT_REFRESH_SECRET`
   - `BOOTSTRAP_ADMIN_PASSWORD` (and reset affected user passwords)
2. Update local env/secrets files (`config/env/*.env`, `secrets/postgres_password.txt`) and restart the stack.
3. Ensure leaked local secret files are not tracked:
   - `git ls-files config/env/*.env secrets/*.txt`
4. Run secret policy check:
   - `python3 scripts/checks/check_no_tracked_secrets.py`
5. Install local commit hook once:
   - `python3 -m pip install pre-commit`
   - `pre-commit install`
  - restore dry-run.

If you want, I can generate a concrete compose/env/bootstrap bundle tailored to this repo next.

## Migration later (this machine -> MacBook)
1. Freeze writes briefly (maintenance window).
2. Take final Postgres backup (`pg_dump` + optional volume snapshot).
3. Copy deployment bundle:
   - `deploy/docker/docker-compose.yml`
   - `deploy/caddy/Caddyfile` / reverse-proxy config
   - migration scripts
   - `config/env/*.env` values (regenerate secrets where appropriate)
4. Restore DB on MacBook and run migrations.
5. Smoke test:
   - auth/login
   - role enforcement
   - trip/event/find read flows
   - find create/update
6. Point clients to new API host URL.
7. Keep old host read-only for rollback window, then decommission.
