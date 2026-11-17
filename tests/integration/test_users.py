import asyncio
from uuid import uuid4

from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.application.errors import EmailAlreadyExists, UserNotFound
from app.application.users import CreateUser, GetUser
from app.domain.users import User
from app.infrastructure.models import UserRow
from tests.integration.support import PostgresTestCase


class UserPersistenceTests(PostgresTestCase):
    async def test_create_and_get_round_trip(self):
        created = await CreateUser(self.transaction).execute(" Alice@EXAMPLE.com ")
        fetched = await GetUser(self.transaction).execute(created.id)
        self.assertEqual(fetched, created)
        self.assertIsInstance(fetched, User)
        self.assertEqual(fetched.email, "alice@example.com")
        self.assertIsNotNone(fetched.created_at.utcoffset())
        self.assertEqual(self.engine.pool.checkedout(), 0)

    async def test_duplicate_email_is_translated_and_next_transaction_works(self):
        original = await CreateUser(self.transaction).execute("alice@example.com")
        with self.assertRaises(EmailAlreadyExists):
            await CreateUser(self.transaction).execute("ALICE@example.com")
        self.assertEqual(await GetUser(self.transaction).execute(original.id), original)
        await CreateUser(self.transaction).execute("bob@example.com")
        self.assertEqual(self.engine.pool.checkedout(), 0)

    async def test_database_unique_constraint_handles_concurrent_creates(self):
        results = await asyncio.gather(
            CreateUser(self.transaction).execute("race@example.com"),
            CreateUser(self.transaction).execute("RACE@example.com"),
            return_exceptions=True,
        )
        self.assertEqual(sum(isinstance(result, User) for result in results), 1)
        self.assertEqual(
            sum(isinstance(result, EmailAlreadyExists) for result in results), 1
        )

    async def test_repository_does_not_commit_and_failure_rolls_back(self):
        user = User(email="rollback@example.com")
        with self.assertRaisesRegex(RuntimeError, "Request failed"):
            async with self.transaction() as users:
                await users.add(user)
                raise RuntimeError("Request failed")
        with self.assertRaises(UserNotFound):
            await GetUser(self.transaction).execute(user.id)
        self.assertEqual(self.engine.pool.checkedout(), 0)

    async def test_other_integrity_errors_are_not_reported_as_email_conflicts(self):
        original = await CreateUser(self.transaction).execute("alice@example.com")
        same_id = User(id=original.id, email="other@example.com")
        with self.assertRaises(IntegrityError):
            async with self.transaction() as users:
                await users.add(same_id)

    async def test_database_rejects_noncanonical_email(self):
        async with self.sessions() as session:
            with self.assertRaises(IntegrityError):
                async with session.begin():
                    session.add(
                        UserRow(
                            id=uuid4(),
                            email="UPPER@example.com",
                            created_at=User(email="x@example.com").created_at,
                        )
                    )

    async def test_migration_downgrade_and_upgrade(self):
        await self.migrate("downgrade", "base")
        async with self.engine.connect() as connection:
            tables = await connection.run_sync(lambda conn: inspect(conn).get_table_names())
        self.assertNotIn("users", tables)
        await self.migrate("upgrade", "head")
        async with self.engine.connect() as connection:
            revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
        self.assertEqual(revision, "0001_create_users")
        await CreateUser(self.transaction).execute("after-migration@example.com")
