from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.application.errors import EmailAlreadyExists, UserNotFound
from app.domain.users import InvalidEmail


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(InvalidEmail)
    async def invalid_email(request: Request, exc: InvalidEmail) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"detail": "Invalid email address"},
        )

    @app.exception_handler(EmailAlreadyExists)
    async def duplicate_email(request: Request, exc: EmailAlreadyExists) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": "A user with this email already exists"},
        )

    @app.exception_handler(UserNotFound)
    async def user_not_found(request: Request, exc: UserNotFound) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": "User not found"},
        )
