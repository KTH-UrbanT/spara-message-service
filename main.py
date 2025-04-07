from socket_manager.app import app, socket_app
from config.settings import MS_HOST, MS_PORT
from events.scheduled_handler import scheduled_thread_read, EXPIRATION_TIME
from events.handlers import *
import asyncio
import schedule
import uvicorn


# Schedule the job every 300 seconds
schedule.every(EXPIRATION_TIME).seconds.do(scheduled_thread_read)
# schedule.every(30).seconds.do(scheduled_thread_read) # For testing purposes


# Async function to run schedule loop
async def run_scheduler():
    while True:
        schedule.run_pending()
        await asyncio.sleep(30)  # Check every second for pending tasks


# Start scheduler on FastAPI startup
@app.on_event("startup")
async def start_scheduler():
    asyncio.create_task(run_scheduler())  # Runs in the background


if __name__ == "__main__":
    uvicorn.run(socket_app, host=MS_HOST, port=MS_PORT)
