import os
from dotenv import load_dotenv
from pathlib import Path

# Load .env from project root, two levels up from this file
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

MS_HOST = os.getenv("MS_HOST", "localhost")
MS_PORT = int(os.getenv("MS_PORT", 8000))

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

SQL_DB_HOST = os.getenv("SQL_DB_HOST", "localhost")
SQL_DB_PORT = int(os.getenv("SQL_DB_PORT", 5432))
SQL_DB_NAME = os.getenv("SQL_DB_NAME", "message_store")
SQL_DB_USER = os.getenv("SQL_DB_USER", "postgres")
SQL_DB_PASSWORD = os.getenv("SQL_DB_PASSWORD", "postgres")