import unittest
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC
from uuid import UUID, uuid4

from app.application.errors import EmailAlreadyExists, UserNotFound
from app.application.users import CreateUser, GetUser
from app.domain.users import InvalidEmail, User


class FakeUserRepository:
    def __init__(self, users: dict[UUID, User]) -> None:
        self.users = users

    async def add(self, user: User) -> None:
        if any(existing.email == user.email for existing in self.users.values()):
            raise EmailAlreadyExists()
        self.users[user.id] = user

    async def get(self, user_id: UUID) -> User | None:
        return self.users.get(user_id)


class FakeTransaction:
    def __init__(self) -> None:
        self.users: dict[UUID, User] = {}
        self.commits = 0
        self.rollbacks = 0
        self.fail_commit = False

    @asynccontextmanager
    async def __call__(self) -> AsyncIterator[FakeUserRepository]:
        pending = self.users.copy()
        try:
            yield FakeUserRepository(pending)
            if self.fail_commit:
                raise RuntimeError("Commit failed")
        except BaseException:
            self.rollbacks += 1
            raise
        else:
            self.users = pending
            self.commits += 1


class UserDomainTests(unittest.TestCase):
    def test_email_is_canonical_and_identity_is_generated(self):
        user = User(email="  Alice@EXAMPLE.com  ")
        self.assertEqual(user.email, "alice@example.com")
        self.assertIsInstance(user.id, UUID)
        self.assertEqual(user.created_at.tzinfo, UTC)

    def test_invalid_emails_are_rejected(self):
        for email in ["", "bad", "user@", "@example.com", "a..b@example.com", "a b@example.com"]:
            with self.subTest(email=email), self.assertRaises(InvalidEmail):
                User(email=email)

    def test_idn_domain_is_normalized_without_dns(self):
        self.assertEqual(User(email="user@bücher.de").email, "user@xn--bcher-kva.de")


class UserUseCaseTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.transaction = FakeTransaction()
        self.create = CreateUser(self.transaction)
        self.get = GetUser(self.transaction)

    async def test_create_commits_then_get_returns_the_same_entity(self):
        created = await self.create.execute("Alice@example.com")
        self.assertEqual(self.transaction.users[created.id], created)
        self.assertEqual(self.transaction.commits, 1)
        self.assertEqual(await self.get.execute(created.id), created)

    async def test_invalid_email_does_not_open_a_transaction(self):
        with self.assertRaises(InvalidEmail):
            await self.create.execute("not-an-email")
        self.assertEqual(self.transaction.commits, 0)
        self.assertEqual(self.transaction.rollbacks, 0)
        self.assertEqual(self.transaction.users, {})

    async def test_missing_user_raises_application_error(self):
        with self.assertRaises(UserNotFound):
            await self.get.execute(uuid4())

    async def test_duplicate_email_leaves_existing_user_unchanged(self):
        original = await self.create.execute("alice@example.com")
        with self.assertRaises(EmailAlreadyExists):
            await self.create.execute("ALICE@example.com")
        self.assertEqual(self.transaction.users, {original.id: original})
        self.assertEqual(self.transaction.rollbacks, 1)

    async def test_commit_failure_is_propagated_and_does_not_return_success(self):
        self.transaction.fail_commit = True
        with self.assertRaisesRegex(RuntimeError, "Commit failed"):
            await self.create.execute("alice@example.com")
        self.assertEqual(self.transaction.users, {})
        self.assertEqual(self.transaction.commits, 0)
        self.assertEqual(self.transaction.rollbacks, 1)
