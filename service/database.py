from dataclasses import dataclass
import psycopg2
import os


@dataclass
class User:
    user_id: int
    username: str
    email: str
    password: str
    created_at: str


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
    sender_id: int
    content: str
    sent_at: str


def get_connection():
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        database=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        port=os.environ["DB_PORT"],
    )


# DATABASE FUNCTIONS - USERS


def insert_user(username: str, email: str, password: str) -> int:
    """Insert a new user into the users table

    Args:
        username (str): Username
        email (str): Email
        password (str): Password

    Returns:
        int: user_id of new user
    """
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


def get_users() -> list[User]:
    """Select all rows from the users table

    Returns:
        list: List of users dict
    """
    try:
        # Establish the connection
        connection = get_connection()
        cursor = connection.cursor()

        # SQL query to fetch all users
        select_query = "SELECT user_id, username, email, created_at FROM users;"

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


def get_selected_user(column_name: str, filter_value: str | int) -> User:
    """Select user from filtered by selected column.

    Args:
        column_name ("user_id" | "username" | "email"): column name string to filter
        filter_value (str | int): filter value for select

    Returns:
        dict: User dictionary
    """
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
        SELECT user_id, username, email, password_hash, created_at FROM users
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
            # "password": user_row[3],
            "created_at": user_row[4],
        }

        return user_dict

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

        # If still no user, raise an error
        if not session_rows:
            raise KeyError("Session not found for given filters.")

        # Convert the results to a list of dictionaries
        session_list = []
        for session in session_rows:
            session_list.append(
                {
                    "session_id": session[0],
                    "user_id": session[0],
                    "session_token": session[1],
                    "is_active": session[2],
                    "created_at": session[3],
                    "last_accessed": session[4],
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


# DATABASE FUNCTIONS - MESSAGES


def get_selected_messages(column_name: str, filter_value: int) -> list[Message]:
    """Select messages from filtered by selected column.

    Args:
        column_name ("message_id" | "session_id" | "sender_id" ): column name string to filter
        filter_value (int): filter value for select

    Returns:
        list: List of sessions dictionary
    """
    try:
        # Raise error if column name is invalid
        if column_name not in ["message_id", "session_id", "sender_id"]:
            raise ValueError("Invalid column name.")

        # Establish the connection
        connection = get_connection()
        cursor = connection.cursor()

        select_query = f"""
        SELECT message_id, session_id, sender_id, content, sent_at FROM messages
        WHERE {column_name}={filter_value};
        """

        # Execute the query
        cursor.execute(select_query)
        # Fetch all results
        message_rows = cursor.fetchall()

        # If still no user, raise an error
        if not message_rows:
            raise KeyError("Message not found for given filters.")

        # Convert the results to a list of dictionaries
        message_list = []
        for message in message_rows:
            message_list.append(
                {
                    "message_id": message[0],
                    "session_id": message[1],
                    "sender_id": message[2],
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
            - sender_id (int)
            - content (str)
            - sent_at (datetime)

    Raises:
        ValueError: If the messages list is empty or any message dictionary is missing required keys.
        Exception: If any database error occurs.

    Returns:
        list: List of inserted message ids
    """
    if not messages:
        raise ValueError("Messages list is empty.")

    try:
        # Establish the connection
        connection = get_connection()
        cursor = connection.cursor()

        # Prepare the SQL query
        placeholders = []
        for message in messages:
            placeholders.append(
                f"({message.session_id}, {message.sender_id}, '{message.content}', {message.sent_at})"
            )

        insert_query = f"""
        INSERT INTO messages (session_id, sender_id, content, sent_at)
        VALUES {', '.join(placeholders)} RETURNING message_id;
        """

        # Execute the query
        cursor.execute(insert_query)

        # Commit the transaction
        connection.commit()

        # Fetch all results
        message_ids = cursor.fetchall()
        return message_ids

    except Exception as e:
        connection.rollback()
        raise e

    finally:
        # Close the connection and cursor
        if cursor:
            cursor.close()
        if connection:
            connection.close()
