# Load environment variables
from dotenv import load_dotenv

# Flask application
from flask import Flask
# SocketIO
from flask_socketio import SocketIO, emit

# Celery
from app.celery import celery_init_app

# Load congigurations
from app.web.config import Config

# Load database
from app.web.db import db, init_db_command
from app.web.db import models

# Load views
from app.web.views import (
    server_views
)


socketio = SocketIO()

def create_app():
    app = Flask(__name__)
    app.url_map.strict_slashes = False
    app.config.from_object(Config)

    socketio.init_app(app, cors_allowed_origins="*")
    register_extensions(app)
    # register_hooks(app)
    register_blueprints(app)
    if Config.CELERY["broker_url"]:
        celery_init_app(app)

    return app

# Blueprints for Flask
def register_blueprints(app):
    app.register_blueprint(server_views.bp)

# Database initialization
def register_extensions(app):
    db.init_app(app)
    app.cli.add_command(init_db_command)

# In-memory storage for messages
messages_history = []

@socketio.on('message')
def handle_message(data):
    # Store the message in history
    messages_history.append(data)
    print('Message received: ' + data)
    # Limit the history size to the last 50 messages or any number you prefer
    if len(messages_history) > 50:
        messages_history.pop(0)
    emit('message', data, broadcast=True)

@socketio.on('connect')
def handle_connect():
    # Send message history to the newly connected client
    for message in messages_history:
        emit('message', message)
