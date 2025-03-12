from socket_manager.app import sio, redis_client
import asyncio
import json
import time


@sio.event
async def connect(sid, environ):
    print("Client connected:", sid)


@sio.event
async def disconnect(sid):
    print("Client disconnected:", sid)


@sio.event
async def send_message(sid, data):
    """
    Handle incoming messages from WebSocket clients and store them in Redis.
    """
    print("does code reach here")
    print(f"Received message from {sid}: {data}")
    try:
        print("Session id:", sid)
        print("SEND_MESSAGE data:", data)
        if not data:
            await sio.emit(
                "error_message", {"error": "Message cannot be empty."}, room=sid
            )
            return

        # Add message to Redis thread
        message_data = json.dumps(
            {"content": data, "role": "user", "timestamp": time.time()}
        )
        redis_client.rpush(sid, message_data)

        # Notify Redis queue manager to process the message
        event_data = json.dumps({"event": "message_added", "thread_name": sid})
        redis_client.publish("thread_events", event_data)

        print(f"Message added to Redis for thread: {sid}")

        # Wait for the reply from the Redis queue
        retry_count = 0
        max_retries = 10  # Adjust this based on expected processing time
        response_message = None

        while retry_count < max_retries:
            await asyncio.sleep(0.5)  # Check every 0.5 seconds
            messages = redis_client.lrange(sid, 0, -1)

            if len(messages) > 1:  # Check if a response message has been added
                last_message = json.loads(messages[-1])
                if (
                    last_message.get("role") == "assistant"
                ):  # Ensure it's from the language model
                    response_message = {
                        "content": last_message.get("content"),
                        "role": "assistant",
                        "status": "success",
                        "session_id": sid,
                        "timestamp": last_message.get("timestamp"),
                    }
                    break

            retry_count += 1

        if not response_message:
            response_message = {
                "content": "Processing timed out. Please try again later.",
                "role": "assistant",
                "status": "error",
                "session_id": sid,
                "timestamp": time.time(),
            }

        # Emit the response back to the client
        print("Redis client:", redis_client)
        await sio.emit("answer_message", response_message, room=sid)
        print("Response sent:", response_message)

    except Exception as e:
        print("Error processing message:", e)
        await sio.emit("error_message", {"error": str(e)}, room=sid)
