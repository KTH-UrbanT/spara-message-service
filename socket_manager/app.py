import socketio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware


from service.entrypoints import router
from config import settings
import redis

import psycopg2.errors
import os

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
redis_client = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT , decode_responses=True)


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

@app.get("/health")
async def healthcheck():
    # 1) Check Postgres
    try:
        conn = psycopg2.connect(
            dbname=os.getenv("SQL_DB_NAME"),
            user=os.getenv("SQL_DB_USER"),
            password=os.getenv("SQL_DB_PASSWORD"),
            host=os.getenv("SQL_DB_HOST"),
            port=os.getenv("SQL_DB_PORT"),
            connect_timeout=1
        )
        cur = conn.cursor()
        cur.execute("SELECT 1")
        conn.close()
    except Exception as e:
        # Print to logs and show the error message
        print("Healthcheck DB error:", str(e))
        raise HTTPException(status_code=500, detail=str(e))
    
    # 2) Check Redis (via imported redis_client)
    try:
        # Write a temporary key
        redis_client.set("healthcheck_key", "ok", ex=5)  # expires in 5 seconds
        # Read it back
        value = redis_client.get("healthcheck_key")

        if value is None or value.decode("utf-8") != "ok":
            raise Exception("get and set operation failed, redis is unresponsive")
    except Exception as e:
        print("Healthcheck Redis error:", str(e))
        raise HTTPException(status_code=500, detail=f"Redis error: {e}")

    return {"status": "ok"}