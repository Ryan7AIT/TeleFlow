# Telegram Bot with Voice Recognition

A flexible Telegram bot that supports text commands, voice messages, and multi-step conversations with fuzzy command matching.

## Features

- Text command processing with fuzzy matching (80% similarity threshold)
- Voice message recognition using Faster Whisper
- Multi-step conversations with user input validation
- Custom keyboard options for guided interactions
- Response storage and summary generation
- Conversation reset functionality
- User authentication with token management
- Secure login process with credential storage

## Project Structure

```
telegram_bot/
├── commands/
│   ├── basic_commands.json    # Command definitions
│   └── api_commands.json      # API-based command definitions
├── main.py                    # Bot initialization and setup
├── message_handler.py         # Message processing logic
├── auth_handler.py           # Authentication management
├── state.py                   # Shared state management
├── auth_mapping.json         # User authentication data
└── requirements.txt           # Project dependencies
```

## File Descriptions

### main.py
- Bot initialization and configuration
- Command handler registration
- Error handling setup
- Login conversation flow
- Application entry point

### message_handler.py
- CustomMessageHandler class for processing messages
- Voice message transcription using Faster Whisper
- Text message processing with fuzzy matching
- Conversation state management
- Keyboard creation for interactive responses

### auth_handler.py
- User authentication management
- Token storage and retrieval
- Login state tracking
- Secure credential handling

### state.py
- Shared state management (commands and user states)
- ConversationState class for managing multi-step conversations
- Command loading functionality

### commands/basic_commands.json
- JSON-based command definitions
- Supports both simple and conversation-based commands

### commands/api_commands.json
- API-based command definitions
- Endpoint configurations
- Response formatting rules

## message_handler.py: Message Processing and Conversation Logic

This module is responsible for all message processing, command matching, and multi-step conversation handling in the bot. It supports both text and voice messages, and manages dynamic, stateful conversations with users.

### General Workflow
1. **Message Reception**: Receives text or voice messages from users.
2. **Authentication Check**: Ensures the user is logged in before processing commands.
3. **Command Matching**: Uses fuzzy matching to identify the intended command from user input.
4. **Conversation State Management**: Handles multi-step conversations, storing user responses and managing the flow between steps.
5. **Dynamic Keyboards**: Presents reply keyboards for expected responses/options.
6. **API Integration**: Handles steps that require backend API calls, including formatting and presenting results.
7. **Voice Recognition**: Transcribes voice messages using Faster Whisper and processes them as text.

### Main Functions
- **CustomMessageHandler**: Main class that encapsulates all message handling logic.
  - `process_message`: Entry point for all incoming messages. Routes to text or voice handling, checks authentication, and manages group vs. private chat logic.
  - `_handle_voice_message`: Downloads, transcribes, and processes voice messages.
  - `_handle_response`: Matches user input to commands using fuzzy logic, and starts or continues conversations.
  - `_handle_conversation_state`: Core function for managing multi-step conversations. Handles storing responses, navigating between steps, updating fields, confirming data, and triggering API calls. Ensures robust and dynamic flow for all command types.
  - `_create_keyboard`: Generates reply keyboards for steps that expect specific responses.
  - `_handle_api_request`: Manages API requests for steps that require backend interaction, including payload construction, authentication, and response formatting.
  - `_format_api_response`: Formats API responses according to rules defined in the command JSON files.

### Conversation Flow Example
- User sends a command (text or voice)
- Bot matches the command and starts a conversation (if needed)
- For each step:
  - Bot asks a question or presents options
  - User responds (with text or by choosing an option)
  - Bot stores the response and moves to the next step, or returns to confirmation if updating a field
  - If a step requires an API call, the bot sends the request and presents the result
- Conversation ends when all steps are complete or the user cancels

This design allows for flexible, dynamic, and robust conversational flows, supporting both simple and complex command structures defined in JSON files.

## Authentication System

The bot implements a secure authentication system with the following features:

### Login Command (/login)
Users can authenticate using the `/login` command, which:
1. Checks if the user is already logged in
2. If not, prompts for username and password
3. Validates credentials with the backend
4. Stores authentication token securely
5. Manages login state

### Security Features
- Passwords are immediately deleted from chat
- Credentials are stored securely in auth_mapping.json
- Token-based authentication
- Session management
- Automatic login state checking

### auth_mapping.json Structure
```json
{
  "telegram_users": {
    "telegram_id": {
      "system_username": "username",
      "system_password": "password",
      "current_token": "auth_token",
      "last_login": timestamp
    }
  }
}
```

## Workflow

1. **Bot Initialization**
   - Load commands from JSON files
   - Initialize message handler
   - Set up command handlers
   - Start polling for updates

2. **Message Processing**
   - Receive message (text or voice)
   - For voice messages:
     1. Download and save temporarily
     2. Transcribe using Faster Whisper
     3. Process transcribed text
   - For text messages:
     1. Apply fuzzy matching to find matching command
     2. Execute command or continue conversation

3. **Command Execution**
   - Simple commands: Return immediate response
   - Conversation commands:
     1. Initialize conversation state
     2. Present user with prompts/options
     3. Validate responses
     4. Store responses if needed
     5. Generate summaries
     6. Handle completion

## How to Add New Features

### 1. Adding New Commands
Add new commands in the `commands` directory JSON files:

```json
{
    "command_name": {
        "type": "simple",
        "response": "Your response here"
    }
}
```

Or for conversations:

```json
{
    "command_name": {
        "type": "conversation",
        "steps": [
            {
                "id": "step1",
                "bot": "Question text?",
                "store_response": true,
                "expect": ["option1", "option2"]  // Optional
            }
        ]
    }
}
```

### 2. Adding New Message Types
To support new message types:

1. Update `message_handler.py`:
   - Add new handler method
   - Implement processing logic
   - Update `process_message()` to handle new type

2. Update `main.py`:
   - Add new filter to MessageHandler if needed

### 3. Adding New Features
To add new functionality:

1. For new state management:
   - Add to `state.py`

2. For new message processing:
   - Extend `CustomMessageHandler` in `message_handler.py`

3. For new commands:
   - Add handler in `main.py`
   - Add command definition in commands JSON

## Dependencies

```
python-telegram-bot
faster-whisper
thefuzz
requests
pydantic
loguru
python-dotenv
ffmpeg-python
```

## Setup and Running

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure your bot token in `main.py`

3. Run the bot:
```bash
python main.py
```

## Best Practices for Extensions

1. **Command Definitions**
   - Keep commands organized in separate JSON files
   - Use clear, descriptive command names
   - Document expected responses and validations

2. **State Management**
   - Add new state variables to `state.py`
   - Use proper type hints
   - Document state transitions

3. **Message Processing**
   - Follow existing error handling patterns
   - Log important events
   - Clean up temporary files
   - Validate user inputs

4. **Testing**
   - Test new commands with various inputs
   - Verify voice recognition accuracy
   - Test conversation flows
   - Ensure proper error handling