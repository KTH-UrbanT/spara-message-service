from socket_manager.app import redis_client
import json
from service.database import insert_session, insert_messages, get_all_sessions


def scheduled_thread_read():
    print("I'm working scheduled job...")
    thread_keys = redis_client.scan_iter("thread:*")

    if not thread_keys:
        print("No threads found")
        return

    insert_dict = {}
    for key in thread_keys:
        print("KEY", key)
        thread_content = redis_client.lrange(key, 0, -1)
        insert_dict[key] = read_thread_messages(thread_content)
        print("MESSAGES: ", insert_dict[key])

    # Insert the messages into the database
    print("Inserting messages into the database...")
    # insert_threads(insert_dict)

    # Process the messages and delete the thread
    # redis_client.delete(*thread_keys)


def read_thread_messages(thread_content):
    print("processing messages...")

    messages_processed = []
    for message in thread_content:
        messages_processed.append(json.loads(message))

    return messages_processed


def insert_threads(processed_threads):
    # Start with first thread
    # If session id exists, insert messages
    # If not, insert session and messages
    # Continue to next thread
    for key, value in processed_threads.items():
        if not value:
            print("No messages found in thread.")
            continue
        # session_id = value[0]["session_id"]

        # all_sessions = get_all_sessions()
        # all_session_ids = [session["session_id"] for session in all_sessions]
        # print("ALL SESSIONS: ", all_sessions)

        # if session_id in all_session_ids:
        #     print(f"Session {session_id} already exists.")
        # else:
        #     # TODO: Insert session
        #     # sender id is not available in the message
        #     # check if sender id is available in the db
        #     # if not, insert new user or skip? but DB should have a sender id
        #     insert_session(session_id)

        # # TODO: Insert messages
        # # sender id is not available in the message
        # insert_messages(
        #     [
        #         {
        #             "session_id": session_id,
        #             # "sender_id": sender_id,
        #             "content": message["content"],
        #             "role": message["role"],
        #             "timestamp": message["timestamp"],
        #         }
        #         for message in value
        #     ]
        # )


# thread_name = "thread:YDOrEnG8w0iC6WTrAAAB"  # Example thread
# messages = redis_client.lrange(thread_name, 0, -1)  # Get all messages
# print(messages)

# # Convert JSON strings back to Python objects
# messages = [json.loads(msg) for msg in messages]
# print(messages)
