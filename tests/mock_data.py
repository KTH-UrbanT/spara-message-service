from typing import Dict, List, Any
from service.entrypoints import pwd_context

# ============================================
# USER MOCK DATA
# ============================================

MOCK_USER_REGULAR: Dict[str, Any] = {
    "user_id": 1,
    "username": "testuser",
    "email": "test@example.com",
    "password_hash": pwd_context.hash("password123"),
    "created_at": "2024-01-01T00:00:00",
    "last_logged_in": "2024-01-01T00:00:00",
}

MOCK_USER_TEMP: Dict[str, Any] = {
    "user_id": 2,
    "username": None,
    "email": None,
    "password_hash": None,
    "created_at": "2024-01-01T00:00:00",
    "last_logged_in": None,
}

MOCK_USER_3: Dict[str, Any] = {
    "user_id": 3,
    "username": "otheruser",
    "email": "other@example.com",
    "password_hash": pwd_context.hash("password123"),
    "created_at": "2024-01-01T00:00:00",
    "last_logged_in": "2024-01-01T00:00:00",
}


# List of all mock users for bulk operations
ALL_MOCK_USERS: List[Dict[str, Any]] = [
    MOCK_USER_REGULAR,
    MOCK_USER_TEMP,
    MOCK_USER_3,
]

# ============================================
# SESSION MOCK DATA
# ============================================

MOCK_SESSION: Dict[str, Any] = {
    "session_id": 100,
    "user_id": 1,
    "session_token": "test-session-token",
    "is_active": True,
    "created_at": "2024-01-01T00:00:00",
    "last_accessed": "2024-01-01T00:00:00",
}

MOCK_SESSION_2: Dict[str, Any] = {
    "session_id": 101,
    "user_id": 3,
    "session_token": "test-session-token-2",
    "is_active": True,
    "created_at": "2024-01-01T00:00:00",
    "last_accessed": "2024-01-01T00:00:00",
}

MOCK_SESSION_INACTIVE: Dict[str, Any] = {
    "session_id": 102,
    "user_id": 1,
    "session_token": "inactive-session-token",
    "is_active": False,
    "created_at": "2024-01-01T00:00:00",
    "last_accessed": "2024-01-01T00:00:00",
}

ALL_MOCK_SESSIONS: List[Dict[str, Any]] = [
    MOCK_SESSION,
    MOCK_SESSION_2,
    MOCK_SESSION_INACTIVE,
]

# ============================================
# MESSAGE MOCK DATA
# ============================================

MOCK_MESSAGE_USER: Dict[str, Any] = {
    "message_id": 1,
    "session_id": 100,
    "role": "user",
    "content": "Hello",
    "sent_at": "2024-01-01T00:00:00",
}

MOCK_MESSAGE_ASSISTANT: Dict[str, Any] = {
    "message_id": 2,
    "session_id": 100,
    "role": "assistant",
    "content": "Hi there!",
    "sent_at": "2024-01-01T00:00:01",
}

MOCK_MESSAGE_USER_2: Dict[str, Any] = {
    "message_id": 3,
    "session_id": 100,
    "role": "user",
    "content": "How are you?",
    "sent_at": "2024-01-01T00:00:02",
}

MOCK_MESSAGE_ASSISTANT_2: Dict[str, Any] = {
    "message_id": 4,
    "session_id": 100,
    "role": "assistant",
    "content": "I'm doing well, thank you!",
    "sent_at": "2024-01-01T00:00:03",
}

MOCK_MESSAGES: List[Dict[str, Any]] = [
    MOCK_MESSAGE_USER,
    MOCK_MESSAGE_ASSISTANT,
    MOCK_MESSAGE_USER_2,
    MOCK_MESSAGE_ASSISTANT_2,
]

# Messages for session 2
MOCK_MESSAGES_SESSION_2: List[Dict[str, Any]] = [
    {
        "message_id": 5,
        "session_id": 101,
        "role": "user",
        "content": "Different session message",
        "sent_at": "2024-01-01T00:00:00",
    },
]

# ============================================
# AUTHENTICATION MOCK DATA
# ============================================

MOCK_JWT_SECRET = "test-secret-key-12345"
MOCK_JWT_ALGORITHM = "HS256"
MOCK_JWT_EXPIRATION_MINUTES = 60
