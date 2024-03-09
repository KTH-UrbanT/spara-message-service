# Load environment variables
from dotenv import load_dotenv

# Simple OpenAI GPT-3 chatbot for CLI testing
from openai import OpenAI

load_dotenv()
client = OpenAI()

class Chat:
    def __init__(self, model="gpt-3.5-turbo", temperature=0.7, max_tokens=150, stop=None):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.stop = stop

    def generate_response(self, prompt):
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": "You are a helpful assistant."},
                          {"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stop=self.stop
            )
            return response.choices[0].message.content
        except Exception as e:
            return str(e)

def build_chat(model="gpt-3.5-turbo"):
    return Chat(model=model)
