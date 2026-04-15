import os
from dotenv import load_dotenv
from pathlib import Path

# Load .env from project root, two levels up from this file
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)


def _get_bool(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}

MS_HOST = os.getenv("MS_HOST", "localhost")
MS_PORT = int(os.getenv("MS_PORT", 8000))

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

SQL_DB_HOST = os.getenv("SQL_DB_HOST", "localhost")
SQL_DB_PORT = int(os.getenv("SQL_DB_PORT", 5432))
SQL_DB_NAME = os.getenv("SQL_DB_NAME", "message_store")
SQL_DB_USER = os.getenv("SQL_DB_USER", "postgres")
SQL_DB_PASSWORD = os.getenv("SQL_DB_PASSWORD", "postgres")

SOCKETIO_LOGGER = _get_bool("SOCKETIO_LOGGER", False)
SOCKETIO_ENGINEIO_LOGGER = _get_bool("SOCKETIO_ENGINEIO_LOGGER", False)

SESSION_EXPIRATION_TIME = 300  # 300 seconds
