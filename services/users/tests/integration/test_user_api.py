from uuid import uuid4

import httpx
from fastapi import FastAPI

from app.application.users import CreateUser, GetUser
from app.presentation.errors import register_error_handlers
from app.presentation.users import create_users_router
from tests.integration.support import PostgresTestCase


class UserApiTests(PostgresTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        app = FastAPI()
        app.include_router(
            create_users_router(CreateUser(self.transaction), GetUser(self.transaction))
        )
        register_error_handlers(app)
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        )
        self.addAsyncCleanup(self.client.aclose)

    async def test_create_get_and_duplicate_email(self):
        response = await self.client.post("/users", json={"email": "Alice@EXAMPLE.com"})
        self.assertEqual(response.status_code, 201, response.text)
        user = response.json()
        self.assertEqual(set(user), {"id", "email", "created_at"})
        self.assertEqual(user["email"], "alice@example.com")
        fetched = await self.client.get(f"/users/{user['id']}")
        self.assertEqual(fetched.status_code, 200, fetched.text)
        self.assertEqual(fetched.json(), user)
        duplicate = await self.client.post("/users", json={"email": "ALICE@example.com"})
        self.assertEqual(duplicate.status_code, 409, duplicate.text)
        self.assertEqual(duplicate.json(), {"detail": "A user with this email already exists"})
        self.assertEqual(self.engine.pool.checkedout(), 0)

    async def test_unknown_user_returns_404(self):
        response = await self.client.get(f"/users/{uuid4()}")
        self.assertEqual(response.status_code, 404, response.text)
        self.assertEqual(response.json(), {"detail": "User not found"})

    async def test_invalid_input_returns_422(self):
        for payload in [{"email": "invalid"}, {"email": ""}, {}, {"email": 12}]:
            with self.subTest(payload=payload):
                response = await self.client.post("/users", json=payload)
                self.assertEqual(response.status_code, 422, response.text)
        response = await self.client.get("/users/not-a-uuid")
        self.assertEqual(response.status_code, 422, response.text)
