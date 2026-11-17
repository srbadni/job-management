from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.users import CreateUser, GetUser
from app.infrastructure.database import engine, get_session, session_factory
from app.infrastructure.users import make_user_transaction
from app.presentation.errors import register_error_handlers
from app.presentation.users import create_users_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        yield
    finally:
        await engine.dispose()


app = FastAPI(lifespan=lifespan)
user_transaction = make_user_transaction(session_factory)
app.include_router(
    create_users_router(CreateUser(user_transaction), GetUser(user_transaction))
)
register_error_handlers(app)


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}


@app.get("/health/db")
async def database_health(
    session: Annotated[AsyncSession, Depends(get_session)],
):
    try:
        result = await session.scalar(text("SELECT 1"))
    except (SQLAlchemyError, OSError, TimeoutError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable",
        ) from None
    if result != 1:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable",
        )
    return {"status": "ok"}
