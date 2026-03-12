from dataclasses import dataclass
import psycopg2
import os
import json
from config import settings


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


def get_connection():
    return psycopg2.connect(
        host=os.environ["SQL_DB_HOST"],
        database=os.environ["SQL_DB_NAME"],
        user=os.environ["SQL_DB_USER"],
        password=os.environ["SQL_DB_PASSWORD"],
        port=os.environ["SQL_DB_PORT"],
    )


# DATABASE FUNCTIONS - USERS


def insert_user(username: str, email: str, password: str) -> int:
    """Insert a new user into the users table

    Args:
        username (str): Username
        email (str): Email
        password (str): Hashed password

    Returns:
        int: user_id of new user
    """
    connection = None
    cursor = None
    try:
        # Establish the connection
        connection = get_connection()
        cursor = connection.cursor()

        # SQL query to insert a new user
        insert_query = f"""
        INSERT INTO users (username, email, password_hash, created_at)
        VALUES ('{username}', '{email}', '{password}', NOW()) RETURNING user_id;
        """

        # Execute the query with parameters
        cursor.execute(insert_query)

        # Commit the transaction
        connection.commit()

        # Fetch the generated user_id for the inserted user
        user_id = cursor.fetchone()[0]

        return user_id

    except Exception as e:
        raise e

    finally:
        # Close the connection and cursor
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def insert_empty_user() -> int:
    """Insert a new user into the users table

    Returns:
        int: user_id of new user
    """
    # Initialize variables to None at the very start
    connection = None
    cursor = None
    
    try:
        # Establish the connection
        connection = get_connection()
        cursor = connection.cursor()

        # SQL query to insert a new user
        # Note: Using %s is safer, though not strictly required for a static query like this
        insert_query = """
        INSERT INTO users (created_at, last_logged_in)
        VALUES (NOW(), NOW()) RETURNING user_id;
        """

        # Execute the query
        cursor.execute(insert_query)

        # Commit the transaction
        connection.commit()

        # Fetch the generated user_id
        result = cursor.fetchone()
        user_id = result[0] if result else None

        return user_id

    except Exception as e:
        # Now we raise the original DB error (like the password failure) 
        # instead of the UnboundLocalError
        raise e

    finally:
        # Safely close only if they were successfully initialized
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


def get_users(filter: str = "all") -> list[User]:
    """Select all rows from the users table

    Args:
        filter ('all' | 'regular' | 'temporary'): Filter type for users.
            - 'all': Get all users
            - 'regular': Get regular users (with username and email)
            - 'temporary': Get temporary users (without username and email)

    Returns:
        list: List of users dict
    """
    connection = None
    cursor = None
    try:
        # Validate filter type
        if filter not in ["all", "regular", "temporary"]:
            raise ValueError(
                "Invalid filter type. Use 'all', 'regular', or 'temporary'."
            )

        # Establish the connection
        connection = get_connection()
        cursor = connection.cursor()

        if filter == "regular":
            # SQL query to fetch regular users
            select_query = (
                "SELECT user_id, username, email, created_at, last_logged_in FROM users "
                "WHERE username IS NOT NULL AND email IS NOT NULL;"
            )
        elif filter == "temporary":
            # SQL query to fetch temporary users
            select_query = (
                "SELECT user_id, created_at, last_logged_in FROM users "
                "WHERE username IS NULL OR email IS NULL;"
            )
        elif filter == "all":
            # SQL query to fetch all users
            select_query = "SELECT user_id, username, email, created_at, last_logged_in FROM users;"

        # Execute the query
        cursor.execute(select_query)

        # Fetch all results
        users = cursor.fetchall()

        # Convert the results to a list of dictionaries
        users_list = []
        for user in users:
            users_list.append(
                {
                    "user_id": user[0],
                    "username": user[1],
                    "email": user[2],
                    "created_at": user[3],
                    "last_logged_in": user[4],
                }
            )

        return users_list

    except Exception as e:
        raise e

    finally:
        # Close the connection and cursor
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def get_selected_user(
    column_name: str, filter_value: str | int, include_password: bool = False
) -> User:
    """Select user from filtered by selected column.

    Args:
        column_name ("user_id" | "username" | "email"): column name string to filter
        filter_value (str | int): filter value for select

    Returns:
        dict: User dictionary
    """
    connection = None
    cursor = None
    try:
        # Raise error if column name is invalid
        if column_name not in ["user_id", "username", "email"]:
            raise ValueError("Invalid column name.")

        # Raise error if user_id column filter value is not integer
        if column_name == "user_id" and not isinstance(filter_value, int):
            raise TypeError("'filter_value' should be 'int' for user_id column name.")

        # Raise error if username or email filter value is not string
        if (column_name == "username" or column_name == "email") and not isinstance(
            filter_value, str
        ):
            raise TypeError(
                "'filter_value' should be 'str' for username and email column name."
            )

        # Establish the connection
        connection = get_connection()
        cursor = connection.cursor()

        filter_str = (
            f"'{filter_value}'" if isinstance(filter_value, str) else filter_value
        )
        select_query = f"""
        SELECT user_id, username, email, password_hash, created_at, last_logged_in FROM users
        WHERE {column_name}={filter_str};
        """

        # Execute the query
        cursor.execute(select_query)
        # Fetch all results
        user_row = cursor.fetchone()

        # If still no user, raise an error
        if not user_row:
            raise KeyError("User not found for given filters.")

        # Convert the results to a dictionary
        user_dict = {
            "user_id": user_row[0],
            "username": user_row[1],
            "email": user_row[2],
            "created_at": user_row[4],
            "last_logged_in": user_row[5],
        }

        # Include password hash if requested
        if include_password:
            user_dict["password_hash"] = user_row[3]

        return user_dict

    except Exception as e:
        raise e

    finally:
        # Close the connection and cursor
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def update_user(user_id: int, username: str, email: str, password: str):
    """Update the user with the given user_id
    Args:
        user_id (int): user_id to update
        username (str): new username
        email (str): new email
        password (str): new password

    Raises:
        ValueError: If trying to update a regular user to another regular user.
        Exception: If any database error occurs.
    """
    connection = None
    cursor = None
    try:
        selected_user = get_selected_user(
            column_name="user_id", filter_value=user_id, include_password=True
        )

        if selected_user["username"] is not None or selected_user["email"] is not None:
            raise ValueError("Cannot update a regular user to another regular user.")

        # Establish the connection
        connection = get_connection()
        cursor = connection.cursor()

        # SQL query to update the user
        update_query = f"""
        UPDATE users
        SET username='{username}', email='{email}', password_hash='{password}', last_logged_in=NOW()
        WHERE user_id={user_id};
        """

        # Execute the query with parameters
        cursor.execute(update_query)

        # Commit the transaction
        connection.commit()

    except Exception as e:
        raise e

    finally:
        # Close the connection and cursor
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# DATABASE FUNCTIONS - SESSIONS


def insert_session(user_id: int, session_token: str, is_active: bool) -> int:
    """_summary_

    Args:
        user_id (int): user id of the session
        session_token (str): token for the session
        is_active (bool): True if the session is active, False if not.

    Returns:
        int: session_id of the new session
    """
    connection = None
    cursor = None
    try:
        # Establish the connection
        connection = get_connection()
        cursor = connection.cursor()

        # SQL query to insert a new user
        insert_query = f"""
        INSERT INTO sessions (user_id, session_token, is_active, created_at, last_accessed)
        VALUES ({user_id}, '{session_token}', {'TRUE' if is_active else 'FALSE'}, NOW(), NOW()) RETURNING session_id;
        """

        # Execute the query with parameters
        cursor.execute(insert_query)

        # Commit the transaction
        connection.commit()

        # Fetch the generated user_id for the inserted user
        session_id = cursor.fetchone()[0]

        return session_id

    except Exception as e:
        raise e

    finally:
        # Close the connection and cursor
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def update_session(session_id: int, last_access_time: str, is_active: bool):
    """Update the session with the given session_id

    Args:
        session_id (int): session_id to update
        last_access_time (str): last_accessed time string
        is_active (bool): True if the session is active, False if not.

    Raises:
        Exception: If any database error occurs.
    """
    connection = None
    cursor = None
    try:
        # Establish the connection
        connection = get_connection()
        cursor = connection.cursor()

        # SQL query to update the session
        update_query = f"""
        UPDATE sessions
        SET last_accessed='{last_access_time}', is_active={'TRUE' if is_active else 'FALSE'}
        WHERE session_id={session_id};
        """

        # Execute the query with parameters
        cursor.execute(update_query)

        # Commit the transaction
        connection.commit()

    except Exception as e:
        raise e

    finally:
        # Close the connection and cursor
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def get_selected_session(
    column_name: str, filter_value: int, filter_is_active: bool = False
) -> list[Session]:
    """Select sessions from filtered by selected column.

    Args:
        column_name ("session_id" | "user_id" ): column name string to filter
        filter_value (int): filter value for select
        filter_is_active (bool): True if filter by is_active column, False if no filter.
            Default is False.

    Returns:
        list: List of sessions dictionary
    """
    connection = None
    cursor = None
    try:
        # Raise error if column name is invalid
        if column_name not in ["session_id", "user_id"]:
            raise ValueError("Invalid column name.")

        # Establish the connection
        connection = get_connection()
        cursor = connection.cursor()

        filter_is_active_str = "AND is_active=TRUE" if filter_is_active else ""
        select_query = f"""
        SELECT session_id, user_id, session_token, is_active, created_at, last_accessed FROM sessions
        WHERE {column_name}={filter_value} {filter_is_active_str};
        """

        # Execute the query
        cursor.execute(select_query)
        # Fetch all results
        session_rows = cursor.fetchall()

        # Convert the results to a list of dictionaries
        session_list = []
        for session in session_rows:
            session_list.append(
                {
                    "session_id": session[0],
                    "user_id": session[1],
                    "session_token": session[2],
                    "is_active": session[3],
                    "created_at": session[4],
                    "last_accessed": session[5],
                }
            )

        return session_list

    except Exception as e:
        raise e

    finally:
        # Close the connection and cursor
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def get_all_sessions() -> list[Session]:
    """Select all rows from the sessions table

    Returns:
        list: List of sessions dict
    """
    connection = None
    cursor = None
    try:
        # Establish the connection
        connection = get_connection()
        cursor = connection.cursor()

        # SQL query to fetch all users
        select_query = "SELECT session_id, user_id, session_token, is_active, last_accessed FROM sessions;"

        # Execute the query
        cursor.execute(select_query)

        # Fetch all results
        sessions = cursor.fetchall()

        # Convert the results to a list of dictionaries
        sessions_list = [
            {
                "session_id": session[0],
                "user_id": session[1],
                "session_token": session[2],
                "is_active": session[3],
                "last_accessed": session[4],
            }
            for session in sessions
        ]

        return sessions_list

    except Exception as e:
        raise e

    finally:
        # Close the connection and cursor
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# DATABASE FUNCTIONS - MESSAGES


def get_selected_messages(column_name: str, filter_value: int) -> list[Message]:
    """Select messages from filtered by selected column.

    Args:
        column_name ("message_id" | "session_id" | "sender_id" ): column name string to filter
        filter_value (int): filter value for select

    Returns:
        list: List of sessions dictionary
    """
    connection = None
    cursor = None
    try:
        # Raise error if column name is invalid
        if column_name not in ["message_id", "session_id", "sender_id"]:
            raise ValueError("Invalid column name.")

        # Establish the connection
        connection = get_connection()
        cursor = connection.cursor()

        select_query = f"""
        SELECT message_id, session_id, role, content, sent_at FROM messages
        WHERE {column_name}={filter_value};
        """

        # Execute the query
        cursor.execute(select_query)
        # Fetch all results
        message_rows = cursor.fetchall()

        # Convert the results to a list of dictionaries
        message_list = []
        for message in message_rows:
            message_list.append(
                {
                    "message_id": message[0],
                    "session_id": message[1],
                    "role": message[2],
                    "content": message[3],
                    "sent_at": message[4],
                }
            )

        return message_list

    except Exception as e:
        raise e

    finally:
        # Close the connection and cursor
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def insert_messages(messages: list[dict]):
    """Insert multiple messages into the messages table.

    Args:
        messages (list[dict]): List of message dictionaries, each containing keys:
            - session_id (int)
            - role (str)
            - content (str)
            - sent_at (datetime)

    Raises:
        ValueError: If the messages list is empty or any message dictionary is missing required keys.
        Exception: If any database error occurs.

    Returns:
        list: List of inserted message ids
    """
    connection = None
    cursor = None
    if not messages:
        raise ValueError("Messages list is empty.")

    check_roles = [(m["role"] not in ["user", "assistant", "system"]) for m in messages]

    if any(check_roles):
        raise ValueError(
            "Invalid role type in messages list. Valid roles are 'user', 'assistant', 'system'."
        )

    try:
        # Establish the connection
        connection = get_connection()
        cursor = connection.cursor()

        insert_query = """
            INSERT INTO messages (session_id, role, content, sent_at)
            VALUES (%s, %s, %s, %s) RETURNING message_id;
        """

        # Prepare data for insertion
        data = [
            (msg["session_id"], msg["role"], msg["content"], msg["sent_at"])
            for msg in messages
        ]

        # Execute the query
        cursor.executemany(insert_query, data)

        # Commit the transaction
        connection.commit()

        return

    except Exception as e:
        connection.rollback()
        raise e

    finally:
        # Close the connection and cursor
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# DATABASE FUNCTIONS - ratings
def insert_rating(user_id, rating, message, version):
    connection = None
    cursor = None
    userId = user_id
    if user_id == 1:
        userId = "NULL"
    print(version)

    try:
        connection = get_connection()
        cursor = connection.cursor()

        insert_query = f"""
            INSERT INTO ratings (user_id, rating, message, version)
            VALUES ({userId}, {rating}, '{message}', '{version}') RETURNING rating_id
        """

        cursor.execute(insert_query)

        connection.commit()

        rating_id = cursor.fetchone()[0]
        return rating_id

    except Exception as e:
        connection.rollback()
        raise e

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def check_rating_exists(message_id):
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()

        select_query = f"""
            SELECT rating_id FROM ratings WHERE message = '{message_id}'
        """

        cursor.execute(select_query)
        result = cursor.fetchone()

        if result is not None:
            return result[0]  # Return the rating_id
        else:
            return None

    except Exception as e:
        raise e

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def update_rating(rating_id, rating):
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()

        update_query = f"""
            UPDATE ratings
            SET rating = {rating}
            WHERE rating_id = {rating_id}
        """

        cursor.execute(update_query)

        connection.commit()

    except Exception as e:
        connection.rollback()
        raise e

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
