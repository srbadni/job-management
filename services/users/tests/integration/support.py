import unittest
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy.schema import CreateSchema, DropSchema
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.infrastructure.database import settings
from app.infrastructure.users import make_user_transaction


class PostgresTestCase(unittest.IsolatedAsyncioTestCase):
    """Apply real migrations in a disposable schema, never in the app's schema."""

    async def asyncSetUp(self):
        self.schema = "test_users_" + uuid4().hex
        self.admin = create_async_engine(settings.url, poolclass=NullPool)
        self.engine = create_async_engine(
            settings.url,
            connect_args={"server_settings": {"search_path": self.schema}, "timeout": 5},
        )
        self.addAsyncCleanup(self.cleanup_database)
        async with self.admin.begin() as connection:
            await connection.execute(CreateSchema(self.schema))
        await self.migrate("upgrade", "head")
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        self.transaction = make_user_transaction(self.sessions)

    async def migrate(self, operation: str, revision: str):
        def run(connection):
            cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
            cfg.attributes["connection"] = connection
            getattr(command, operation)(cfg, revision)

        async with self.engine.begin() as connection:
            await connection.run_sync(run)

    async def cleanup_database(self):
        try:
            await self.engine.dispose()
            async with self.admin.begin() as connection:
                await connection.execute(DropSchema(self.schema, cascade=True, if_exists=True))
        finally:
            await self.admin.dispose()
