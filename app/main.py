# server.py
from fastapi import FastAPI
import socketio

# Create a new Socket.IO server
# Allow localhost:5173 as a CORS origin
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=['http://localhost:5173']
)
app = FastAPI()
app = socketio.ASGIApp(sio, app)  # Integrate Socket.IO with FastAPI

# Socket.IO events
@sio.event
async def connect(sid, environ):
    print("Client connected:", sid)

@sio.event
async def disconnect(sid):
    print("Client disconnected:", sid)

@sio.event
async def send_message(sid, data):
    print(f"Received message from {sid}: {data}")  # Log the received message
    try:
        await sio.emit("receive_message", data, room=sid)  # Attempt to emit to all clients
        print("Message sent:", data)  # Log the success if it works
    except Exception as e:
        print("Error emitting message:", e)  # Log any error if emit fails

# Run the application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
