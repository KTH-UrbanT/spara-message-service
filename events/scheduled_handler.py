from socket_manager.app import redis_client
import json
from service.database import (
    insert_session,
    insert_messages,
    get_all_sessions,
    update_session,
)
import time
from datetime import datetime, timezone

from config.settings import SESSION_EXPIRATION_TIME


def scheduled_thread_read():
    print("Scheduled job running...")
    # Fetch all thread keys from Redis
    thread_keys = redis_client.keys()

    # Check if any threads exist
    if not thread_keys:
        print("No threads found.")
        return

    insert_dict = []
    current_time = int(time.time())
    for key in thread_keys:
        thread_content = redis_client.lrange(key, 0, -1)
        print("THREAD KEY: ", key)
        # print("THREAD CONTENT: ", thread_content)
        if last_update_time(thread_content, current_time) is True:
            insert_dict.append(key)
        # insert_dict[key] = read_thread_messages(thread_content)
        # print("MESSAGES: ", insert_dict[key])

    # Insert the messages into the database
    # Check if there are any threads to insert
    if not insert_dict:
        print("No threads to insert.")
        return

    insert_threads(insert_dict)


def last_update_time(thread_content, current_time):
    """Check if the last message in the thread is older than the expiration time."""
    if not thread_content:
        return False

    if json.loads(thread_content[-1])["timestamp"] < (current_time - SESSION_EXPIRATION_TIME):
        return True
    return False


def insert_threads(processed_threads):
    """Processes and inserts threads into the database, then deletes them from Redis."""
    for thread_id in processed_threads:
        try:
            # Fetch messages from Redis
            thread_content = redis_client.lrange(thread_id, 0, -1)

            if not thread_content:
                print(f"Thread {thread_id} is empty or does not exist.")
                continue  # Skip empty threads

            all_sessions = get_all_sessions()

            # Check if the thread exists in the database
            is_session_exists = [
                session
                for session in all_sessions
                if session["session_token"] == thread_id
            ]
            print("IS SESSION EXISTS: ", is_session_exists)

            user_id = thread_id.split(":")[0]

            if not is_session_exists:
                print(f"Thread {thread_id} does not exist in the database.")
                session_id = insert_session(user_id, thread_id, True)
            else:
                session_id = is_session_exists[0]["session_id"]

            # Convert JSON strings to Python objects
            try:
                thread_content_updated = [json.loads(msg) for msg in thread_content]
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON for thread {thread_id}: {e}")
                continue  # Skip this thread if JSON is invalid

            # Convert timestamps to UTC format
            thread_content_updated = [
                {
                    "content": msg["content"],
                    "role": msg["role"],
                    "sent_at": datetime.fromtimestamp(
                        msg["timestamp"], tz=timezone.utc
                    ).isoformat(),
                    "session_id": session_id,
                    "sender_id": user_id,
                }
                for msg in thread_content_updated
                if "timestamp" in msg and msg["added_to_database"] == 0
            ]

            # Validate if messages exist after processing
            if not thread_content_updated:
                print(f"Thread {thread_id} has no valid messages after processing.")
                continue

            # Insert messages into the database
            insert_messages(thread_content_updated)

            # Delete thread from Redis after successful processing
            redis_client.delete(thread_id)
            print(f"Thread {thread_id} successfully processed and deleted from Redis.")

            # TODO: send socket emit to update the session

            # Update the session is_active status
            update_session(session_id, "NOW()", False)

        except Exception as e:
            print(f"Error processing thread {thread_id}: {e}")
