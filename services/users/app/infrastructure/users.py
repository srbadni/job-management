from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.errors import EmailAlreadyExists
from app.application.ports import UserRepository, UserTransaction
from app.domain.users import User
from app.infrastructure.models import USER_EMAIL_CONSTRAINT, UserRow


def to_row(user: User) -> UserRow:
    return UserRow(id=user.id, email=user.email, created_at=user.created_at)


def to_domain(row: UserRow) -> User:
    return User(id=row.id, email=row.email, created_at=row.created_at)


class SqlAlchemyUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, user: User) -> None:
        self.session.add(to_row(user))
        # Detect persistence errors now, but never commit inside a repository.
        await self.session.flush()

    async def get(self, user_id: UUID) -> User | None:
        row = await self.session.get(UserRow, user_id)
        return to_domain(row) if row is not None else None


def make_user_transaction(sessions: async_sessionmaker[AsyncSession]) -> UserTransaction:
    @asynccontextmanager
    async def transaction() -> AsyncIterator[UserRepository]:
        async with sessions() as session:
            try:
                async with session.begin():
                    yield SqlAlchemyUserRepository(session)
            except IntegrityError as exc:
                # asyncpg's original PostgreSQL error carries the constraint name.
                # Don't misreport primary-key/check/other integrity errors as email conflicts.
                cause = exc.orig.__cause__
                if (
                    getattr(exc.orig, "sqlstate", None) == "23505"
                    and getattr(cause, "constraint_name", None) == USER_EMAIL_CONSTRAINT
                ):
                    raise EmailAlreadyExists() from exc
                raise

    return transaction
