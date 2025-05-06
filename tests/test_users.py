# submodules/message-service/tests/test_register.py

import pytest
from httpx import AsyncClient
from socket_manager import app  # Adjust if your FastAPI app is imported from another path

@pytest.mark.asyncio
async def test_user_register():
    async with AsyncClient(app=app, base_url="http://test") as client:
        payload = {
            "username": "testuser",
            "email": "testuser@example.com",
            "password": "supersecurepassword"
        }

        response = await client.post("/user/register/", json=payload)

        assert response.status_code == 200  # or 201 if that's what your API returns
        data = response.json()
        assert "email" in data
        assert data["email"] == "testuser@example.com"
