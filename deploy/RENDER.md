# Free Render + Neon pilot

This deployment uses `Dockerfile.render` at the repository root. It builds React
and serves it alongside FastAPI at the same HTTPS origin. The normal Docker
Compose deployment is unchanged. No hosting resources are created by these files.

1. Create a Neon Free project with PostgreSQL 17, preferably in the same region
   as the Render service. Use a fresh database for the pilot.
2. Ensure the database role password is a unique random secret of at least 32
   characters (required by Rally's production settings). If necessary, change it
   in Neon, then copy the updated connection string from Connect. Keep it private.
3. Choose the direct/unpooled connection for this small single-service pilot.
   Change only the URL scheme from `postgresql://` to `postgresql+psycopg://`.
   Keep its SSL query parameters and URL-encoded credentials intact. Do not copy
   the surrounding `psql` command or quotes.
4. Commit and push the deployment files to GitHub.
5. In Render, create a Web Service from the repository, select Docker, leave
   Root Directory blank, set Dockerfile Path to `./Dockerfile.render`, and select
   Free. Keep Docker Command blank. Set health check to `/api/health/ready`.
6. Set the environment variables below. Replace the example origin with the
   exact HTTPS URL assigned by Render, without a trailing slash. If it is only
   shown after creation, update ALLOWED_ORIGINS and redeploy before testing login.

| Variable | Value |
| --- | --- |
| DATABASE_URL | Private Neon SQLAlchemy connection URL from step 3 |
| ENVIRONMENT | production |
| COOKIE_SECURE | true |
| CLUB_TIMEZONE | America/Los_Angeles |
| ALLOWED_ORIGINS | ["https://YOUR-SERVICE.onrender.com"] |

Render supplies PORT; the image uses it automatically. Startup runs `alembic
upgrade head` before starting the application. For this pilot keep one service
against the database; do not deploy multiple independent services concurrently
running migrations. Review future migrations and take backups before upgrades.

7. Deploy, then check `/api/health/ready` and register through the home page.
   This creates a fresh account; local development accounts are not transferred.
8. Bootstrap your own registered account in Neon's SQL Editor. First find its ID:

```sql
SELECT id, name, contact_method, contact FROM users;
```

Then promote only your trusted account using that exact ID:

```sql
UPDATE users SET is_admin = true WHERE id = 'YOUR_ACCOUNT_ID';
```

Refresh the app and use the approval card to approve coaches. Test publishing
availability, booking, equipment conflicts, cancellation, and login persistence
before sharing the URL with the pilot group.

Free Render services sleep after inactivity and can take about a minute to wake.
Keep user data in Neon, not the container filesystem. Review both dashboards'
usage limits. The full-server nginx login rate limiter is not part of this
single-process pilot deployment; add application-level rate limiting before a
broad public launch. Arrange database exports and account recovery for club use.

Official instructions: https://render.com/docs/web-services,
https://render.com/docs/free, https://neon.com/docs/get-started/signing-up.
