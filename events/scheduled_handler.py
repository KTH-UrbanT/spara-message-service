from socket_manager.app import redis_client
import json
from service.database import insert_session, insert_messages, get_all_sessions
import time 
from datetime import datetime, timezone
EXPIRATION_TIME = 5 * 60  # 300 seconds

def scheduled_thread_read():
    print("I'm working scheduled job...")
    thread_keys = redis_client.keys()

    if not thread_keys:
        print("No threads found")
        return

    insert_dict = []
    current_time = int(time.time()) 
    for key in thread_keys:
        print("KEY", key)
        thread_content = redis_client.lrange(key, 0, -1)
        if last_update_time(thread_content , current_time) is True : 
            insert_dict.append(key)
        #insert_dict[key] = read_thread_messages(thread_content)
        #print("MESSAGES: ", insert_dict[key])

    # Insert the messages into the database
    print("Inserting messages into the database...")
    print(insert_dict)
    insert_threads(insert_dict)

    # Process the messages and delete the thread
    # redis_client.delete(*thread_keys)


def last_update_time(thread_content , current_time):
    print("processing messages...")
    if json.loads(thread_content[-1])['timestamp'] < (current_time - EXPIRATION_TIME) : 
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

            # Convert JSON strings to Python objects
            try:
                thread_content_updated = [json.loads(msg) for msg in thread_content]
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON for thread {thread_id}: {e}")
                continue  # Skip this thread if JSON is invalid

            # Convert timestamps to UTC format
            thread_content_updated = [
                {
                    **msg, 
                    'timestamp': datetime.fromtimestamp(msg.get('timestamp', 0), tz=timezone.utc).isoformat()
                }
                for msg in thread_content_updated if 'timestamp' in msg
            ]

            # Validate if messages exist after processing
            if not thread_content_updated:
                print(f"Thread {thread_id} has no valid messages after processing.")
                continue

            ### Database Push Code (Placeholder)
            # insert_into_database(thread_id, thread_content_updated)  # Replace with actual DB function

            # Delete thread from Redis after successful processing
            redis_client.delete(thread_id)
            print(f"Thread {thread_id} successfully processed and deleted from Redis.")

        except Exception as e:
            print(f"Error processing thread {thread_id}: {e}")