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
async def connect(sid, environ, auth):
    """Handle client connection and authenticate the session.

    This function is called when a client connects to the WebSocket.
    It checks the authentication details provided by the client, enters the
    client into the appropriate session room, and retrieves the messages
    associated with that session from the database. It also inserts the
    messages into the Redis client for real-time updates.

    Args:
        sid (str): The socket session ID of the client.
        environ (dict): The environment variables provided by the client.
        auth (dict): Authentication details provided by the client, including
            session_id and session_id_int.
    """
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
            thread_id=session_id,
        )

    # Update the session with the latest messages
    await session_updated(session_id=auth.get("session_id"), room=sid)


@sio.event
async def disconnect(sid):
    """Handle client disconnection and clean up session data.

    This function is called when a client disconnects from the WebSocket.
    It removes the session from Redis, updates the session status in the
    database as inactive.

    Args:
        sid (str): The socket session ID of the client.
    """
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
    """Establish a session socket id pair for the client and store details in socket.

    Args:
        sid (str): The socket session ID of the client.
        session_id (str): The session ID for the current conversation.
        session_id_int (int): The integer session ID from DB.
        user_id (str): The ID of the user client.
    """
    await sio.save_session(
        sid,
        {
            "session_id": session_id,
            "session_id_int": session_id_int,
            "user_id": user_id,
        },
    )


@sio.event  #här ska det fixas
async def create_session(sid, message, user_id=None):
    """Create a new session for the user and store it in the database.

    This function is called when a new session is initiated by the client
    and it creates a new session in the database, associates it with the
    provided user ID, and emits a confirmation message back to the client.

    Args:
        sid (str): The socket session ID of the client.
        message (str): The initial message or context for the session.
        user_id (str, optional): The ID of the user creating the session.
    """
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
    """Handle incoming messages from WebSocket clients.

    This function processes messages sent by clients, adds them to the Redis
    queue, and sends the messages to the language model in order to generate
    responses. Inserts the messages into the database and emits the response,
    back to the client.

    Args:
        sid (str): The socket session ID of the client.
        data (str): The message content sent by the client.
        session_id (str): The session ID for the current conversation.
        session_id_int (int): The integer session ID from DB.
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
        thread_name = f"thread:{session_id}:messages"
        # Push the message to the Redis
        redis_client.rpush(thread_name, message_data)

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
        event_data = json.dumps({"event": "message_added", "session_id_int": session_id_int, "thread_name": session_id })
        redis_client.publish("thread_events", event_data)

        print(f"Message added to Redis for thread: {session_id}")

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
    """Emit to client about session updates.

    This function retrieves the messages from Redis for the given session ID,
    filters out system messages, and emits the updated session messages
    back to the client. If the session ID is None, it initializes an empty
    messages list.

    Args:
        session_id (str): Session ID to update.
        room (str, optional): Room ID to emit. Defaults to None.
    """
    if session_id is None:
        messages_list = []
    else:
        thread_name = f"thread:{session_id}:messages"
        messages = redis_client.lrange(thread_name, 0, -1)
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
