import os
from flask import Blueprint, send_from_directory, current_app
# Load database
from app.web.db import db, init_db_command
from app.web.db.models import User, Message, Conversation

bp = Blueprint(
    "server",
    __name__,
)

@bp.route("/")
def index():
    return "SPARA server is running"

# Sample database - to be removed
@bp.route("/sample-db")
def sample_db():
    # Create a new user
    user = User(username='testuser', email='testuser@example.com')
    db.session.add(user)
    db.session.commit()

    # Print the id of the new user
    print(user.id)

    # Create a new conversation
    conversation = Conversation()
    db.session.add(conversation)
    db.session.commit()

    # Create a new message
    message = Message(content='Hello, world!', user_id=user.id, conversation_id=conversation.id)
    db.session.add(message)
    db.session.commit()

    # Query the database for the message we just added
    message_from_db = Message.query.get(message.id)
    print(message_from_db.content)

    # Query the database for the user we just added
    user_from_db = User.query.get(user.id)
    print(user_from_db.username)
    return "Sample db"

@bp.route("/<path:path>")
def catch_all(path):
    if path != "" and os.path.exists(os.path.join(current_app.static_folder, path)):
        return send_from_directory(current_app.static_folder, path)
    else:
        return send_from_directory(current_app.static_folder, "index.html")
