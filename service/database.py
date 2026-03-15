from dataclasses import dataclass
from typing import Any
import os

import psycopg2
from psycopg2 import sql


@dataclass
class User:
    user_id: int
    username: str
    email: str
    password: str
    created_at: str
    last_logged_in: str


@dataclass
class Session:
    session_id: int
    user_id: int
    session_token: str
    is_active: bool
    created_at: str
    last_accessed: str


@dataclass
class Message:
    message_id: int
    session_id: int
    role: str
    content: str
    sent_at: str


ALLOWED_USER_COLUMNS = {"user_id", "username", "email"}
ALLOWED_SESSION_COLUMNS = {"session_id", "user_id"}
ALLOWED_MESSAGE_COLUMNS = {"message_id", "session_id", "sender_id"}
VALID_MESSAGE_ROLES = {"user", "assistant", "system"}


def get_connection():
    return psycopg2.connect(
        host=os.environ["SQL_DB_HOST"].strip(),
        dbname=os.environ["SQL_DB_NAME"].strip(),
        user=os.environ["SQL_DB_USER"].strip(),
        password=os.environ["SQL_DB_PASSWORD"],
        port=os.environ["SQL_DB_PORT"].strip(),
        connect_timeout=5,
    )


def _close_safely(cursor=None, connection=None):
    if cursor is not None:
        cursor.close()
    if connection is not None:
        connection.close()


def insert_user(username: str, email: str, password: str) -> int:
    """Insert a new user into the users table and return user_id."""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO users (username, email, password_hash, created_at)
            VALUES (%s, %s, %s, NOW())
            RETURNING user_id;
            """,
            (username, email, password),
        )
        user_id = cursor.fetchone()[0]
        connection.commit()
        return user_id
    except Exception:
        if connection is not None:
            connection.rollback()
        raise
    finally:
        _close_safely(cursor, connection)


def insert_empty_user() -> int:
    """Insert a new temporary user and return user_id."""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO users (created_at, last_logged_in)
            VALUES (NOW(), NOW())
            RETURNING user_id;
            """
        )
        result = cursor.fetchone()
        connection.commit()
        if not result:
            raise RuntimeError("Failed to create temporary user.")
        return result[0]
    except Exception:
        if connection is not None:
            connection.rollback()
        raise
    finally:
        _close_safely(cursor, connection)


def get_users(filter: str = "all") -> list[User]:
    """Select users from the users table."""
    connection = None
    cursor = None
    try:
        if filter not in {"all", "regular", "temporary"}:
            raise ValueError("Invalid filter type. Use 'all', 'regular', or 'temporary'.")

        connection = get_connection()
        cursor = connection.cursor()

        if filter == "regular":
            query = """
                SELECT user_id, username, email, created_at, last_logged_in
                FROM users
                WHERE username IS NOT NULL AND email IS NOT NULL;
            """
        elif filter == "temporary":
            query = """
                SELECT user_id, username, email, created_at, last_logged_in
                FROM users
                WHERE username IS NULL OR email IS NULL;
            """
        else:
            query = """
                SELECT user_id, username, email, created_at, last_logged_in
                FROM users;
            """

        cursor.execute(query)
        users = cursor.fetchall()

        return [
            {
                "user_id": user[0],
                "username": user[1],
                "email": user[2],
                "created_at": user[3],
                "last_logged_in": user[4],
            }
            for user in users
        ]
    finally:
        _close_safely(cursor, connection)


def get_selected_user(
    column_name: str, filter_value: str | int, include_password: bool = False
) -> User:
    """Select a single user filtered by a validated column name."""
    connection = None
    cursor = None
    try:
        if column_name not in ALLOWED_USER_COLUMNS:
            raise ValueError("Invalid column name.")

        if column_name == "user_id" and not isinstance(filter_value, int):
            raise TypeError("'filter_value' should be 'int' for user_id column name.")

        if column_name in {"username", "email"} and not isinstance(filter_value, str):
            raise TypeError("'filter_value' should be 'str' for username and email column name.")

        connection = get_connection()
        cursor = connection.cursor()
        query = sql.SQL(
            """
            SELECT user_id, username, email, password_hash, created_at, last_logged_in
            FROM users
            WHERE {column} = %s;
            """
        ).format(column=sql.Identifier(column_name))

        cursor.execute(query, (filter_value,))
        user_row = cursor.fetchone()

        if not user_row:
            raise KeyError("User not found for given filters.")

        user_dict = {
            "user_id": user_row[0],
            "username": user_row[1],
            "email": user_row[2],
            "created_at": user_row[4],
            "last_logged_in": user_row[5],
        }

        if include_password:
            user_dict["password_hash"] = user_row[3]

        return user_dict
    finally:
        _close_safely(cursor, connection)


def update_user(user_id: int, username: str, email: str, password: str):
    """Update a temporary user into a regular user."""
    connection = None
    cursor = None
    try:
        selected_user = get_selected_user(
            column_name="user_id", filter_value=user_id, include_password=True
        )

        if selected_user["username"] is not None or selected_user["email"] is not None:
            raise ValueError("Cannot update a regular user to another regular user.")

        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            UPDATE users
            SET username = %s,
                email = %s,
                password_hash = %s,
                last_logged_in = NOW()
            WHERE user_id = %s;
            """,
            (username, email, password, user_id),
        )
        connection.commit()
    except Exception:
        if connection is not None:
            connection.rollback()
        raise
    finally:
        _close_safely(cursor, connection)


def insert_session(user_id: int, session_token: str, is_active: bool) -> int:
    """Insert a new session and return session_id."""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO sessions (user_id, session_token, is_active, created_at, last_accessed)
            VALUES (%s, %s, %s, NOW(), NOW())
            RETURNING session_id;
            """,
            (user_id, session_token, is_active),
        )
        session_id = cursor.fetchone()[0]
        connection.commit()
        return session_id
    except Exception:
        if connection is not None:
            connection.rollback()
        raise
    finally:
        _close_safely(cursor, connection)


def update_session(session_id: int, last_access_time: str, is_active: bool):
    """Update the session with the given session_id."""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            UPDATE sessions
            SET last_accessed = %s,
                is_active = %s
            WHERE session_id = %s;
            """,
            (last_access_time, is_active, session_id),
        )
        connection.commit()
    except Exception:
        if connection is not None:
            connection.rollback()
        raise
    finally:
        _close_safely(cursor, connection)


def get_selected_session(
    column_name: str, filter_value: int, filter_is_active: bool = False
) -> list[Session]:
    """Select sessions filtered by a validated column name."""
    connection = None
    cursor = None
    try:
        if column_name not in ALLOWED_SESSION_COLUMNS:
            raise ValueError("Invalid column name.")

        connection = get_connection()
        cursor = connection.cursor()

        if filter_is_active:
            query = sql.SQL(
                """
                SELECT session_id, user_id, session_token, is_active, created_at, last_accessed
                FROM sessions
                WHERE {column} = %s AND is_active = TRUE;
                """
            ).format(column=sql.Identifier(column_name))
            params = (filter_value,)
        else:
            query = sql.SQL(
                """
                SELECT session_id, user_id, session_token, is_active, created_at, last_accessed
                FROM sessions
                WHERE {column} = %s;
                """
            ).format(column=sql.Identifier(column_name))
            params = (filter_value,)

        cursor.execute(query, params)
        session_rows = cursor.fetchall()

        return [
            {
                "session_id": session[0],
                "user_id": session[1],
                "session_token": session[2],
                "is_active": session[3],
                "created_at": session[4],
                "last_accessed": session[5],
            }
            for session in session_rows
        ]
    finally:
        _close_safely(cursor, connection)


def get_all_sessions() -> list[Session]:
    """Select all rows from the sessions table."""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT session_id, user_id, session_token, is_active, last_accessed
            FROM sessions;
            """
        )
        sessions = cursor.fetchall()

        return [
            {
                "session_id": session[0],
                "user_id": session[1],
                "session_token": session[2],
                "is_active": session[3],
                "last_accessed": session[4],
            }
            for session in sessions
        ]
    finally:
        _close_safely(cursor, connection)


def get_selected_messages(column_name: str, filter_value: int) -> list[Message]:
    """Select messages filtered by a validated column name."""
    connection = None
    cursor = None
    try:
        if column_name not in ALLOWED_MESSAGE_COLUMNS:
            raise ValueError("Invalid column name.")

        connection = get_connection()
        cursor = connection.cursor()
        query = sql.SQL(
            """
            SELECT message_id, session_id, role, content, sent_at
            FROM messages
            WHERE {column} = %s;
            """
        ).format(column=sql.Identifier(column_name))
        cursor.execute(query, (filter_value,))
        message_rows = cursor.fetchall()

        return [
            {
                "message_id": message[0],
                "session_id": message[1],
                "role": message[2],
                "content": message[3],
                "sent_at": message[4],
            }
            for message in message_rows
        ]
    finally:
        _close_safely(cursor, connection)


def insert_messages(messages: list[dict]):
    """Insert multiple messages into the messages table."""
    connection = None
    cursor = None
    if not messages:
        raise ValueError("Messages list is empty.")

    invalid_roles = [m["role"] for m in messages if m["role"] not in VALID_MESSAGE_ROLES]
    if invalid_roles:
        raise ValueError(
            "Invalid role type in messages list. Valid roles are 'user', 'assistant', 'system'."
        )

    try:
        connection = get_connection()
        cursor = connection.cursor()
        insert_query = """
            INSERT INTO messages (session_id, role, content, sent_at)
            VALUES (%s, %s, %s, %s)
            RETURNING message_id;
        """
        data = [
            (msg["session_id"], msg["role"], msg["content"], msg["sent_at"])
            for msg in messages
        ]
        cursor.executemany(insert_query, data)
        connection.commit()
        return
    except Exception:
        if connection is not None:
            connection.rollback()
        raise
    finally:
        _close_safely(cursor, connection)


def insert_rating(user_id, rating, message, version):
    connection = None
    cursor = None
    user_id_value: Any = None if user_id == 1 else user_id

    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO ratings (user_id, rating, message, version)
            VALUES (%s, %s, %s, %s)
            RETURNING rating_id;
            """,
            (user_id_value, rating, message, version),
        )
        rating_id = cursor.fetchone()[0]
        connection.commit()
        return rating_id
    except Exception:
        if connection is not None:
            connection.rollback()
        raise
    finally:
        _close_safely(cursor, connection)


def check_rating_exists(message_id):
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT rating_id
            FROM ratings
            WHERE message = %s;
            """,
            (message_id,),
        )
        result = cursor.fetchone()
        return result[0] if result is not None else None
    finally:
        _close_safely(cursor, connection)


def update_rating(rating_id, rating):
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            UPDATE ratings
            SET rating = %s
            WHERE rating_id = %s;
            """,
            (rating, rating_id),
        )
        connection.commit()
    except Exception:
        if connection is not None:
            connection.rollback()
        raise
    finally:
        _close_safely(cursor, connection)