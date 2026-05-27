import pytest
import base64
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
        assert response.json()["email"] == "temporary@example.com"
        assert response.json()["username"] is None
        assert response.json()["temporary_user"] is True
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

    @patch("service.entrypoints.get_selected_user")
    @patch("service.entrypoints.insert_temporary_user")
    def test_register_temporary_user_success(self, mock_insert_temporary_user, mock_get_selected_user):
        """Test successful temporary user registration"""
        mock_get_selected_user.side_effect = KeyError("User not found")
        mock_insert_temporary_user.return_value = 10

        response = client.post(
            "/user/register/temporary/",
            json={"email": "Temporary@Example.com"},
        )

        assert response.status_code == 200
        assert response.json()["user_id"] == 10
        assert response.json()["email"] == "temporary@example.com"
        mock_insert_temporary_user.assert_called_once_with(email="temporary@example.com")

    @patch("service.entrypoints.get_selected_user")
    @patch("service.entrypoints.insert_temporary_user")
    def test_register_temporary_user_reuses_existing_temporary_user(
        self, mock_insert_temporary_user, mock_get_selected_user
    ):
        """Test continue-with-email reuses an existing email-backed temporary user."""
        mock_get_selected_user.return_value = MOCK_USER_TEMP

        response = client.post(
            "/user/register/temporary/",
            json={"email": "Temporary@Example.com"},
        )

        assert response.status_code == 200
        assert response.json()["user_id"] == 2
        assert response.json()["email"] == "temporary@example.com"
        assert "loaded" in response.json()["message"]
        mock_insert_temporary_user.assert_not_called()

    @patch("service.entrypoints.get_selected_user")
    @patch("service.entrypoints.insert_temporary_user")
    def test_register_temporary_user_rejects_registered_email(
        self, mock_insert_temporary_user, mock_get_selected_user
    ):
        """Test continue-with-email does not bypass password login."""
        mock_get_selected_user.return_value = MOCK_USER_REGULAR

        response = client.post(
            "/user/register/temporary/",
            json={"email": "test@example.com"},
        )

        assert response.status_code == 400
        assert "Please log in" in response.json()["detail"]
        mock_insert_temporary_user.assert_not_called()


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
            user_id=2, email="temporary@example.com", temporary_user=True
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
            user_id=2, email="temporary@example.com", temporary_user=True
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

    @patch("service.entrypoints.update_session")
    @patch("service.entrypoints.get_selected_session")
    def test_update_session_active_state_success(
        self, mock_get_selected_session, mock_update_session
    ):
        """Test deactivating and reactivating a session owned by the user."""
        mock_get_selected_session.return_value = [MOCK_SESSION]
        token = create_test_token(
            user_id=1, email="test@example.com", temporary_user=False
        )

        response = client.patch(
            "/session/100/active/",
            params={"is_active": False},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        assert response.json()["session_id"] == 100
        assert response.json()["is_active"] is False
        mock_update_session.assert_called_once()

    @patch("service.entrypoints.get_selected_session")
    def test_update_session_active_state_forbidden_for_other_user(
        self, mock_get_selected_session
    ):
        """Test changing another user's session is forbidden."""
        mock_get_selected_session.return_value = [
            {"session_id": 200, "user_id": 3, "is_active": True}
        ]
        token = create_test_token(
            user_id=1, email="test@example.com", temporary_user=False
        )

        response = client.patch(
            "/session/200/active/",
            params={"is_active": False},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 403
        assert "Forbidden" in response.json()["detail"]


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
    @patch("service.entrypoints.get_selected_messages")
    def test_get_messages_by_session_id_includes_optional_rating(
        self, mock_get_selected_messages, mock_get_selected_session
    ):
        """Test message retrieval preserves rating fields when present."""
        mock_get_selected_session.return_value = [MOCK_SESSION]
        mock_get_selected_messages.return_value = [
            {
                "message_id": 2,
                "session_id": 100,
                "role": "assistant",
                "content": "Hi there!",
                "sent_at": "2024-01-01T00:00:01",
                "rating_id": 8,
                "rating": 4.5,
                "version": "GROUP-A",
            },
            {
                "message_id": 3,
                "session_id": 100,
                "role": "assistant",
                "content": "Unrated reply",
                "sent_at": "2024-01-01T00:00:02",
                "rating_id": None,
                "rating": None,
                "version": None,
            },
        ]
        token = create_test_token(
            user_id=1, email="test@example.com", temporary_user=False
        )

        response = client.get(
            "/messages/100/", headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        assert response.json()[0]["rating"] == 4.5
        assert response.json()[0]["rating_id"] == 8
        assert response.json()[1]["rating"] is None
        assert response.json()[1]["version"] is None

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


class TestReportEndpoints:
    @patch("service.entrypoints.get_selected_session")
    @patch("service.entrypoints.get_report_payload")
    def test_download_report_success(
        self, mock_get_report_payload, mock_get_selected_session
    ):
        mock_get_report_payload.return_value = {
            "thread_id": "session-token-1",
            "file_name": "draft_report.txt",
            "mime_type": "text/plain; charset=utf-8",
            "content": "# Draft",
        }
        mock_get_selected_session.return_value = [
            {"session_id": 100, "user_id": 1, "session_token": "session-token-1"}
        ]
        token = create_test_token(
            user_id=1, email="test@example.com", temporary_user=False
        )

        response = client.get(
            "/reports/report-1/download/",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        assert response.text == "# Draft"
        assert response.headers["content-disposition"] == 'attachment; filename="draft_report.txt"'
        assert response.headers["content-type"].startswith("text/plain")

    @patch("service.entrypoints.get_selected_session")
    @patch("service.entrypoints.get_report_payload")
    def test_download_pdf_report_success(
        self, mock_get_report_payload, mock_get_selected_session
    ):
        pdf_bytes = b"%PDF-1.4\nfake"
        mock_get_report_payload.return_value = {
            "thread_id": "session-token-1",
            "file_name": "BUILDING-1.pdf",
            "mime_type": "application/pdf",
            "content_base64": base64.b64encode(pdf_bytes).decode("ascii"),
            "content_encoding": "base64",
        }
        mock_get_selected_session.return_value = [
            {"session_id": 100, "user_id": 1, "session_token": "session-token-1"}
        ]
        token = create_test_token(
            user_id=1, email="test@example.com", temporary_user=False
        )

        response = client.get(
            "/reports/report-2/download/",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        assert response.content == pdf_bytes
        assert response.headers["content-type"].startswith("application/pdf")
        assert response.headers["content-disposition"] == 'attachment; filename="BUILDING-1.pdf"'

    @patch("service.entrypoints.get_report_payload")
    def test_download_report_not_found(self, mock_get_report_payload):
        mock_get_report_payload.return_value = None
        token = create_test_token(
            user_id=1, email="test@example.com", temporary_user=False
        )

        response = client.get(
            "/reports/missing/download/",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404
        assert "expired" in response.json()["detail"]


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


class TestEvaluationEndpoints:
    @patch("service.entrypoints.upsert_advisor_review")
    def test_save_advisor_review_with_corrections_success(self, mock_upsert_advisor_review):
        mock_upsert_advisor_review.return_value = {
            "advisor_review_id": 7,
            "message_id": 22,
            "reviewer_user_id": 1,
            "updated_at": "2026-05-19T12:00:00",
        }
        token = create_test_token(
            user_id=1, email="test@example.com", temporary_user=False
        )

        response = client.post(
            "/evaluation/advisor-review/",
            json={
                "message_id": 22,
                "route_correct": True,
                "error_tags": ["generation", "unsupported_claim"],
                "correction_actions": [
                    {"type": "remove_unsupported_claim", "field": "recommendation"}
                ],
                "corrected_answer": "Use general advice until the building data is confirmed.",
                "correction_summary": "Removed a claim that was not supported by retrieved evidence.",
                "comments": "Needs a clearer source citation.",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        assert response.json()["advisor_review_id"] == 7
        mock_upsert_advisor_review.assert_called_once()
        call_kwargs = mock_upsert_advisor_review.call_args.kwargs
        assert call_kwargs["message_id"] == 22
        assert call_kwargs["reviewer_user_id"] == 1
        assert call_kwargs["review"]["correction_actions"] == [
            {"type": "remove_unsupported_claim", "field": "recommendation"}
        ]
        assert call_kwargs["review"]["corrected_answer"] == (
            "Use general advice until the building data is confirmed."
        )
        assert call_kwargs["review"]["correction_summary"] == (
            "Removed a claim that was not supported by retrieved evidence."
        )

    @patch("service.entrypoints.upsert_advisor_review")
    def test_save_advisor_review_forbidden_for_temporary_user(self, mock_upsert_advisor_review):
        token = create_test_token(
            user_id=2, email="temporary@example.com", temporary_user=True
        )

        response = client.post(
            "/evaluation/advisor-review/",
            json={"message_id": 22, "comments": "temporary user cannot review"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 403
        assert "Temporary users cannot submit advisor reviews" in response.json()["detail"]
        mock_upsert_advisor_review.assert_not_called()
