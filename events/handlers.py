from socket_manager.app import sio, redis_client
import asyncio
import json
import time
from service.redis import insert_into_redis_client
from service.database import get_selected_messages


@sio.event
async def connect(sid, environ, auth):
    if not auth:
        print("Authentication failed for client: ", sid)
        return False  # Reject the connection if no auth is provided

    print("Client connected:", sid, auth)
    if "session_token" in auth and auth.get("session_token"):
        messages_list = get_selected_messages(
            column_name="session_id", filter_value=auth["session_id"]
        )

        insert_into_redis_client(
            conversation_list=messages_list,
            redis_client=redis_client,
            thread_name=auth["session_token"],
        )

    if "session_id" in auth and "session_token" in auth:
        # Update the session with the latest messages
        await update_session(
            session_id=auth.get("session_id"), thread_name=auth.get("session_token")
        )


@sio.event
async def disconnect(sid):
    print("Client disconnected:", sid)


@sio.event
async def send_message(sid, data, user_id, session_id, session_token):
    """
    Handle incoming messages from WebSocket clients and store them in Redis.
    """
    print("does code reach here")
    print(f"Received message from {sid}: {data}")

    if not session_token:
        thread_name = f"{user_id}:{sid}"
    else:
        thread_name = session_token

    try:
        print("SEND_MESSAGE data:", data, "to thread: ", thread_name)
        if not data:
            await sio.emit(
                "error_message", {"error": "Message cannot be empty."}, room=sid
            )
            return

        # Add message to Redis thread
        message_data = json.dumps(
            {
                "content": data,
                "role": "user",
                "timestamp": time.time(),
                "added_to_database": 0,
            }
        )
        redis_client.rpush(thread_name, message_data)
        await update_session(session_id, thread_name)

        # Notify Redis queue manager to process the message
        event_data = json.dumps({"event": "message_added", "thread_name": thread_name})
        redis_client.publish("thread_events", event_data)

        print(f"Message added to Redis for thread: {thread_name}")

        # Wait for the reply from the Redis queue
        retry_count = 0
        max_retries = 100  # Adjust this based on expected processing time
        response_message = None

        while retry_count < max_retries:
            await asyncio.sleep(10)  # Check every 0.5 seconds
            messages = redis_client.lrange(thread_name, 0, -1)

            if len(messages) > 1:  # Check if a response message has been added
                last_message = json.loads(messages[-1])
                if (
                    last_message.get("role") == "assistant"
                ):  # Ensure it's from the language model
                    response_message = {
                        "content": last_message.get("content"),
                        "role": "assistant",
                        "status": "success",
                        "session_id": thread_name,
                        "timestamp": last_message.get("timestamp"),
                        "added_to_database": 0,
                    }
                    break

            retry_count += 1

        if not response_message:
            response_message = {
                "content": "Processing timed out. Please try again later.",
                "role": "assistant",
                "status": "error",
                "session_id": thread_name,
                "timestamp": time.time(),
                "added_to_database": 0,
            }
            redis_client.rpush(thread_name, json.dumps(response_message))

        await update_session(session_id, thread_name)
        # Emit the response back to the client
        print("Redis client:", redis_client)
        await sio.emit("answer_message", response_message, room=sid)
        print("Response sent:", response_message)

    except Exception as e:
        print("Error processing message:", e)
        await sio.emit("error_message", {"error": str(e)}, room=sid)


async def update_session(session_id, thread_name):
    if thread_name is None:
        messages_list = []
    else:
        messages = redis_client.lrange(thread_name, 0, -1)
        messages_list = [
            json.loads(message)
            for message in messages
            if json.loads(message).get("role") != "system"
        ]

    await sio.emit(
        "session_update",
        {
            "session_id": session_id,
            "thread_name": thread_name,
            "messages": messages_list,
        },
    )
