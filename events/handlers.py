from socket_manager.app import sio, redis_client
import asyncio
import json
import time
from service.redis import insert_into_redis_client
from service.database import (
    get_selected_messages,
    insert_session,
    insert_messages,
    update_session,
)
from datetime import datetime, timezone


@sio.event
async def connect(sid, _, auth):
    if not auth:
        print("Authentication failed for client: ", sid)
        return False  # Reject the connection if no auth is provided

    if (
        "session_id" in auth
        and auth.get("session_id")
        and "session_id_int" in auth
        and auth.get("session_id_int")
    ):
        session_id = auth["session_id"]
        sio.enter_room(sid, session_id)
        print("Client connected:", sid, auth)

        messages_list = []

        try:
            messages_list = get_selected_messages(
                column_name="session_id", filter_value=auth["session_id_int"]
            )
        except Exception as e:
            print("Error fetching messages:", e)

        insert_into_redis_client(
            conversation_list=messages_list,
            redis_client=redis_client,
            thread_name=session_id,
        )

    # Update the session with the latest messages
    await session_updated(session_id=auth.get("session_id"), room=sid)


@sio.event
async def disconnect(sid):
    print("Client disconnected:", sid)

    auth = await sio.get_session(sid) or {}
    session_id = auth.get("session_id")
    session_id_int = auth.get("session_id_int")

    if session_id and session_id_int:
        try:
            # Remove the session from Redis
            redis_client.delete(session_id)
            print(f"Thread {session_id} successfully processed and deleted from Redis.")

            # Set the session as inactive in the database
            timestamp = datetime.fromtimestamp(time.time(), tz=timezone.utc).isoformat()
            update_session(
                session_id=session_id_int,
                last_access_time=timestamp,
                is_active=False,
            )

        except Exception as e:
            print("Error closing session:", e)
            await sio.emit("error_message", {"error": str(e)}, room=sid)


@sio.event
async def establish_session(sid, session_id, session_id_int, user_id):
    """Establish a session socket id pair for the client and store details in socket."""
    await sio.save_session(
        sid,
        {
            "session_id": session_id,
            "session_id_int": session_id_int,
            "user_id": user_id,
        },
    )


@sio.event
async def create_session(sid, message, user_id=None):
    try:
        if not user_id:
            print("User ID is required to create a session.")
            await sio.emit("error_message", {"error": "User ID is required."}, room=sid)
            return

        session_id_int = insert_session(
            user_id=user_id, session_token=sid, is_active=True
        )
        session_id = str(sid)

        await sio.emit(
            "session_created",
            {
                "session_id": session_id,
                "session_id_int": session_id_int,
                "message": message,
            },
            room=sid,
        )
        print("New session created with ID:", session_id)

    except Exception as e:
        print("Error creating session:", e)


@sio.event
async def send_message(sid, data, session_id, session_id_int):
    """
    Handle incoming messages from WebSocket clients and store them in Redis.
    """
    print(f"Received message from {sid}: {data}")

    try:
        if not data or not data.strip():
            await sio.emit(
                "error_message", {"error": "Message cannot be empty."}, room=sid
            )
            return

        if not session_id:
            await sio.emit(
                "error_message", {"error": "Session ID is required."}, room=sid
            )
            return

        if not session_id_int:
            await sio.emit(
                "error_message", {"error": "Session ID integer is required."}, room=sid
            )
            return

        print("SEND_MESSAGE to thread: ", session_id, "session_id_int:", session_id_int)

        message_dict = {
            "content": data,
            "role": "user",
            "timestamp": time.time(),
            "added_to_database": 0,
        }
        # Add message to Redis thread
        message_data = json.dumps(message_dict)

        # Push the message to the Redis
        redis_client.rpush(session_id, message_data)

        # Insert message into the database
        insert_messages(
            [
                {
                    "content": message_dict["content"],
                    "role": message_dict["role"],
                    "sent_at": datetime.fromtimestamp(
                        message_dict["timestamp"], tz=timezone.utc
                    ).isoformat(),
                    "session_id": int(session_id_int),
                }
            ]
        )

        await session_updated(session_id, room=sid)

        # Notify Redis queue manager to process the message
        event_data = json.dumps({"event": "message_added", "thread_name": session_id})
        redis_client.publish("thread_events", event_data)

        print(f"Message added to Redis for thread: {session_id}")

        # Wait for the reply from the Redis queue
        retry_count = 0
        max_retries = 100  # Adjust this based on expected processing time
        response_message = None

        while retry_count < max_retries:
            await asyncio.sleep(10)  # Check every 0.5 seconds
            messages = redis_client.lrange(session_id, 0, -1)

            if len(messages) > 1:  # Check if a response message has been added
                last_message = json.loads(messages[-1])
                if (
                    last_message.get("role") == "assistant"
                ):  # Ensure it's from the language model
                    response_message = {
                        "content": last_message.get("content"),
                        "role": "assistant",
                        "status": "success",
                        "session_id": session_id,
                        "timestamp": last_message.get("timestamp"),
                    }
                    break

            retry_count += 1

        if not response_message:
            # If no response after retries, send a timeout message
            response_message = {
                "content": "Processing timed out. Please try again later.",
                "role": "assistant",
                "status": "error",
                "session_id": session_id,
                "timestamp": time.time(),
            }
            redis_client.rpush(session_id, json.dumps(response_message))

        # Insert response message into the database
        insert_messages(
            [
                {
                    "content": response_message["content"],
                    "role": response_message["role"],
                    "sent_at": datetime.fromtimestamp(
                        response_message["timestamp"], tz=timezone.utc
                    ).isoformat(),
                    "session_id": int(session_id_int),
                }
            ]
        )

        await session_updated(session_id, room=sid)

        # Emit the response back to the client
        # print("Redis client:", redis_client) # Debugging line
        await sio.emit("answer_message", response_message, room=sid)
        print("Response sent:", response_message)

    except Exception as e:
        print("Error processing message:", e)
        await sio.emit("error_message", {"error": str(e)}, room=sid)


async def session_updated(session_id, room=None):
    if session_id is None:
        messages_list = []
    else:
        messages = redis_client.lrange(session_id, 0, -1)
        messages_list = [
            json.loads(message)
            for message in messages
            if json.loads(message).get("role") != "system"
        ]
        # print("Messages in Redis for session:", session_id, messages_list) # Debugging line

    await sio.emit(
        "session_updated",
        {
            "session_id": session_id,
            "messages": messages_list,
        },
        room=room,
    )
