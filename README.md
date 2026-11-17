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
The app loads it relative to `database.py`; exported environment variables take
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

## Run FastAPI on the host

```bash
uv run --locked uvicorn main:app --host 0.0.0.0 --port 8000 --reload
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
which closes on success or error and rolls back uncommitted work. Write handlers
must explicitly commit their transactions; the dependency never auto-commits.
FastAPI's lifespan disposes the engine's connection pool at shutdown.

With PostgreSQL running, execute the configuration and integration tests:

```bash
uv run --locked python -m unittest discover -s tests -v
```

These tests verify URL settings, real query execution, session cleanup on
success and error, and pool disposal at shutdown without changing schema/data.

No schema, models, or migrations are introduced by this connection setup.
