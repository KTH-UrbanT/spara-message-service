from flask import Flask
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
socketio = SocketIO(app, cors_allowed_origins="*")

# In-memory storage for messages
messages_history = []

@app.route('/')
def index():
    return "SPARA server is running"

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

if __name__ == '__main__':
    socketio.run(app,
                 host='0.0.0.0',
                 port=2345,
                 debug=True
                 )
