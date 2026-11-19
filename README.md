# Job Management

A monorepo for a hiring platform. The running backend is the Users service,
built with Python 3.12+, uv, FastAPI, async SQLAlchemy, PostgreSQL and Alembic.
It creates and retrieves users and retains the existing hello and database
health routes.

## Repository layout

```text
compose.yaml             Local stack for the Users service and infrastructure
.env.example             Root development configuration template
services/users/          FastAPI service, uv project and lockfile, migrations, tests, Dockerfile
services/recruiting/     Proposed job postings and application pipelines
services/candidates/     Proposed candidate profiles and preferences
services/documents/      Proposed document metadata and object storage access
services/ai-assessment/  Proposed AI-assisted assessments for human review
services/notifications/ Proposed communication templates and delivery
apps/web/               Proposed Next.js App Router frontend
apps/bff/               Proposed browser-facing backend boundary
```

Each backend service will own its runtime, dependency lockfile, migrations and
data. The proposed boundaries can evolve with the product. Within Users,
`domain` contains users and email invariants, `application` contains use cases
and ports, `infrastructure` implements adapters, and `presentation` maps HTTP
requests and errors. `main.py` wires the layers together. Other services should
integrate through explicit contracts and avoid importing Users internals or
querying its tables.

## Run with Docker Compose

From the repository root, use Docker with the Compose v2 plugin:

```bash
if [ ! -e .env ]; then cp .env.example .env; fi
# Edit .env and replace the example passwords and secret key with local values.
docker compose up --build --wait
docker compose ps -a
```

If you already have a `.env` from the PostgreSQL-only setup, add the new
settings from `.env.example` and keep the PostgreSQL credentials that match
your existing volume. Use single quotes for values containing literal
`$` or `#`. PostgreSQL and RabbitMQ apply their initialization credentials
when their data directories are empty. Changing the file alone does not
rotate those accounts on a populated volume.

Compose builds one Users image. The one-shot `migrate` service runs
`alembic upgrade head` with that image once PostgreSQL is healthy. The API
starts after the migration succeeds. An exited migration container with code
0 is expected. Inspect failures with `docker compose logs migrate app`.

If your build network uses a TLS inspection proxy, give the dependency
build the trusted CA bundle using a local Compose override. The bundle
must contain the normal public roots and your proxy CA.

```yaml
services:
  app:
    build:
      secrets:
        - build_ca_bundle
secrets:
  build_ca_bundle:
    file: /path/to/trusted-ca-bundle.pem
```

Pass the override with `docker compose -f compose.yaml -f /path/to/build-ca.yaml
up --build --wait`. BuildKit mounts the bundle only for dependency
installation.

| Component | Address inside Compose | Default host port |
| --- | --- | --- |
| Users API | `app:8000` | `8000` |
| PostgreSQL | `postgres:5432` | `5432` |
| RabbitMQ (AMQP) | `rabbitmq:5672` | `5672` |
| Redis | `redis:6379` | `6379` |
| MinIO-compatible S3 API | `http://minio:9000` | `9000` |
| Object storage console | `http://minio:9001` | `9001` |

Host ports bind to `127.0.0.1`. The default Compose network provides service
name resolution. The host ports can be changed in `.env` without changing the
container addresses. PostgreSQL, RabbitMQ and object storage persist in named
volumes. Redis is disposable and runs without persistence. `docker compose
down` stops the stack and keeps the named volumes.

The `minio` service uses a pinned release of [PGSTY
Silo](https://github.com/pgsty/silo), a maintained MinIO fork. This keeps the
development image pullable after upstream MinIO ended community image
distribution. Set `MINIO_IMAGE` to use a compatible image from a registry you
can access. The image must support the server command and include `curl` for
the readiness check.

### Smoke checks

```bash
curl --fail-with-body http://127.0.0.1:8000/health/db
docker compose exec app python -m database
docker compose exec app python -m app.infrastructure.check_connections
docker compose exec app alembic current
```

The infrastructure command performs an authenticated AMQP connection, a Redis
`PING`, and an S3 `ListBuckets` request. It closes each client and exits
nonzero if any check fails. The example S3 credentials are for the local
server; this smoke check needs permission to list buckets. These clients are
scoped to the smoke command, so the Users API and its database health check
only depend on PostgreSQL.

The existing API exposes `GET /`, `GET /hello/{name}`,
`GET /health/db`, `POST /users`, and `GET /users/{id}`. For example:

```bash
curl --fail-with-body -X POST http://127.0.0.1:8000/users \
  -H 'Content-Type: application/json' -d '{"email":"alice@example.com"}'
# Use the returned id for GET /users/{id}.
```

User creation still validates and canonicalizes email. The database enforces
uniqueness, and the API returns 422 for invalid input, 409 for duplicates and
404 for unknown users.

## Run and test the Users service on the host

Use Python 3.12 and uv. To run the API on the host, start only its infrastructure
from the repository root. If Compose already owns port 8000, stop its `app`
service first or use a different port for Uvicorn.

```bash
docker compose up -d --wait postgres rabbitmq minio redis
cd services/users
uv sync --locked --python 3.12
uv run --locked alembic upgrade head
uv run --locked python -m app.infrastructure.check_connections
uv run --locked uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

The host Python commands load the root `.env`. Exported variables take
precedence. If you change `MINIO_PORT`, also update the host
`MINIO_ENDPOINT`. Change the port in the HTTP examples if you override
`APP_PORT` or the Uvicorn port.

From `services/users`, run:

```bash
uv run --locked python -m unittest discover -s tests/unit -v
uv run --locked python -m unittest discover -s tests -v
uv run --locked alembic check
```

Unit tests need no infrastructure. The full suite needs PostgreSQL and a
role that can create schemas in the configured database. User integration
tests apply and exercise the real migrations in disposable schemas. Run
`alembic check` against a database already upgraded to head.

## Roadmap

1. Refine service boundaries around job posting and application workflows.
   Define API contracts and authorization boundaries while keeping ownership
   of data explicit.
2. Establish CI for the Users service and decide on deployment, secrets,
   and operational monitoring before deploying independent services.
3. Build the web shell and its initial Next.js BFF against versioned backend
   APIs. Add messaging and storage contracts when a workflow requires them.
4. Define data access, retention, human review and evaluation criteria before
   introducing LLM-assisted hiring workflows.
