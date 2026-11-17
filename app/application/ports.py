from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Protocol
from uuid import UUID

from app.domain.users import User


class UserRepository(Protocol):
    async def add(self, user: User) -> None: ...

    async def get(self, user_id: UUID) -> User | None: ...


# A successful exit commits; an exceptional exit rolls back and propagates errors.
# Each call creates a fresh repository/session, so use cases can be shared safely.
UserTransaction = Callable[[], AbstractAsyncContextManager[UserRepository]]
