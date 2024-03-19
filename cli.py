# Load environment variables
from dotenv import load_dotenv

# This is to run the app from the command line
from app.cli import chat_with_openai

from app.cli.memory_playground import my_function

load_dotenv()
my_function()
#chat_with_openai()