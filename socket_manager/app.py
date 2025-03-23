import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from service.entrypoints import router
from config.settings import ALLOWED_ORIGINS
import redis


# Create Socket.IO server with CORS settings
sio = socketio.AsyncServer(
    async_mode="asgi", cors_allowed_origins="*", logger=True, engineio_logger=True
)

# Initialize FastAPI app and mount Socket.IO as ASGI middleware
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
socket_app = socketio.ASGIApp(sio, app)

# Redis connection
redis_client = redis.StrictRedis(host="127.0.0.1", port=6379, decode_responses=True)
print("result is here")


@app.get("/")
async def root():
    return {"message": "WebSocket and Redis app running!"}


@app.get("/test-redis")
async def test_redis():
    try:
        redis_client.set("test_key", "Hello from FastAPI")
        value = redis_client.get("test_key")
        return {"redis_value": value}
    except Exception as e:
        return {"error": str(e)}
