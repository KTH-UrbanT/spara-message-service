import socketio
from fastapi import FastAPI
from service.entrypoints import router
from config.settings import ALLOWED_ORIGINS

# Create Socket.IO server with CORS settings
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=ALLOWED_ORIGINS,
    logger=True,
    engineio_logger=True
)

# Initialize FastAPI app and mount Socket.IO as ASGI middleware
app = FastAPI()
app.include_router(router)
socket_app = socketio.ASGIApp(sio, app)
