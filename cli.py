# Load environment variables
from dotenv import load_dotenv

# This is to run the app from the command line
from app.cli import chat_with_openai

load_dotenv()
chat_with_openai()