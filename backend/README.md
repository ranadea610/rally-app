# Rally backend — phases 1–6

FastAPI + SQLAlchemy + Alembic + PostgreSQL. Includes accounts, availability, training types, shared equipment, and transactional booking/cancellation. The React frontend now uses these APIs for all account and scheduling workflows. Waitlists are not implemented yet.

## Start with Docker

From the repository root, with Docker Desktop running:

```sh
docker compose up --build -d
```

Compose starts PostgreSQL, runs `alembic upgrade head`, starts the API after migrations succeed, and serves the connected React app at http://127.0.0.1:8080. Open http://127.0.0.1:8000/docs for the interactive API. Readiness: http://127.0.0.1:8000/health/ready. Database storage persists in the `rally_pgdata` volume. `docker compose down` stops the services without deleting that volume.

The included database credentials and non-secure cookies are for localhost development. Set a unique database password, HTTPS, `COOKIE_SECURE=true`, and an exact `ALLOWED_ORIGINS` list before deployment. Never expose the development database publicly. API and database ports bind to loopback only. Add login rate limiting and account recovery before public rollout.

## Local Python development (PowerShell)

From the repository root:

```powershell
docker compose up -d db
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
.venv/Scripts/python -m alembic upgrade head
.venv/Scripts/python -m uvicorn app.main:app --reload
```

Run Python commands from `backend/`. On macOS/Linux use `.venv/bin/python`. The sample config uses the club timezone `America/Los_Angeles`; change `CLUB_TIMEZONE` if needed. Timestamp inputs must include an offset. PostgreSQL stores timezone-aware instants, and practice validation happens in the configured club timezone, including daylight saving changes. Date queries use club-local dates and an exclusive end date.

## Accounts and officer setup

1. `POST /auth/register` with `name`, `contact_method` (`instagram`, `discord`, `phone`), `contact`, `password` (8–128 characters), and `role` (`player`, `coach`, `both`). Registration signs the user in. Phone contacts require international format such as `+14155551234`; Instagram handles ignore `@` and casing.
2. Login with the contact method, contact, and password at `POST /auth/login`. Passwords use Argon2 hashes. Server-side sessions expire after seven days by default; only a SHA-256 hash of the session credential is stored in PostgreSQL. The browser receives an HttpOnly, SameSite=Lax cookie.
3. Login/register and `GET /auth/me` return `{user, csrf_token}`. Send that token as `X-CSRF-Token` on authenticated POST, PUT, and DELETE requests. Browser API calls need `credentials: 'include'`. Use the same hostname for frontend and API (both `localhost` or both `127.0.0.1`) so SameSite cookies work during development. The cookie is not accessible to JavaScript. Login/register also reject untrusted browser origins.
4. Coaching requests start **unapproved**. A role selection never grants coach permissions by itself. To bootstrap a trusted officer, find their registered user ID from `/auth/me`, then run:

```sh
docker compose exec api python -m app.cli make-admin USER_ID
```

The local equivalent is `.venv/Scripts/python -m app.cli make-admin USER_ID`. This requires local database/operator access; there is no public administrator-registration route.

5. The officer can list `GET /admin/coach-requests` and approve `POST /admin/coaches/{user_id}/approve` using their own authenticated cookie and CSRF token. Coaches can publish only after approval. `/auth/me` reports `requested_role`, `coach_approved`, and `is_admin` so the future frontend can show approval state explicitly.
6. `POST /auth/logout` deletes the current server session and clears its cookie.

## Availability API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/calendar?start=2030-01-01&end=2030-02-01` | Authenticated calendar containing coach names and derived 15-minute slots; never contact details |
| GET | `/coach/availability?start=2030-01-01&end=2030-02-01` | Approved coach's own availability windows |
| POST | `/coach/availability` | Publish a window |
| PUT | `/coach/availability/{id}` | Replace an owned window |
| PUT | `/coach/availability/week` | Atomically replace all availability in one Monday-starting week |
| DELETE | `/coach/availability/{id}` | Delete an owned window |

POST/PUT body example (choose a future Monday, Tuesday, or Thursday):

```json
{"starts_at":"2030-01-07T18:30:00-08:00","ends_at":"2030-01-07T19:30:00-08:00"}
```

Weekly PUT accepts `{"week_start":"2030-01-07","windows":[...]}` where each window has the same timestamp fields above. Up to 30 windows may be selected. Every window must fit inside that week and practice hours. Existing past slots may be preserved, but new past availability cannot be added. All active booked intervals must remain covered; reservation references are reassigned to the replacement windows inside the same transaction. Any validation failure leaves the entire previous week intact.

Windows must stay within 6:30–9 PM on a single practice date, align to 15-minute boundaries, and start in the future. Adjacent windows are allowed. Overlaps for the same coach return HTTP 409. All mutations serialize on the coach's database row, so simultaneous writes cannot both insert overlapping windows. Other coaches' windows cannot be edited or deleted. Date queries are bounded to 93 days. An active reservation's window cannot be deleted or shortened to exclude the reservation; cancel the affected sessions first. Expanding or otherwise editing a window while preserving all booked intervals is allowed.

## Training, equipment, and reservations

Migration `0002` seeds six training types. `rally` and `short-game` need no club equipment. `multi-ball`, `serve-practice`, `receive-practice`, and `serve-receive` each require **both** the training-ball set and ball catcher. Each equipment row represents one resource of capacity one. Requirements are stored in the database rather than duplicated in API conditionals.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/training-types` | Training catalog with required equipment IDs |
| GET | `/equipment` | Inventory names and capacities |
| GET | `/booking-options?coach_id=ID&starts_at=TIMESTAMP` | Snapshot of which training types can be booked at a chosen time |
| POST | `/reservations` | Book a 15-minute session and required equipment atomically |
| GET | `/reservations` | Current player's upcoming active sessions with training and equipment details |
| GET | `/coach/reservations?start=DATE&end=DATE` | Approved coach's active sessions, including player names |
| DELETE | `/reservations/{id}` | Player or booked coach cancels a session and releases its equipment |

These endpoints require authentication; writes also require `X-CSRF-Token`. Only `player` and `both` roles can book. A player cannot coach themselves, hold overlapping sessions, or play while they are coaching someone else. Coaches must be approved and available for the entire requested interval. The server derives the end time; extra client-supplied player IDs or durations cannot override it.

Example booking body:

```json
{"coach_id":"COACH_UUID","starts_at":"2030-01-07T19:00:00-08:00","training_type_id":"multi-ball"}
```

Use URL encoding for timestamps in query parameters (`+` must be encoded as `%2B`); an HTTP client's `params` option handles this. Booking-options results are a snapshot: the final POST always rechecks everything transactionally. Conflicts return HTTP 409 and leave no partial coach/equipment reservation. Unknown training and invalid times return 422. Cancellation is idempotent, preserves a canceled reservation for history, and cannot occur after a session starts. Other users cannot inspect or cancel your reservations. The calendar returns `booked` and `equipment_available` on each slot without exposing other players' identities; equipment occupation alone does not block rally or short game with a free coach.

Booking transactions lock coach/player rows in stable ID order, then required equipment rows in stable order. Cancellation and availability edits follow compatible locking rules. PostgreSQL exclusion constraints also reject overlapping active bookings per coach/player and overlapping active equipment allocations. Ranges are half-open, so a 7:00–7:15 session and a 7:15–7:30 session do not conflict. The migration enables `btree_gist`; the database migration account must be allowed to install this extension (or an operator must install it first). Downgrade removes booking tables but leaves the potentially shared extension installed.

## Migrations

```sh
alembic upgrade head
alembic check
alembic downgrade base
```

Downgrading removes the backend tables and their data; use it only on a disposable database. Never use model `create_all` as a migration substitute. Generate future revisions with `alembic revision --autogenerate -m "description"` and review the resulting file.

## Tests with PostgreSQL

The tests require a dedicated migrated database whose name ends in `_test`. They use savepoints and roll back test records; they will reject a non-test database URL. From the repo root:

```powershell
docker compose up -d db
docker compose exec db createdb -U rally rally_test
cd backend
$env:DATABASE_URL = 'postgresql+psycopg://rally:rally@127.0.0.1:5432/rally_test'
.venv/Scripts/python -m alembic upgrade head
$env:TEST_DATABASE_URL = $env:DATABASE_URL
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m alembic check
```

`createdb` is needed only once. Without `TEST_DATABASE_URL`, database integration tests are explicitly skipped; pure validation tests still run. Clear the test environment variables before running the development server against the regular database. Tests cover authentication, permissions, practice rules, availability CRUD, all training requirements, equipment conflicts, cancellation, availability protection, database constraints, and concurrent requests. Concurrency tests use independent real PostgreSQL transactions and verify that only one conflicting booking wins; simultaneous rally and adjacent equipment sessions can both succeed.
