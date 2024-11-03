from socket_manager.app import sio

@sio.event
async def connect(sid, environ):
    print("Client connected:", sid)

@sio.event
async def disconnect(sid):
    print("Client disconnected:", sid)

@sio.event
async def send_message(sid, data):
    print(f"Received message from {sid}: {data}")
    try:
        await sio.emit("receive_message", data, room=sid)
        print("Message sent:", data)
    except Exception as e:
        print("Error emitting message:", e)
