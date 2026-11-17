# Job Management

A small FastAPI application using Python 3.12+, `uv`, SQLAlchemy 2.x, and
`asyncpg`. Run the following commands from the repository root. Docker with the
Compose plugin is required for the local PostgreSQL service.

## Configure and install

```bash
if [ ! -f .env ]; then cp .env.example .env; fi
# For a new .env, replace POSTGRES_PASSWORD with a local development password.
uv sync --locked --python 3.12
```

`.env` is ignored by Git. It contains local settings, not production credentials.
The app loads it from the repository root; exported environment variables take
precedence. All three of `POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD`
are required. The host defaults to `localhost`, and the port defaults to `5432`.
SQLAlchemy builds the `postgresql+asyncpg` URL from these fields, so passwords
containing URL-special characters do not need URL encoding. Single-quote values
in `.env` when they contain literal `$` or `#`, so both dotenv and Compose read
the same password.

## Start PostgreSQL

```bash
docker compose up -d --wait postgres
docker compose ps
```

Compose runs PostgreSQL 17, publishes its port on loopback only, checks readiness
with `pg_isready`, and retains data in the `postgres_data` named volume. The
healthcheck verifies server readiness; the application checks below also verify
authentication and query execution.

```bash
docker compose stop postgres          # Keep containers and data
docker compose down                   # Remove containers, retain data
# docker compose down -v              # Destructive: deletes the local database
```

PostgreSQL's initialization variables apply only to an empty volume. Changing
the username, database, or password in `.env` does not update an existing
database; update it through PostgreSQL, or deliberately recreate disposable local
data. Do not remove a volume containing data you need.

## Migrations and FastAPI on the host

```bash
uv run --locked alembic upgrade head
uv run --locked alembic current
uv run --locked uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The app and Alembic share the same environment settings and asyncpg URL; no
credentials are stored in `alembic.ini`. Apply migrations before serving requests.
Startup never calls `create_all`. The initial migration creates `users` with a
UUID primary key, non-null email and timezone-aware `created_at`, a named email
uniqueness constraint, and a lowercase storage check. Future schema changes:

```bash
uv run --locked alembic revision --autogenerate -m "describe schema change"
# Review the generated migration before applying it.
uv run --locked alembic upgrade head
uv run --locked alembic check
# uv run --locked alembic downgrade -1  # Destructive: initial downgrade drops users
```

For this mode, keep `POSTGRES_HOST=localhost` and set `POSTGRES_PORT` to the
published port (default `5432`). If that port is occupied, choose another port in
`.env` and run `docker compose up -d --wait postgres` again.

## FastAPI inside Docker

`localhost` inside an application container means that container, not PostgreSQL.
When running FastAPI in the **same Compose network**, explicitly override its
environment:

```yaml
# Add these settings to your FastAPI container service, if you have one.
environment:
  POSTGRES_HOST: postgres
  POSTGRES_PORT: "5432"
depends_on:
  postgres:
    condition: service_healthy
```

Pass `POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD` to that service as
well (for local development, `env_file: .env` is one option). The environment
overrides the host defaults in `.env`. Use PostgreSQL's internal port `5432`
even if its published host port differs. A standalone application container
must join this Compose project's network for the `postgres` hostname to resolve.
Only the database is containerized by the supplied Compose file; there is no
application image or automatic container detection.

## Test the connection

With PostgreSQL running, test the async engine directly without starting FastAPI:

```bash
uv run --locked python -m database
# PostgreSQL connection OK: SELECT 1 = 1
```

This command runs a real `SELECT 1`, exits nonzero on failure, and disposes the
engine even if the query fails. With FastAPI running, test the request-scoped
session and the existing routes:

```bash
curl --fail-with-body http://127.0.0.1:8000/health/db
# {"status":"ok"}
curl --fail-with-body http://127.0.0.1:8000/
# {"message":"Hello World"}
curl --fail-with-body http://127.0.0.1:8000/hello/User
# {"message":"Hello User"}
```

`/health/db` executes `SELECT 1` through `Depends(get_session)` and returns HTTP
503 if the database is unavailable. Each request gets its own async session,
which closes on success or error and rolls back uncommitted work. This low-level
dependency never auto-commits. User use cases instead use the transaction boundary
described below, which completes before the HTTP response is returned.
FastAPI's lifespan disposes the engine's connection pool at shutdown.

## Architecture and User example

```text
app/
  domain/users.py          # User entity and email invariant; no web/ORM dependencies
  application/
    ports.py              # UserRepository contract and transaction factory type
    users.py              # CreateUser and GetUser use cases
    errors.py             # EmailAlreadyExists and UserNotFound
  infrastructure/
    database.py           # Async engine, sessions, environment settings
    models.py             # SQLAlchemy Base and UserRow (separate from User)
    users.py              # Repository, domain/ORM mapping, transaction adapter
  presentation/
    users.py              # FastAPI router and request/response schemas
    errors.py             # Domain/application errors -> HTTP
migrations/               # Alembic environment and versioned schema changes
tests/unit/               # Domain/use cases with fakes, no database
tests/integration/        # Real PostgreSQL, migrations, and HTTP tests
main.py                   # Composition root; also retains the existing health routes
database.py               # Compatibility entry point for the connection check
```

Dependencies point inward: `presentation -> application -> domain` and
`infrastructure -> application/domain`. Only the composition root wires all
layers together. Routers receive use cases, and use cases only know the repository
contract and a transaction factory. Domain uses `email-validator` for syntax
validation but never imports FastAPI, Pydantic, SQLAlchemy, or database settings.

Each use case enters one transaction. The infrastructure adapter opens a fresh
async session and uses `session.begin()` to commit on successful exit or roll back
on errors. The session closes before the use case returns. Repositories flush
but never commit. There is no generic repository, CQRS, event bus, or auth layer.

```bash
curl --fail-with-body -X POST http://127.0.0.1:8000/users \
  -H 'Content-Type: application/json' -d '{"email":"alice@example.com"}'
# 201: {"id":"<uuid>","email":"alice@example.com","created_at":"<UTC timestamp>"}
curl --fail-with-body 'http://127.0.0.1:8000/users/<uuid>'
# Replace <uuid> with the id returned by POST.
```

Emails are trimmed, validated without DNS, converted to ASCII for IDN domains,
and stored in lowercase. Identity by email is case insensitive, including the
local part; SMTPUTF8 local parts are not supported in this initial example.
The database constraint, not a pre-insert lookup, resolves concurrent duplicate
creates. Invalid input returns 422, duplicate email 409, and missing user 404.
Other database integrity errors are not mislabeled as duplicate emails.

## Tests

```bash
# No PostgreSQL, .env, or database credentials needed:
uv run --locked python -m unittest discover -s tests/unit -v

# Requires configured PostgreSQL and a role with CREATE permission on the database:
docker compose up -d --wait postgres
uv run --locked python -m unittest discover -s tests/integration -v

# All tests (same PostgreSQL requirement):
uv run --locked python -m unittest discover -s tests -v
```

Unit tests exercise domain invariants, use cases, and transaction failures with
in-memory fakes. Integration tests apply the real migrations in a uniquely named
disposable schema per test, then drop only that schema. They do not truncate or
drop application tables. They cover persistence round trips, rollback, concurrent
uniqueness, HTTP error mapping, downgrade/upgrade, and the existing session/pool
cleanup checks. `httpx` is a development dependency only.
