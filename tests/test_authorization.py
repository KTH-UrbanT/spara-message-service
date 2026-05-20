# tests/test_authorization.py
from datetime import datetime, timedelta, timezone
import pytest
from unittest.mock import patch
from fastapi import HTTPException
import jwt

from service.authorization import AuthorizationService
from tests.mock_data import (
    MOCK_USER_REGULAR,
    MOCK_USER_TEMP,
    MOCK_JWT_SECRET,
    MOCK_JWT_ALGORITHM,
    MOCK_JWT_EXPIRATION_MINUTES,
)


@pytest.fixture
def auth_service():
    """Provide a fresh AuthorizationService instance for each test"""
    auth_service = AuthorizationService()
    auth_service.JWT_SECRET = MOCK_JWT_SECRET
    auth_service.JWT_ALGORITHM = MOCK_JWT_ALGORITHM
    auth_service.JWT_EXPIRATION_TIME = MOCK_JWT_EXPIRATION_MINUTES
    return auth_service


# ============================================
# TOKEN CREATION TESTS
# ============================================


class TestCreateToken:
    def test_create_token_regular_user(self, auth_service):
        """Test creating a token for a regular user"""
        token = auth_service.create_token(
            MOCK_USER_REGULAR["user_id"], MOCK_USER_REGULAR["email"], False
        )

        # Verify token is a string
        assert isinstance(token, str)
        assert len(token) > 0

        # Decode and verify payload
        payload = jwt.decode(
            token, auth_service.JWT_SECRET, algorithms=[auth_service.JWT_ALGORITHM]
        )

        assert payload["user_id"] == 1
        assert payload["email"] == "test@example.com"
        assert payload["temporary_user"] == False
        assert payload["exp"] is not None

    def test_create_token_temporary_user(self, auth_service):
        """Test creating a token for a temporary user"""
        token = auth_service.create_token(
            MOCK_USER_TEMP["user_id"], MOCK_USER_TEMP["email"], True
        )

        payload = jwt.decode(
            token, auth_service.JWT_SECRET, algorithms=[auth_service.JWT_ALGORITHM]
        )
        assert payload["user_id"] == 2
        assert payload["email"] == "temporary@example.com"
        assert payload["temporary_user"] is True

    def test_create_token_has_expiration(self, auth_service):
        """Test that token has correct expiration time"""
        token = auth_service.create_token(
            MOCK_USER_REGULAR["user_id"], MOCK_USER_REGULAR["email"], False
        )

        payload = jwt.decode(
            token, auth_service.JWT_SECRET, algorithms=[auth_service.JWT_ALGORITHM]
        )

        # Check expiration is in the future
        exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        now = datetime.now(tz=timezone.utc)

        # Should expire in approximately 60 minutes (allow 1 minute tolerance)
        time_diff = (exp_time - now).total_seconds()
        assert 59 * 60 <= time_diff <= 61 * 60


# ============================================
# TOKEN DECODING TESTS
# ============================================


class TestDecodeToken:
    def test_decode_valid_token(self, auth_service):
        """Test decoding a valid token"""
        token = auth_service.create_token(
            MOCK_USER_REGULAR["user_id"], MOCK_USER_REGULAR["email"], False
        )

        decoded = auth_service.decode_token(token)

        assert decoded["user_id"] == 1
        assert decoded["email"] == "test@example.com"
        assert "exp" in decoded

    def test_decode_expired_token(self, auth_service):
        """Test decoding an expired token raises HTTPException"""
        # Create a token that expired 1 hours ago
        now = datetime.now(tz=timezone.utc)
        expired_time = now - timedelta(hours=1)

        payload = {
            "user_id": MOCK_USER_REGULAR["user_id"],
            "email": MOCK_USER_REGULAR["email"],
            "exp": expired_time,
            "temporary_user": False,
        }
        expired_token = jwt.encode(
            payload, auth_service.JWT_SECRET, algorithm=auth_service.JWT_ALGORITHM
        )

        with pytest.raises(HTTPException) as exc_info:
            auth_service.decode_token(expired_token)

        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    def test_decode_invalid_token(self, auth_service):
        """Test decoding an invalid token raises HTTPException"""
        invalid_token = "invalid.token.string"

        with pytest.raises(HTTPException) as exc_info:
            auth_service.decode_token(invalid_token)

        assert exc_info.value.status_code == 401
        assert "invalid" in exc_info.value.detail.lower()


# ============================================
# GET TOKEN DATA TESTS (Dependency)
# ============================================


class TestGetTokenData:
    @pytest.mark.asyncio
    @patch("service.authorization.get_selected_user")
    async def test_get_token_data_success(self, mock_get_selected_user, auth_service):
        """Test successfully getting token data with valid token"""
        mock_get_selected_user.return_value = MOCK_USER_REGULAR

        token = auth_service.create_token(
            user_id=MOCK_USER_REGULAR["user_id"],
            email=MOCK_USER_REGULAR["email"],
            temporary_user=False,
        )

        result = await auth_service.get_token_data(token)

        assert result["user_id"] == 1
        assert result["email"] == "test@example.com"
        assert result["temporary_user"] is False
        mock_get_selected_user.assert_called_once_with(
            column_name="user_id", filter_value=1
        )

    @pytest.mark.asyncio
    @patch("service.authorization.get_selected_user")
    async def test_get_token_data_temporary_user(
        self, mock_get_selected_user, auth_service
    ):
        """Test getting token data for temporary user"""
        mock_get_selected_user.return_value = MOCK_USER_TEMP

        token = auth_service.create_token(
            user_id=MOCK_USER_TEMP["user_id"],
            email=MOCK_USER_TEMP["email"],
            temporary_user=True,
        )

        result = await auth_service.get_token_data(token)

        assert result["user_id"] == 2
        assert result["temporary_user"] is True

    @pytest.mark.asyncio
    @patch("service.authorization.get_selected_user")
    async def test_get_token_data_user_not_found(
        self, mock_get_selected_user, auth_service
    ):
        """Test get_token_data when user doesn't exist in database"""
        mock_get_selected_user.side_effect = KeyError(
            "User not found for given filters."
        )

        token = auth_service.create_token(
            user_id=999, email="notfound@example.com", temporary_user=False
        )

        with pytest.raises(HTTPException) as exc_info:
            await auth_service.get_token_data(token)

        assert exc_info.value.status_code == 401
        assert "user not found" in exc_info.value.detail.lower()
