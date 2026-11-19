import unittest
from contextlib import asynccontextmanager

from pydantic import ValidationError
from sqlalchemy import text

from app.infrastructure.database import DatabaseSettings, engine, get_session
from main import app, lifespan


class DatabaseSettingsTests(unittest.TestCase):
    def settings(self, **overrides) -> DatabaseSettings:
        values = {
            "postgres_host": "localhost",
            "postgres_port": 5432,
            "postgres_db": "test_db",
            "postgres_user": "test_user",
            "postgres_password": "p@ss:/?#%",
        }
        values.update(overrides)
        return DatabaseSettings(_env_file=None, **values)

    def test_host_url_and_password(self):
        url = self.settings().url
        self.assertEqual(url.drivername, "postgresql+asyncpg")
        self.assertEqual(url.host, "localhost")
        self.assertEqual(url.port, 5432)
        self.assertEqual(url.password, "p@ss:/?#%")
        self.assertNotIn("p@ss", str(url))

    def test_container_url(self):
        self.assertEqual(self.settings(postgres_host="postgres").url.host, "postgres")

    def test_invalid_port(self):
        with self.assertRaises(ValidationError):
            self.settings(postgres_port=70000)


class DatabaseIntegrationTests(unittest.IsolatedAsyncioTestCase):
    """Requires the configured PostgreSQL service; never modifies schema or data."""

    async def asyncTearDown(self):
        # Each test has its own loop; don't carry pooled connections across loops.
        await engine.dispose()

    async def test_session_releases_connection(self):
        async with asynccontextmanager(get_session)() as session:
            self.assertEqual(await session.scalar(text("SELECT 1")), 1)
            self.assertTrue(session.in_transaction())
            self.assertEqual(engine.pool.checkedout(), 1)
        self.assertFalse(session.in_transaction())
        self.assertEqual(engine.pool.checkedout(), 0)

    async def test_session_releases_connection_on_error(self):
        with self.assertRaisesRegex(RuntimeError, "request failed"):
            async with asynccontextmanager(get_session)() as session:
                self.assertEqual(await session.scalar(text("SELECT 1")), 1)
                raise RuntimeError("request failed")
        self.assertFalse(session.in_transaction())
        self.assertEqual(engine.pool.checkedout(), 0)

    async def test_lifespan_disposes_pool(self):
        async with lifespan(app):
            async with engine.connect() as connection:
                self.assertEqual(await connection.scalar(text("SELECT 1")), 1)
            self.assertEqual(engine.pool.checkedin(), 1)
        self.assertEqual(engine.pool.checkedin(), 0)


if __name__ == "__main__":
    unittest.main()
