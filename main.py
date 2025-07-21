from socket_manager.app import socket_app
from config.settings import MS_HOST, MS_PORT
from events.handlers import *
import uvicorn


if __name__ == "__main__":
    uvicorn.run(socket_app, host=MS_HOST, port=MS_PORT)
