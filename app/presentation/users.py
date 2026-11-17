from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from app.application.users import CreateUser, GetUser
from app.domain.users import User


class CreateUserRequest(BaseModel):
    email: str = Field(min_length=1, max_length=254)


class UserResponse(BaseModel):
    id: UUID
    email: str
    created_at: datetime

    @classmethod
    def from_domain(cls, user: User) -> "UserResponse":
        return cls(id=user.id, email=user.email, created_at=user.created_at)


def create_users_router(create_user: CreateUser, get_user: GetUser) -> APIRouter:
    router = APIRouter(prefix="/users", tags=["users"])

    @router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
    async def create_user_endpoint(payload: CreateUserRequest) -> UserResponse:
        user = await create_user.execute(payload.email)
        return UserResponse.from_domain(user)

    @router.get("/{user_id}", response_model=UserResponse)
    async def get_user_endpoint(user_id: UUID) -> UserResponse:
        user = await get_user.execute(user_id)
        return UserResponse.from_domain(user)

    return router
