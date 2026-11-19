from uuid import UUID

from app.application.errors import UserNotFound
from app.application.ports import UserTransaction
from app.domain.users import User


class CreateUser:
    def __init__(self, transaction: UserTransaction) -> None:
        self.transaction = transaction

    async def execute(self, email: str) -> User:
        user = User(email=email)
        async with self.transaction() as users:
            await users.add(user)
        # The transaction must finish successfully before returning the result.
        return user


class GetUser:
    def __init__(self, transaction: UserTransaction) -> None:
        self.transaction = transaction

    async def execute(self, user_id: UUID) -> User:
        async with self.transaction() as users:
            user = await users.get(user_id)
            if user is None:
                raise UserNotFound()
        return user
