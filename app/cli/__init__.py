# Load environment variables
from dotenv import load_dotenv

# Load chat module
# from app.chat import build_chat, ChatArgs

# Formatter for outputs
from pyboxen import boxen

def cli():
    print(boxen("Hello, World!"), "yellow")