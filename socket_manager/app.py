import redis
import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from service.entrypoints import router, limiter
from config import settings

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

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(router)
socket_app = socketio.ASGIApp(sio, app)

# Redis connection
redis_client = redis.Redis(
    host=settings.REDIS_HOST, port=settings.REDIS_PORT, decode_responses=True
)


@app.get("/")
async def root():
    return {"message": "SocketIO and Redis are running!"}


@app.get("/test-redis")
async def test_redis():
    try:
        redis_client.set("test_key", "Hello from FastAPI")
        value = redis_client.get("test_key")
        return {"redis_value": value}
    except Exception as e:
        return {"error": str(e)}
