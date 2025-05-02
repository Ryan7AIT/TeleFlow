import os
from typing import Tuple, Optional, Dict, Any
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, MessageHandler as TelegramMessageHandler
from thefuzz import fuzz
from faster_whisper import WhisperModel
import tempfile
import logging
from state import user_states, ConversationState, commands
from auth_handler import AuthHandler
import requests
from telegram.constants import ChatAction

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CustomMessageHandler:
    def __init__(self, commands: dict, bot_username: str, auth_handler: AuthHandler):
        self.commands = commands
        self.bot_username = bot_username
        self.whisper_model = WhisperModel("small", device="cpu", compute_type="int8")
        self.auth_handler = auth_handler
        
    async def process_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Process incoming messages (text or voice) and generate appropriate responses."""
        chat_id = update.message.chat.id
        telegram_id = str(update.effective_user.id)
        if not self.auth_handler.is_user_logged_in(telegram_id):
            await update.message.reply_text("Please type /login to login before using the bot.")
            return
        message_type = update.message.chat.type
        
        # Handle voice messages
        if update.message.voice:
            await self._handle_voice_message(update, context)
            return
            
        # Handle text messages
        text = update.message.text
        logger.info(f'User ({chat_id}) in {message_type}: "{text}"')
        
        # if the bot is in a group chat remove the tag from the message
        if message_type == "group":
            if self.bot_username in text:
                new_text = text.replace(self.bot_username, "").strip()
                response, keyboard = await self._handle_response(new_text, chat_id, telegram_id)
            else:
                return
        else:
            response, keyboard = await self._handle_response(text, chat_id, telegram_id)
            
        logger.info(f"Bot response: {response}")
        await update.message.reply_text(response, reply_markup=keyboard)
        
    async def _handle_voice_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Process voice messages using Faster Whisper."""
        try:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
             
            # Download the voice message
            voice = await update.message.voice.get_file()
            
            # Create a temporary file to store the voice message
            with tempfile.NamedTemporaryFile(delete=False, suffix='.ogg') as temp_file:
                await voice.download_to_drive(temp_file.name)
                
                # Transcribe the voice message
                segments, _ = self.whisper_model.transcribe(temp_file.name)
                transcribed_text = " ".join([segment.text for segment in segments])
                
            # Clean up the temporary file
            os.unlink(temp_file.name)
            
            logger.info(f"Transcribed voice message: {transcribed_text}")
            
            # Process the transcribed text
            response, keyboard = await self._handle_response(transcribed_text, update.message.chat.id, str(update.effective_user.id))
            await update.message.reply_text(
                f"🎤 Transcribed: {transcribed_text}\n\n{response}",
                reply_markup=keyboard
            )
            
        except Exception as e:
            logger.error(f"Error processing voice message: {str(e)}")
            await update.message.reply_text(
                "Sorry, I couldn't process your voice message. Please try again or send a text message."
            )
            
    async def _handle_response(self, text: str, chat_id: int, telegram_id: str) -> Tuple[str, Optional[ReplyKeyboardMarkup]]:
        """Process text responses with fuzzy matching for commands."""
        processed_text = text.lower()
        
        # If user is in conversation, handle as before
        if chat_id in user_states:
            return await self._handle_conversation_state(chat_id, processed_text, telegram_id)
            
        # Try to find the best matching command using fuzzy matching
        best_match = None
        highest_ratio = 0
        
        for command in self.commands.keys():
            ratio = fuzz.ratio(processed_text, command)
            # ratio = fuzz.token_set_ratio(processed_text, command) //TODO: add this instead of just ration
            if ratio > highest_ratio and ratio >= 80:  
                highest_ratio = ratio
                best_match = command
                
        if best_match:
            command_data = self.commands[best_match]
            if command_data["type"] == "simple":
                return command_data["response"], None
            elif command_data["type"] == "conversation":
                user_states[chat_id] = ConversationState(best_match)
                first_step = command_data["steps"][0]
                keyboard = self._create_keyboard(first_step)
                return first_step["bot"], keyboard
            elif command_data["type"] == "api_request":
                user_states[chat_id] = ConversationState(best_match)
                first_step = command_data["steps"][0]
                keyboard = self._create_keyboard(first_step)
                return first_step["bot"], keyboard
                
        return "I don't understand what you said.", None
        
    def _create_keyboard(self, step: dict) -> Optional[ReplyKeyboardMarkup]:
        """Create a keyboard markup if the step has expected responses."""
        if "expect" in step:
            return ReplyKeyboardMarkup(
                [[option] for option in step["expect"]],
                one_time_keyboard=True
            )
        return None
        
    async def _handle_api_request(self, step: dict, telegram_id: str, chat_id: int) -> Tuple[str, Dict[str, Any]]:
        """Handle API requests defined in the command steps, including user cookies and CSRF for Laravel."""
        api_config = step["api"]
        payload = api_config.get("payload", {})
        if not isinstance(payload, dict):
            payload = {}
        # Get user cookies
        cookies = self.auth_handler.get_user_cookies(telegram_id)
        if not cookies:
            return "You are not logged in.", None
        session = requests.Session()
        session.cookies.update(cookies)
        
        # Set headers with proper CSRF token
        headers = dict(api_config.get("headers", {}))
        headers["Accept"] = "application/json"
        
        # Get the user's stored responses from the conversation state
        state = user_states.get(chat_id)
        if state:
            user_data = state.responses  # This should be a dict of {step_id: user_value}
            # Replace placeholders in the payload
            payload = {k: v.format(**user_data) if isinstance(v, str) else v for k, v in payload.items()}
        
        try:
            if api_config["method"].upper() == "GET":
                resp = session.get(api_config["url"], params=payload, headers=headers, timeout=10)
            else:
                token = self.auth_handler.get_user_token(telegram_id)
                if token:
                    payload["_token"] = token
                resp = session.request(api_config["method"], api_config["url"], json=payload, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return self._format_api_response(data, step["response_format"])
            elif resp.status_code == 419:
                # CSRF token mismatch/session expired: log out user and notify
                self.auth_handler.logout_user(telegram_id)
                return ("Your session has expired (CSRF token mismatch). Please type /login to login again.", None)
            else:
                logger.error(f"API error {resp.status_code}: {resp.text}")
                return step['response_format']['error_message'], None
        except requests.Timeout:
            logger.error("API request timed out.")
            return step['response_format']['error_message'], None
        except Exception as e:
            logger.error(f"API request failed: {str(e)}")
            return step['response_format']['error_message'], None

    def _format_api_response(self, data: Dict[str, Any], format_config: dict) -> Tuple[str, Optional[Dict[str, Any]]]:
        """
        Format API response according to the defined format rules.

        Args:
            data: The raw data returned from the API (usually a dict, sometimes with a 'data' key containing a list).
            format_config: The formatting configuration from the command step, including templates and messages.
            

        Returns:
            A tuple of (formatted_message, None). If formatting fails, returns (error_message, None).
        """
        try:
            formatted_parts = {}
            # Iterate over each formatting rule defined in the response_format in the json file for the command
            for key, rules in format_config["format_rules"].items():
                # If the API response is a dict and contains a 'data' key, use its value (often a list of items)
                # Otherwise, use the data as-is (could be a dict or list)
                items = data.get("data") if isinstance(data, dict) and "data" in data else data

                if isinstance(items, list):
                    if not items:
                        # If the list is empty, use the message or error_message
                        formatted_parts[key] = data.get("message") or format_config.get("error_message", "No data returned.")
                    else:
                        formatted_items = []
                        for item in items:
                            if isinstance(item, dict):
                                formatted_items.append(rules["template"].format(**item))
                            else:
                                formatted_items.append(str(item))
                        formatted_parts[key] = rules["join_with"].join(formatted_items)
                elif isinstance(items, dict):
                    formatted_parts[key] = rules["template"].format(**items)
                else:
                    # Fallback: just use the message or string representation
                    formatted_parts[key] = data.get("message") or str(items)
            # Insert the formatted parts into the success message template
            return format_config["success_message"].format(**formatted_parts), None
        except Exception as e:
            # If anything goes wrong (e.g., missing keys), log the error and return the error message
            logger.error(f"Response formatting failed: {str(e)}")
            return format_config["error_message"], None

    async def _handle_conversation_state(self, chat_id: int, text: str, telegram_id: str) -> Tuple[str, Optional[ReplyKeyboardMarkup]]:
        """Handle ongoing conversations."""
        state = user_states[chat_id]
        current_step = state.get_current_step()
        command_data = self.commands[state.command_key]

        # 1. First, validate the response if expectations exist
        if "expect" in current_step and text not in current_step["expect"]:
            valid_options = ", ".join(current_step["expect"])
            return f"Please choose one of: {valid_options}", ReplyKeyboardMarkup(
                [[option] for option in current_step["expect"]], 
                one_time_keyboard=True
            )

        # 2. Store response if needed
        if current_step.get("store_response", False):
            state.store_response(text)

        # 3. Handle navigation logic
        next_step = None
        response_text = None


# // TODO: test this one to print the goto step title
        # if "responses" in current_step and text in current_step["responses"]:
        #     response_text = current_step["responses"][text]
        # else:
        #     response_text = None

        # 3.1 Handle goto logic (including field updates)
        if "goto" in current_step and text in current_step["goto"]:
            target_id = current_step["goto"][text]
            # Find the target step
            for i, step in enumerate(command_data["steps"]):
                if step["id"] == target_id:
                    state.current_step = i
                    next_step = step
                    # If moving to a field from field_to_update, set the flag
                    if current_step["id"] == "field_to_update":
                        state._from_field_to_update = True
                    break

        # 3.2 Handle responses (like confirmation yes/no)
        # TODO: siech 3.1 with 3.2
        elif "responses" in current_step:
            if text in current_step["responses"]:
                response_text = current_step["responses"][text]
                # If there's a goto for this response, use it
                if "goto" in current_step and text in current_step["goto"]:
                    target_id = current_step["goto"][text]
                    for i, step in enumerate(command_data["steps"]):
                        if step["id"] == target_id:
                            state.current_step = i
                            next_step = step
                            break
                # If no goto but is_final, end conversation
                elif "is_final" in current_step:
                    del user_states[chat_id]
                    return response_text, ReplyKeyboardRemove()
                # Otherwise, move to next step
                else:
                    state.current_step += 1
                    next_step = state.get_current_step()

# //TODO: update the check with hardcoded fields with an updatble  parmater from the commnad or  use the store_response from the commands
        # 3.3 Handle field updates (return to confirmation after update)
        elif current_step["id"] in ["name", "email", "phone", "address", "company"] and hasattr(state, "_from_field_to_update") and state._from_field_to_update:
            state._from_field_to_update = False
            # Find confirmation step
            for i, step in enumerate(command_data["steps"]):
                if step["id"] == "confirmation":
                    state.current_step = i
                    next_step = step
                    break

        # 3.4 Default behavior: move to next step if none of the above applied
        elif next_step is None and not current_step.get("is_final", False):
            state.current_step += 1
            next_step = state.get_current_step()

        # 4. Handle the next step
        if next_step:
            # 4.1 If it's an API step, handle it immediately
            if "api" in next_step:
                response, keyboard = await self._handle_api_request(next_step, telegram_id, chat_id)
                if "is_final" in next_step:
                    del user_states[chat_id]
                return response, keyboard

            # 4.2 Prepare the response for the next step
            bot_response = next_step["bot"]
            if "{summary}" in bot_response:
                bot_response = bot_response.replace("{summary}", state.get_summary())
            
            # Add the previous response text if it exists
            if response_text:
                bot_response = f"{response_text}\n\n{bot_response}"

            # Create keyboard if needed
            keyboard = self._create_keyboard(next_step)
            return bot_response, keyboard

        # 5. Fallback: if we somehow got here without a next step
        return "I'm not sure what to do next. Let's start over.", None