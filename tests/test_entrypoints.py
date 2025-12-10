import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
import jwt

from service.entrypoints import router
from service.authorization import AuthorizationService

from tests.mock_data import (
    MOCK_USER_REGULAR,
    MOCK_USER_TEMP,
    MOCK_USER_3,
    MOCK_SESSION,
    MOCK_SESSION_INACTIVE,
    MOCK_MESSAGES,
)

# Create test app
app = FastAPI()
app.include_router(router)
client = TestClient(app)


# Helper to create valid JWT token
def create_test_token(user_id: int, email, temporary_user: bool):
    auth_service = AuthorizationService()
    return auth_service.create_token(
        user_id=user_id, email=email, temporary_user=temporary_user
    )


@pytest.fixture(autouse=True)
def mock_get_selected_user():
    """Mock get_selected_user function to avoid database calls"""
    with patch("service.authorization.get_selected_user") as mock:
        mock.return_value = MOCK_USER_REGULAR.copy()
        yield mock


# ============================================
# USER ENDPOINT TESTS - SUCCESS CASES
# ============================================


class TestUserEndpoints:

    @patch("service.entrypoints.get_users")
    def test_get_all_users_success(self, mock_get_users):
        """Test successful retrieval of all users"""
        mock_get_users.return_value = [MOCK_USER_REGULAR, MOCK_USER_TEMP, MOCK_USER_3]
        token = create_test_token(
            user_id=MOCK_USER_REGULAR["user_id"],
            email=MOCK_USER_REGULAR["email"],
            temporary_user=False,
        )

        response = client.get(
            "/users/",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        assert len(response.json()) == 3
        mock_get_users.assert_called_once()

    @patch("service.entrypoints.get_selected_user")
    def test_get_user_by_id_success(self, mock_get_selected_user):
        """Test successful retrieval of user by ID"""
        token = create_test_token(
            user_id=MOCK_USER_REGULAR["user_id"],
            email=MOCK_USER_REGULAR["email"],
            temporary_user=False,
        )

        mock_get_selected_user.return_value = MOCK_USER_REGULAR
        response = client.get("/user/1/", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200
        assert response.json()["user_id"] == 1
        assert response.json()["username"] == "testuser"
        assert response.json()["email"] == "test@example.com"
        assert response.json()["created_at"] == "2024-01-01T00:00:00"
        assert response.json()["last_logged_in"] == "2024-01-01T00:00:00"
        mock_get_selected_user.assert_called_once()

    @patch("service.entrypoints.get_selected_user")
    def test_login_success(self, mock_get_selected_user):
        """Test successful user login"""
        mock_get_selected_user.return_value = MOCK_USER_REGULAR

        response = client.post(
            "/user/login/",
            data={"username": "test@example.com", "password": "password123"},
        )

        assert response.status_code == 200
        assert "access_token" in response.json()
        assert response.json()["token_type"] == "bearer"
        assert response.json()["user_id"] == 1
        assert response.json()["username"] == "testuser"
        assert response.json()["email"] == "test@example.com"
        assert response.json()["temporary_user"] is False
        assert "password_hash" not in response.json()
        assert "password" not in response.json()
        mock_get_selected_user.assert_called_once()

    @patch("service.entrypoints.get_selected_user")
    def test_login_temporary_user_success(self, mock_get_selected_user):
        """Test successful temporary user login"""
        mock_get_selected_user.return_value = MOCK_USER_TEMP

        response = client.post("/user/login/temporary/", json={"temp_user_id": 2})

        assert response.status_code == 200
        assert "access_token" in response.json()
        assert response.json()["token_type"] == "bearer"
        assert response.json()["user_id"] == 2
        assert response.json()["temporary_user"] is True
        assert "username" not in response.json()
        assert "email" not in response.json()
        assert "password_hash" not in response.json()
        assert "password" not in response.json()
        mock_get_selected_user.assert_called_once()

    @patch("service.entrypoints.get_users")
    @patch("service.entrypoints.insert_user")
    @patch("service.entrypoints._get_password_hash")
    def test_register_success(
        self, mock_get_password_hash, mock_insert_user, mock_get_users
    ):
        """Test successful user registration"""
        mock_get_users.return_value = []
        mock_get_password_hash.return_value = "hashed_password"
        mock_insert_user.return_value = 5

        response = client.post(
            "/user/register/",
            json={
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "newpassword123",
            },
        )

        assert response.status_code == 200
        assert response.json()["user_id"] == 5
        assert "successfully" in response.json()["message"]
        mock_insert_user.assert_called_once()

    @patch("service.entrypoints.insert_empty_user")
    def test_register_temporary_user_success(self, mock_insert_empty_user):
        """Test successful temporary user registration"""
        mock_insert_empty_user.return_value = {
            "user_id": 10,
            "message": "Temporary user created",
        }

        response = client.post("/user/register/temporary/")

        assert response.status_code == 200
        assert response.json()["user_id"] == 10
        mock_insert_empty_user.assert_called_once()


# ============================================
# USER ENDPOINT TESTS - AUTHENTICATION ERRORS
# ============================================


class TestUserAuthenticationErrors:
    def test_get_all_users_no_token(self):
        """Test getting all users without authentication token"""
        response = client.get("/users/")
        assert response.status_code == 401

    def test_get_user_by_id_no_token(self):
        """Test getting user by ID without authentication token"""
        response = client.get("/user/1/")
        assert response.status_code == 401

    def test_get_user_by_id_invalid_token(self):
        """Test getting user by ID with invalid token"""
        response = client.get(
            "/user/1/", headers={"Authorization": "Bearer invalid_token"}
        )
        assert response.status_code == 401

    def test_get_user_by_id_expired_token(self):
        """Test getting user by ID with expired token"""
        auth_service = AuthorizationService()
        now = datetime.now(tz=timezone.utc)
        expire = now - timedelta(minutes=10)  # Expired 10 minutes ago

        payload = {
            "user_id": 1,
            "email": "test@example.com",
            "exp": expire,
            "temporary_user": False,
        }
        expired_token = jwt.encode(
            payload, auth_service.JWT_SECRET, algorithm=auth_service.JWT_ALGORITHM
        )

        response = client.get(
            "/user/1/", headers={"Authorization": f"Bearer {expired_token}"}
        )
        assert response.status_code == 401

    def test_get_user_by_id_forbidden_different_user(self, mock_get_selected_user):
        """Test getting user by ID with token of different user (forbidden)"""
        token = create_test_token(
            user_id=1, email="test@example.com", temporary_user=False
        )  # Token for user 1

        response = client.get(
            "/user/3/",  # Trying to access user 3
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 403
        assert "Forbidden" in response.json()["detail"]

    def test_get_all_users_temporary_user_forbidden(self):
        """Test that temporary users cannot access get all users endpoint"""
        token = create_test_token(
            user_id=2, email="", temporary_user=True
        )  # Temp user token

        response = client.get("/users/", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 403
        assert "Temporary users cannot access" in response.json()["detail"]

    @patch("service.entrypoints.get_selected_user")
    def test_login_wrong_password(self, mock_get_selected_user):
        """Test login with wrong password"""

        with patch("service.entrypoints._verify_password", return_value=False):
            response = client.post(
                "/user/login/",
                data={"username": "test@example.com", "password": "wrongpassword"},
            )

        assert response.status_code == 401
        assert "Incorrect email or password" in response.json()["detail"]

    @patch("service.entrypoints.get_selected_user")
    def test_login_user_not_found(self, mock_get_selected_user):
        """Test login with non-existent user"""
        mock_get_selected_user.side_effect = KeyError("User not found")

        response = client.post(
            "/user/login/",
            data={"username": "nonexistent@example.com", "password": "password123"},
        )

        assert response.status_code == 401
        assert "Incorrect email or password" in response.json()["detail"]

    @patch("service.entrypoints.get_selected_user")
    def test_login_with_temporary_user_forbidden(self, mock_get_selected_user):
        """Test regular login endpoint with temporary user (should fail)"""
        mock_get_selected_user.return_value = MOCK_USER_TEMP
        token = create_test_token(
            user_id=2, email="", temporary_user=True
        )  # Temp user token

        response = client.post(
            "/user/login/",
            data={"username": "tempuser", "password": "any_password"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 401
        assert "Incorrect email or password" in response.json()["detail"]

    @patch("service.entrypoints.get_selected_user")
    def test_login_temporary_user_with_credentials(self, mock_get_selected_user):
        """Test temporary login endpoint with regular user (should fail)"""
        mock_get_selected_user.return_value = MOCK_USER_REGULAR  # Has credentials

        response = client.post("/user/login/temporary/", json={"temp_user_id": 1})

        assert response.status_code == 403
        assert "regular user account" in response.json()["detail"]

    @patch("service.entrypoints.get_selected_user")
    def test_login_temporary_user_not_found(self, mock_get_selected_user):
        """Test temporary login with non-existent user"""
        mock_get_selected_user.side_effect = KeyError("User not found")

        response = client.post("/user/login/temporary/", json={"temp_user_id": 999})

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    @patch("service.entrypoints.get_users")
    def test_register_duplicate_email(self, mock_get_users):
        """Test registration with already registered email"""
        mock_get_users.return_value = [MOCK_USER_REGULAR]

        response = client.post(
            "/user/register/",
            json={
                "username": "newuser",
                "email": "test@example.com",  # Already exists
                "password": "newpassword123",
            },
        )

        assert response.status_code == 400
        assert "already registered" in response.json()["detail"]


# ============================================
# SESSION ENDPOINT TESTS - SUCCESS CASES
# ============================================


class TestSessionEndpoints:
    @patch("service.entrypoints.get_selected_session")
    def test_get_session_by_user_id_success(self, mock_get_selected_session):
        """Test successful retrieval of sessions by user ID"""
        mock_get_selected_session.return_value = [MOCK_SESSION, MOCK_SESSION_INACTIVE]
        token = create_test_token(
            user_id=1, email="test@example.com", temporary_user=False
        )

        response = client.get(
            "/session/1/", headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        assert len(response.json()) == 2
        assert response.json()[0]["session_id"] == 100
        assert response.json()[1]["session_id"] == 102
        mock_get_selected_session.assert_called_once()

    @patch("service.entrypoints.insert_session")
    def test_create_session_success(self, mock_insert_session):
        """Test successful session creation"""
        mock_insert_session.return_value = 103
        token = create_test_token(
            user_id=1, email="test@example.com", temporary_user=False
        )

        response = client.post(
            "/session/",
            params={
                "user_id": 1,
                "session_token": "new-session-token",
                "is_active": True,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        assert response.json() == 103
        mock_insert_session.assert_called_once()


# ============================================
# SESSION ENDPOINT TESTS - AUTHENTICATION ERRORS
# ============================================


class TestSessionAuthenticationErrors:
    def test_create_session_forbidden_different_user(self):
        """Test creating session for different user (forbidden)"""
        token = create_test_token(
            user_id=1, email="test@example.com", temporary_user=False
        )

        response = client.post(
            "/session/",
            params={
                "user_id": 3,  # Trying to create session for user 3
                "session_token": "new-session-token",
                "is_active": True,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 403
        assert "Forbidden" in response.json()["detail"]

    @patch("service.entrypoints.get_selected_session")
    def test_get_session_forbidden_different_user(self, mock_get_selected_session):
        """Test getting session for different user (forbidden)"""
        mock_get_selected_session.return_value = [
            {"session_id": 200, "user_id": 3}
        ]  # Session owned by user 3
        token = create_test_token(
            user_id=1, email="test@example.com", temporary_user=False
        )  # Token for user 1

        response = client.get(
            "/session/3/",  # Trying to access sessions for user 3
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 403
        assert "Forbidden" in response.json()["detail"]


# ============================================
# MESSAGE ENDPOINT TESTS - SUCCESS CASES
# ============================================


class TestMessageEndpoints:
    @patch("service.entrypoints.get_selected_session")
    @patch("service.entrypoints.get_selected_messages")
    def test_get_messages_by_session_id_success(
        self, mock_get_selected_messages, mock_get_selected_session
    ):
        """Test successful retrieval of messages by session ID"""
        mock_get_selected_session.return_value = [MOCK_SESSION]
        mock_get_selected_messages.return_value = MOCK_MESSAGES
        token = create_test_token(
            user_id=1, email="test@example.com", temporary_user=False
        )

        response = client.get(
            "/messages/100/", headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        assert len(response.json()) == 4
        assert response.json()[0]["message_id"] == 1
        assert response.json()[1]["message_id"] == 2
        assert response.json()[2]["message_id"] == 3
        assert response.json()[3]["message_id"] == 4
        mock_get_selected_session.assert_called_once()
        mock_get_selected_messages.assert_called_once()

    @patch("service.entrypoints.get_selected_session")
    @patch("service.entrypoints.insert_messages")
    def test_create_message_success(
        self, mock_insert_messages, mock_get_selected_session
    ):
        """Test successful message creation"""
        mock_get_selected_session.return_value = [MOCK_SESSION]
        mock_insert_messages.return_value = None
        token = create_test_token(
            user_id=1, email="test@example.com", temporary_user=False
        )

        response = client.post(
            "/messages/",
            json=[
                {
                    "session_id": 100,
                    "role": "user",
                    "content": "Test message",
                    "sent_at": "2024-01-01T00:00:00",
                }
            ],
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        mock_insert_messages.assert_called_once()


# ============================================
# MESSAGE ENDPOINT TESTS - AUTHENTICATION ERRORS
# ============================================


class TestMessageAuthenticationErrors:
    @patch("service.entrypoints.get_selected_session")
    def test_get_messages_forbidden_different_user(self, mock_get_selected_session):
        """Test getting messages for session owned by different user"""
        mock_get_selected_session.return_value = [
            {"session_id": 100, "user_id": 3}
        ]  # Session owned by user 3
        token = create_test_token(
            user_id=1, email="test@example.com", temporary_user=False
        )  # Token for user 1

        response = client.get(
            "/messages/100/", headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403
        assert "Forbidden" in response.json()["detail"]

    @patch("service.entrypoints.get_selected_session")
    def test_get_messages_session_not_found(self, mock_get_selected_session):
        """Test getting messages for non-existent session"""
        mock_get_selected_session.return_value = []
        token = create_test_token(
            user_id=1, email="test@example.com", temporary_user=False
        )

        response = client.get(
            "/messages/999/", headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    @patch("service.entrypoints.get_selected_session")
    def test_get_messages_session_not_found(self, mock_get_selected_session):
        """Test getting messages for non-existent session"""
        mock_get_selected_session.return_value = []
        token = create_test_token(
            user_id=1, email="test@example.com", temporary_user=False
        )

        response = client.get(
            "/messages/999/", headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    @patch("service.entrypoints.get_selected_session")
    def test_create_message_session_not_found(self, mock_get_selected_session):
        """Test creating message for non-existent session"""
        mock_get_selected_session.return_value = []
        token = create_test_token(
            user_id=1, email="test@example.com", temporary_user=False
        )

        response = client.post(
            "/messages/",
            json=[
                {
                    "session_id": 999,
                    "role": "user",
                    "content": "Test message",
                    "sent_at": "2024-01-01T00:00:00",
                }
            ],
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    @patch("service.entrypoints.get_selected_session")
    def test_create_message_forbidden_different_user(self, mock_get_selected_session):
        """Test creating message for session owned by different user"""
        mock_get_selected_session.return_value = [
            {"session_id": 100, "user_id": 3}
        ]  # Session owned by user 3
        token = create_test_token(
            user_id=1, email="test@example.com", temporary_user=False
        )  # Token for user 1

        response = client.post(
            "/messages/",
            json=[
                {
                    "session_id": 100,
                    "role": "user",
                    "content": "Test message",
                    "sent_at": "2024-01-01T00:00:00",
                }
            ],
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 403
        assert "Forbidden" in response.json()["detail"]


# ============================================
# RATING ENDPOINT TESTS - SUCCESS CASES
# ============================================


class TestRatingEndpoints:
    @patch("service.entrypoints.get_selected_session")
    @patch("service.entrypoints.get_selected_messages")
    @patch("service.entrypoints.check_rating_exists")
    @patch("service.entrypoints.insert_rating")
    def test_send_rating_success(
        self,
        mock_insert_rating,
        mock_check_rating_exists,
        mock_get_selected_messages,
        mock_get_selected_session,
    ):
        """Test successful rating submission"""
        mock_get_selected_session.return_value = [MOCK_SESSION]
        mock_get_selected_messages.return_value = MOCK_MESSAGES
        mock_check_rating_exists.return_value = None
        mock_insert_rating.return_value = 1
        token = create_test_token(
            user_id=1, email="test@example.com", temporary_user=False
        )  # Token for user 1

        response = client.post(
            "/rating/",
            json={
                "userId": 1,
                "rating": 4.5,
                "message": "Hi there!",
                "sessionIdInt": 100,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        assert response.json()["rating_id"] == 1
        assert response.json()["message_id"] == 2
        mock_insert_rating.assert_called_once()

    @patch("service.entrypoints.get_selected_session")
    @patch("service.entrypoints.get_selected_messages")
    @patch("service.entrypoints.check_rating_exists")
    @patch("service.entrypoints.update_rating")
    def test_update_rating_success(
        self,
        mock_update_rating,
        mock_check_rating_exists,
        mock_get_selected_messages,
        mock_get_selected_session,
    ):
        """Test successful rating update when rating already exists"""
        mock_get_selected_session.return_value = [MOCK_SESSION]
        mock_get_selected_messages.return_value = MOCK_MESSAGES
        mock_check_rating_exists.return_value = 5
        token = create_test_token(
            user_id=1, email="test@example.com", temporary_user=False
        )  # Token for user 1

        response = client.post(
            "/rating/",
            json={
                "userId": 1,
                "rating": 5.0,
                "message": "Hi there!",
                "sessionIdInt": 100,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        assert response.json()["rating_id"] == 5
        assert response.json()["message_id"] == 2
        mock_update_rating.assert_called_once()


# ============================================
# RATING ENDPOINT TESTS - AUTHENTICATION ERRORS
# ============================================


class TestRatingAuthenticationErrors:
    def test_send_rating_forbidden_different_user(self):
        """Test sending rating for different user (forbidden)"""
        token = create_test_token(
            user_id=1, email="test@example.com", temporary_user=False
        )  # Token for user 1

        response = client.post(
            "/rating/",
            json={
                "userId": 3,  # Trying to rate for user 3
                "rating": 4.5,
                "message": "Hi there!",
                "sessionIdInt": 100,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 403
        assert "Forbidden" in response.json()["detail"]

    @patch("service.entrypoints.get_selected_session")
    @patch("service.entrypoints.get_selected_messages")
    def test_send_rating_message_not_found(
        self, mock_get_selected_messages, mock_get_selected_session
    ):
        """Test sending rating for non-existent message"""
        mock_get_selected_session.return_value = [MOCK_SESSION]
        mock_get_selected_messages.return_value = MOCK_MESSAGES
        token = create_test_token(
            user_id=1, email="test@example.com", temporary_user=False
        )  # Token for user 1

        response = client.post(
            "/rating/",
            json={
                "userId": 1,
                "rating": 4.5,
                "message": "Non-existent message content",
                "sessionIdInt": 100,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404
        assert "Message not found" in response.json()["detail"]
