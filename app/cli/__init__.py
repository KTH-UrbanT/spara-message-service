# Load chat module
from app.chat import build_chat, ChatArgs

# Formatter for outputs
from pyboxen import boxen

# Make a function to have a chat with OpenAI assistant from a command line
def chat_with_openai():

    # Build chat instance
    chat = build_chat()

    # Print welcome message
    print(boxen(
        "Welcome! That is an OpenAI chat.",
        "To continue enter your request.",
        "To finish enter 'exit'.",
        color="yellow",
        padding=1
        ))

    # Start the chat loop
    while True:
        # Get user input
        user_input = input("User: ")

        # Exit the loop if user enters 'exit'
        if user_input.lower() == 'exit':
            break

        # Generate response from OpenAI assistant
        response = chat.generate_response(user_input)

        # Print the response
        print(boxen(
            response,
            color="green",
            title="bot",
            padding=1,
            margin=(1,0,0,0)
            ))