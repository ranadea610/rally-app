# CI and deployment preparation

Hosting has deliberately not been selected. These files prepare a single Linux Docker host without creating a server, changing DNS, requesting live certificates, pushing source, or publishing the connected app.

## Automated checks

`.github/workflows/ci.yml` runs on pushes, pull requests, and manual dispatch. It uses read-only repository permissions and no deployment credentials.

| Job | Verification |
| --- | --- |
| Frontend build and unit tests | Clean npm install, timezone/configuration tests, TypeScript, Vite build |
| PostgreSQL tests and migrations | Real PostgreSQL 17 tests, model drift check, migration rollback/reapply |
| Browser workflows with PostgreSQL | Chromium workflows against a separate service database, retained failure traces |
| Docker build and smoke test | Built frontend/API, cookie/CSRF/logout checks, backup restore, production proxy rate limiting |

Each database job has its own PostgreSQL service; there are no production secrets. The container job uses a disposable Compose volume. Backend packages are constrained to the verified versions in `backend/constraints.txt`; production installs only runtime requirements, while CI/development installs `backend/requirements-dev.txt`. npm uses the committed lockfile. Base image tags still receive upstream updates; pin image digests for an audited release if strict bit-for-bit reproducibility is needed.

The workflow is only active after these files are committed and pushed to GitHub. A local successful test run does not prove a GitHub-hosted workflow run. Once the first remote run succeeds, configure branch protection to require all four named jobs. There is no automatic production deployment or image-registry push.

## Production shape

Use `compose.production.yaml` **alone**, never merged with the development Compose file. It uses a separate project and persistent volumes. Only Caddy publishes ports 80/443. PostgreSQL, the API, and nginx are private. Caddy terminates HTTPS and routes to nginx; nginx proxies `/api` to FastAPI, preserving the browser origin and secure session cookie behavior.

`deploy/nginx.production.conf` rate limits login and registration per client to 10 requests/minute with a burst of five. It trusts the forwarded client address only because nginx has no public port and sits behind the Caddy edge. Do not expose this nginx service directly or place an unconfigured proxy before Caddy. The API also refuses production startup with non-secure cookies, weak database credentials, or non-HTTPS/wildcard origins.

Caddy's certificate setup requires a real domain resolving to the chosen host, reachable ports 80 and 443, and an operator email. See the [official HTTPS quick-start](https://caddyserver.com/docs/quick-starts/https). Keep the Caddy data volume so certificates persist across releases.

## Configure the future host

The host needs Docker Engine with the Compose plugin, Git, and Node.js 24 for the validation/backup helpers. The secret-generation example also uses Python 3. Select a server and domain before proceeding. These commands are preparation instructions, not commands already executed against a server.

```sh
git clone https://github.com/ranadea610/rally-app.git
cd rally-app
git checkout FULL_TESTED_COMMIT_SHA
cp deploy/.env.production.example deploy/.env.production
chmod 600 deploy/.env.production
```

Fill in the ignored environment file:

- `DOMAIN`: the actual public hostname, without a scheme, port, or path.
- `ACME_EMAIL`: the operator's email for certificate registration.
- `POSTGRES_PASSWORD`: generate a unique random hex secret with `python3 -c "import secrets; print(secrets.token_hex(32))"`.
- `RELEASE_TAG`: the full checked-out Git commit SHA, after its CI checks pass.
- `CLUB_TIMEZONE`: the club's IANA timezone (default `America/Los_Angeles`).

Use an editor or secret-management tooling to set the values; do not commit the filled file or share resolved Compose output, which contains credentials. `npm run check:deploy` validates the settings without printing secret values. Changing `POSTGRES_PASSWORD` after database initialization does **not** rotate the existing database role; plan an explicit database credential rotation.

## First release and updates

```sh
npm run check:deploy
bash scripts/release.sh
```

The release helper requires a clean Git checkout and verifies the configured image tag matches HEAD. It builds the two app images tagged with that commit, starts the private database, pauses the app, creates a backup, runs migrations, and starts all services. This is a short maintenance deployment, not zero downtime. Backups and migrations complete before public traffic resumes. If any step fails, inspect the failure; services may remain paused. Do not force traffic onto a partially migrated database.

After startup, verify `https://YOUR_DOMAIN/api/health/ready`, create an account, bootstrap a trusted officer, and test coach approval, publishing, booking, and cancellation. Promote an already registered officer with:

```sh
docker compose --project-name rally-production --env-file deploy/.env.production -f compose.production.yaml exec api python -m app.cli make-admin USER_ID
```

Keep the previous commit's app images. To roll back application code, check out that tested commit, set `RELEASE_TAG` to its SHA, and use the release helper only if its code is compatible with the current database schema. Do not blindly run Alembic downgrade on live data. For an incompatible migration, keep the app stopped and restore a verified backup into a **new** database/volume, then switch configuration deliberately. This repository's migrations can remove data when downgraded.

## Backups and recovery

```sh
node scripts/backup.mjs
```

This writes a PostgreSQL custom-format dump under ignored `backups/` with restricted filesystem permissions where supported. Failed dumps retain a `.partial` file and are not reported as completed backups. Copy completed dumps to encrypted off-host storage with restricted access; they contain private account data and password hashes. Back up regularly and test restoration; the local volume alone is not a backup. No backup scheduler has been installed.

For a restore rehearsal, use a **new empty database**, never the live one. The following Bash example leaves the live `rally` database untouched:

```sh
docker compose --project-name rally-production --env-file deploy/.env.production -f compose.production.yaml exec -T db createdb -U rally rally_restore_test
docker compose --project-name rally-production --env-file deploy/.env.production -f compose.production.yaml exec -T db pg_restore --exit-on-error -U rally -d rally_restore_test < backups/CHOSEN_BACKUP.dump
```

`createdb` should fail if the destination already exists; choose another fresh name. Inspect the restored schema/data and rehearse application access against it. The Node backup helper avoids PowerShell binary-redirection corruption; use Bash or a binary-safe pipe when restoring on Windows.

## Local verification without deploying

The CI smoke and backup-check helpers intentionally require `RALLY_ALLOW_TEST_DATA=1` and a disposable stack. They create test accounts and restore databases. Do not point them at club data. The development Compose file supports `RALLY_DB_PORT`, `RALLY_API_PORT`, and `RALLY_FRONTEND_PORT` so an isolated Compose project can run beside the normal localhost app.

HTTPS certificate issuance and live hosting remain unverified until a host/domain is selected. Account recovery and off-host backup storage also need an operational choice before inviting the club.
