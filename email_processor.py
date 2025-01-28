import redis
import json
import os
import time
from email.utils import parseaddr

class Email:
    def __init__(self, content, metadata):
        self.content = content
        self.metadata = metadata

    def extract_question(self):
        """Extracts the question from the email content."""
        return self.content.strip()


class RedisQueueManager:
    def __init__(self, redis_host="127.0.0.1", redis_port=6379):
        self.redis_client = redis.StrictRedis(host=redis_host, port=redis_port, decode_responses=True)

    def thread_exists(self, thread_name):
        """Check if a thread already exists in Redis."""
        return self.redis_client.exists(thread_name)

    def create_thread(self, thread_name, initial_message):
        """Create a new Redis thread with the system prompt and user message."""
        if os.path.exists("prompt.txt"):
            with open("prompt.txt", "r") as file:
                prompt = file.read().strip()
            self.redis_client.rpush(thread_name, json.dumps({"content": prompt, "role": "system"}))
        self.redis_client.rpush(thread_name, json.dumps({"content": initial_message, "role": "user"}))
        print(f"Created new thread: {thread_name}")

    def add_to_thread(self, thread_name, message):
        """Add a message to an existing thread."""
        self.redis_client.rpush(thread_name, json.dumps({"content": message, "role": "user"}))

    def publish_event(self, thread_name):
        """Publish an event to notify the processing system."""
        self.redis_client.publish("thread_events", json.dumps({"event": "message_added", "thread_name": thread_name}))

    def read_response(self, thread_name):
        """Read the latest response from the Redis thread."""
        messages = self.redis_client.lrange(thread_name, 0, -1)
        if messages:
            return json.loads(messages[-1])  # Return the latest response
        return None


class EmailProcessor:
    def __init__(self, redis_manager):
        self.redis_manager = redis_manager
        self.email_queue = []

    def check_mailbox(self):
        """Simulate checking a functional mailbox for new emails."""
        # Simulated email check - in practice, fetch from IMAP/SMTP or API
        new_email = {
            "from": "user@example.com",
            "subject": "Question about the service",
            "body": "Kan jag minska elanvändningen genom att använda energieffektiva apparater?"
        }
        print("New email received.")
        self.add_to_queue(Email(new_email["body"], new_email))

    def add_to_queue(self, email):
        """Add new email to processing queue."""
        self.email_queue.append(email)

    def process_queue(self):
        """Process all emails in the queue."""
        while self.email_queue:
            email = self.email_queue.pop(0)
            thread_name = self.get_thread_name(email)
            question = email.extract_question()

            if self.redis_manager.thread_exists(thread_name):
                self.redis_manager.add_to_thread(thread_name, question)
                print(f"Added message to existing thread: {thread_name}")
            else:
                self.redis_manager.create_thread(thread_name, question)

            self.redis_manager.publish_event(thread_name)

            response = self.redis_manager.read_response(thread_name)
            if response:
                EmailSender.send_response(email, response["content"])

    def get_thread_name(self, email):
        """Generate a unique thread name based on email metadata."""
        return f"thread_{parseaddr(email.metadata['from'])[1]}"


class EmailSender:
    @staticmethod
    def send_response(email, response):
        """Simulate sending a response via email."""
        print(f"Sending response to {email.metadata['from']}: {response}")


if __name__ == "__main__":
    redis_manager = RedisQueueManager()
    email_processor = EmailProcessor(redis_manager)

    # Simulate checking for emails in a loop
    while True:
        email_processor.check_mailbox()
        email_processor.process_queue()
        time.sleep(30)  # Check mailbox every 30 seconds
