import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection, pool
from sqlalchemy.ext.asyncio import create_async_engine

from app.infrastructure.database import settings
from app.infrastructure.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    # Use the same URL/settings as the app; keep credentials out of alembic.ini.
    connectable = create_async_engine(settings.url, poolclass=pool.NullPool)
    try:
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await connectable.dispose()


if context.is_offline_mode():
    context.configure(
        url=settings.url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
elif (connection := config.attributes.get("connection")) is not None:
    # A caller (e.g. an integration test) may supply an existing async connection
    # via run_sync, without attempting to nest asyncio.run in a running loop.
    do_run_migrations(connection)
else:
    asyncio.run(run_async_migrations())
