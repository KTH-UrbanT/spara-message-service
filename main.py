from socket_manager.app import socket_app  # Import the Socket.IO FastAPI app
from config.settings import HOST, PORT
import events.handlers as handlers  # Import events to ensure they are registered

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(socket_app, host=HOST, port=PORT)
