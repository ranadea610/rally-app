# Rally · Table tennis coaching

A connected React + TypeScript + Vite frontend and FastAPI + PostgreSQL backend for a university table tennis club. Includes real accounts, coach approval, availability, training/equipment reservations, frontend integration, and CI/deployment preparation.

## Start the full app

With Docker Desktop running, from this directory:

```sh
docker compose up --build -d
```

- App: http://127.0.0.1:8080
- API docs: http://127.0.0.1:8000/docs
- Readiness: http://127.0.0.1:8000/health/ready

Compose starts PostgreSQL, runs migrations, starts the API, and serves the built frontend through nginx. `/api` is proxied to FastAPI on the same browser origin. `docker compose down` stops services and preserves the database volume.

Create a new account using **First time here? Create an account**. The first screen defaults to sign-in. Existing browser-demo logins and bookings are not imported, and no fake coach availability is added to the real club database.

## Coach approval

Players can book immediately. Coach and dual-role registrations request officer approval. Pending coaches see their approval status, and the backend blocks publishing until approval. Dual-role members can keep using Player view.

Bootstrap a trusted officer with the local operator command described in [backend/README.md](backend/README.md). Once promoted, an officer can approve pending coaches in the app's **Coach requests** card. Coaches then publish their practice availability in Coach view. Normal signup cannot grant officer permissions.

## Included

- Instagram, Discord, or international phone-number sign-in; hashed passwords and HttpOnly server sessions.
- Player, coach, and dual-role views, with pending coach approval and officer controls.
- Monthly calendar with current-day highlighting, collapsible coach sections, booked slots, and month navigation.
- Weekly Monday/Tuesday/Thursday 6:30–9 PM availability editor with click/drag or keyboard selection. Publishing replaces the selected week atomically; booked slots are protected.
- Six training types: rally, multi-ball, serve practice, receive practice, serve/receive, and short game.
- Multi-ball and all serve/receive training reserve the one shared training-ball set and ball catcher. Rally and short game do not need them.
- Transactional conflict prevention, booking confirmation, upcoming sessions, coaching schedules, and cancellation that releases equipment.
- Loading/error/retry states, stale booking-conflict handling, cookie-session restoration, session-expiry handling, and periodic/focus refresh.
- Every schedule and appointment displays in the backend's club timezone, including daylight saving changes, regardless of the browser's timezone.
- Fonts are bundled locally; the UI does not depend on external font requests.

Accounts, availability, and reservations live in PostgreSQL. The application no longer reads or writes localStorage scheduling data.

## Frontend development

```sh
docker compose up --build -d api
npm ci
npm run dev
```

Vite prints its URL (normally http://127.0.0.1:5173). It proxies `/api` to `http://127.0.0.1:8000`. Set `RALLY_API_TARGET` to change the development proxy target. `VITE_API_BASE_URL` defaults to `/api`; an external API requires matching CORS, cookie, and HTTPS configuration. `vite preview` does not supply the development proxy; use the Docker frontend to test a production build with the API.

The earlier ChatGPT-hosted static demo is separate from this connected local app. Deploying the connected version externally requires hosting FastAPI and PostgreSQL and configuring an HTTPS API route; no local API URL is embedded into a hosted build.

## Verification

```sh
npm run build
npm test
```

The backend setup, migrations, and PostgreSQL pytest instructions are in [backend/README.md](backend/README.md).

Browser tests use a separate migrated test database, temporary API/frontend servers on ports 8001/5175, and run-specific fixture accounts. Create the database and backend Python environment first, following the backend README. Then:

```sh
npx playwright install chromium
npm run test:e2e
```

`RALLY_E2E_DATABASE_URL` defaults to the local `rally_test` database. Only PostgreSQL database names ending in `_test` are accepted. The runner applies migrations and removes its own fixtures afterward; don't run pytest against the same database concurrently. Tests cover registration/approval, persistence, weekly publishing, shared equipment, stale conflicts, cancellation, retry, and session expiry. They deliberately run the browser in Tokyo while the club uses Los Angeles time.

## Deployment boundaries

`compose.yaml` is for localhost development. The standalone `compose.production.yaml` adds an HTTPS edge, private networking, secure cookies, and sign-in rate limiting. GitHub Actions checks builds, PostgreSQL, browser workflows, and containers after the workflow is pushed. Backend dependencies are pinned through shared constraints; install `backend/requirements-dev.txt` for testing.

See [deploy/README.md](deploy/README.md) for CI details, production configuration, release, rollback, and backup/restore instructions. Hosting is intentionally undecided: no live deployment or automatic production rollout has been configured. Account recovery and off-host backups need operational setup before inviting members. Waitlists, 30-minute paid sessions, and messaging integrations remain future work.
