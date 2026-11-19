import asyncio
from collections.abc import AsyncIterator

from pydantic import Field, SecretStr
from sqlalchemy import URL, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.infrastructure.settings import LocalSettings


class DatabaseSettings(LocalSettings):
    postgres_host: str = Field(default="localhost", min_length=1)
    postgres_port: int = Field(default=5432, ge=1, le=65535)
    postgres_db: str = Field(min_length=1)
    postgres_user: str = Field(min_length=1)
    postgres_password: SecretStr = Field(min_length=1)

    @property
    def url(self) -> URL:
        # Build the URL without manually escaping passwords or other components.
        return URL.create(
            "postgresql+asyncpg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )


settings = DatabaseSettings()
engine = create_async_engine(
    settings.url,
    pool_pre_ping=True,
    connect_args={"timeout": 5},
)
session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    # Closing also rolls back any uncommitted transaction, including on errors.
    async with session_factory() as session:
        yield session


async def check_connection() -> None:
    try:
        async with engine.connect() as connection:
            result = await connection.scalar(text("SELECT 1"))
            if result != 1:
                raise RuntimeError("Unexpected database check result")
            print("PostgreSQL connection OK: SELECT 1 = 1")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(check_connection())
