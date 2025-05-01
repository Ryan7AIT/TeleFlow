# Shared state and conversation logic for the Telegram bot
import json
import os

# Global state
commands = {}
user_states = {}

def load_commands():
    """Load all command JSON files from the commands directory"""
    global commands
    commands_dir = os.path.join(os.path.dirname(__file__), 'commands')
    for filename in os.listdir(commands_dir):
        if filename.endswith('.json'):
            with open(os.path.join(commands_dir, filename), 'r') as f:
                commands.update(json.load(f))

class ConversationState:
    def __init__(self, command_key):
        self.command_key = command_key
        self.current_step = 0
        self.stored_responses = {}

    def get_current_step(self):
        return commands[self.command_key]["steps"][self.current_step]

    def store_response(self, response):
        current_step = self.get_current_step()
        if current_step.get("store_response"):
            self.stored_responses[current_step["id"]] = response

    def get_summary(self):
        return "\n".join([f"{k}: {v}" for k, v in self.stored_responses.items()]) 