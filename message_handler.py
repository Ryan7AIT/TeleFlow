import os
from typing import Tuple, Optional, Dict, Any
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, MessageHandler as TelegramMessageHandler
from thefuzz import fuzz
from faster_whisper import WhisperModel
import tempfile
import logging
import time
from state import user_states, ConversationState, commands
from auth_handler import AuthHandler
import requests
from telegram.constants import ChatAction
import re
from sentence_transformers import SentenceTransformer, util
from logger_service import LoggerService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CustomMessageHandler:
    def __init__(self, commands: dict, bot_username: str, auth_handler: AuthHandler):
        self.commands = commands
        self.bot_username = bot_username
        self.whisper_model = WhisperModel("small", device="cpu", compute_type="int8")
        self.auth_handler = auth_handler
        
        # Initialize the sentence transformer model
        self.transformer_model = SentenceTransformer('distiluse-base-multilingual-cased-v2')
        
        # Precompute embeddings for all commands and their samples
        self.command_embeddings = []
        self.command_keys = []
        for command_key, command_data in self.commands.items():
            # Encode the command key
            embedding = self.transformer_model.encode(command_key, convert_to_tensor=True)
            self.command_embeddings.append(embedding)
            self.command_keys.append(command_key)
            
            # Encode the samples
            if "samples" in command_data:
                for sample in command_data["samples"]:
                    sample_embedding = self.transformer_model.encode(sample, convert_to_tensor=True)
                    self.command_embeddings.append(sample_embedding)
                    self.command_keys.append(command_key)
        
        # Initialize logger service
        self.log_service = LoggerService()
            
    def _clean_user_input(self, text: str) -> str:
        """Clean up user input by removing common phrases."""
        remove_patterns = [
            # English
            r"what would you like to do\??",
            r"how can i help you.*",
            r"please",
            r"^i(?:'d)? like to",
            r"^can you",
            r"^i want to",
            
            # Add more patterns as needed for your use case
        ]
        
        for pattern in remove_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE).strip()
        return text
        
    async def process_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Process incoming messages (text or voice) and generate appropriate responses."""
        chat_id = update.message.chat.id
        telegram_id = str(update.effective_user.id)
        chat_type = update.message.chat.type
        username = update.effective_user.username
        
        start_time = time.time()
        
        if not self.auth_handler.is_user_logged_in(telegram_id):
            await update.message.reply_text("Please type /login to login before using the bot.")
            
            # Log the unauthorized access attempt
            self.log_service.log_interaction(
                user_id=telegram_id,
                username=username,
                chat_id=chat_id,
                chat_type=chat_type,
                user_message=update.message.text if update.message.text else None,
                bot_response="Please type /login to login before using the bot.",
                is_in_conversation=False,
                custom_data={"auth_status": "unauthorized"}
            )
            return
        
        # Handle voice messages
        if update.message.voice:
            await self._handle_voice_message(update, context)
            return
            
        # Handle text messages
        text = update.message.text
        logger.info(f'User ({chat_id}) in {chat_type}: "{text}"')
        
        # if the bot is in a group chat remove the tag from the message
        if chat_type == "group":
            if self.bot_username in text:
                new_text = text.replace(self.bot_username, "").strip()
                response, keyboard = await self._handle_response(new_text, chat_id, telegram_id, 
                                                            message_type="text",
                                                            chat_type=chat_type,
                                                            username=username)
            else:
                return
        else:
            response, keyboard = await self._handle_response(text, chat_id, telegram_id,
                                                         message_type="text",
                                                         chat_type=chat_type,
                                                         username=username)
        
        logger.info(f"Bot response: {response}")
        await update.message.reply_text(response, reply_markup=keyboard)
        
        # Note: We removed the logging here to avoid double logging
        # The logging is now handled in the _handle_response method
        
    async def _handle_voice_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Process voice messages using Faster Whisper."""
        chat_id = update.message.chat.id
        telegram_id = str(update.effective_user.id)
        chat_type = update.message.chat.type
        username = update.effective_user.username
        
        start_time = time.time()
        transcribed_text = None
        
        try:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
             
            # Download the voice message
            voice = await update.message.voice.get_file()
            voice_duration = update.message.voice.duration
            
            # Create a temporary file to store the voice message
            with tempfile.NamedTemporaryFile(delete=False, suffix='.ogg') as temp_file:
                await voice.download_to_drive(temp_file.name)
                
                # Transcribe the voice message
                segments, info = self.whisper_model.transcribe(temp_file.name)
                transcribed_text = " ".join([segment.text for segment in segments])
                detected_language = info.language
                
            # Clean up the temporary file
            os.unlink(temp_file.name)
            
            logger.info(f"Transcribed voice message: {transcribed_text}")
            
            # Process the transcribed text
            response, keyboard = await self._handle_response(transcribed_text, chat_id, telegram_id, 
                                                          message_type="voice", 
                                                          chat_type=chat_type,
                                                          username=username,
                                                          custom_data={
                                                              "voice_duration": voice_duration,
                                                              "transcription_info": {
                                                                  "language": detected_language,
                                                                  "language_probability": info.language_probability
                                                              }
                                                          },
                                                          detected_language=detected_language)
            
            # Send the response
            await update.message.reply_text(response, reply_markup=keyboard)
            
            # Note: We removed the logging here to avoid double logging
            # The logging is now handled in the _handle_response method with additional voice parameters
            
        except Exception as e:
            error_message = f"Error processing voice message: {str(e)}"
            logger.error(error_message)
            await update.message.reply_text(
                "Sorry, I couldn't process your voice message. Please try again or send a text message."
            )
            
            # Log the error
            self.log_service.log_error(
                error_type="voice_processing_error",
                error_message=str(e),
                user_id=telegram_id,
                chat_id=chat_id,
                context={
                    "transcribed_text": transcribed_text,
                    "chat_type": chat_type
                }
            )
            
    async def _handle_response(self, text: str, chat_id: int, telegram_id: str, message_type: str = "text", custom_data: Optional[Dict[str, Any]] = None, detected_language: Optional[str] = None, chat_type: Optional[str] = None, username: Optional[str] = None) -> Tuple[str, Optional[ReplyKeyboardMarkup]]:
        """Process text responses with semantic matching for commands.
        
        Args:
            text: The text message to process
            chat_id: The chat ID
            telegram_id: The user's telegram ID
            message_type: Type of message ("text" or "voice")
            custom_data: Additional data to include in logging
            detected_language: Detected language for voice messages
            chat_type: The chat type
            username: The username of the user
        """
        if custom_data is None:
            custom_data = {}
            
        start_time = time.time()
        processed_text = text.lower()
        
        # If user is in conversation, handle as before
        if chat_id in user_states:
            response, keyboard = await self._handle_conversation_state(chat_id, processed_text, telegram_id)

            # TODO: REMOVE THIS INTO THE ABOVE FUNCTION CUZ IT IS MAKING AN ERROR DUE TO DELEETD STATE
            # # Get conversation state for logging
            # state = user_states[chat_id]
            # conversation_state = {
            #     "command": state.command_key,
            #     "step": state.current_step,
            #     "responses": state.responses
            # }
            
            # Log the interaction
            # self.log_service.log_interaction(
            #     user_id=telegram_id,
            #     username=username,
            #     chat_id=chat_id,
            #     chat_type=chat_type,
            #     message_type=message_type,
            #     user_message=text,
            #     bot_response=response,
            #     command_matched=state.command_key,
            #     processing_time=(time.time() - start_time) * 1000,
            #     is_in_conversation=True,
            #     conversation_state=conversation_state,
            #     language=detected_language,
            #     custom_data=custom_data
            # )
            
            return response, keyboard
            
        # Try to find the best matching command using semantic matching
        best_match = None
        highest_score = 0
        match_method = None
        cleaned_text = self._clean_user_input(processed_text)
        
        # Semantic matching with SentenceTransformer
        text_embedding = self.transformer_model.encode(cleaned_text, convert_to_tensor=True)
        
        # Calculate semantic similarity score for each command and its samples
        for emb, cmd in zip(self.command_embeddings, self.command_keys):
            semantic_score = util.cos_sim(text_embedding, emb).item()
            
            if semantic_score > highest_score:
                highest_score = semantic_score
                best_match = cmd
                match_method = "semantic"
        
        # Calculate processing time for matching
        matching_time = (time.time() - start_time) * 1000  # ms
                
        if best_match and highest_score > 0.5:  # Set a minimum threshold for matching
            command_data = self.commands[best_match]
            if command_data["type"] == "simple":
                # Log the successful match
                self.log_service.log_interaction(
                    user_id=telegram_id,
                    username=username,
                    chat_id=chat_id,
                    chat_type=chat_type,
                    message_type=message_type,
                    user_message=text,
                    bot_response=command_data["response"],
                    command_matched=best_match,
                    match_score=highest_score,
                    match_method=match_method,
                    processing_time=matching_time,
                    is_in_conversation=False,
                    language=detected_language,
                    custom_data=custom_data
                )
                return command_data["response"], None
            elif command_data["type"] in ("conversation", "api_request"):
                user_states[chat_id] = ConversationState(best_match)
                first_step = command_data["steps"][0]
                keyboard = self._create_keyboard(first_step)
                
                # Log the successful match
                self.log_service.log_interaction(
                    user_id=telegram_id,
                    username=username,
                    chat_id=chat_id,
                    chat_type=chat_type,
                    message_type=message_type,
                    user_message=text,
                    bot_response=first_step["bot"],
                    command_matched=best_match,
                    match_score=highest_score,
                    match_method=match_method,
                    processing_time=matching_time,
                    is_in_conversation=True,
                    conversation_state={"command": best_match, "step": 0},
                    language=detected_language,
                    custom_data=custom_data
                )
                return first_step["bot"], keyboard

        # No match was found or score was below threshold
        default_response = "I don't understand what you said. Could you try again with different wording?"
        
        # Log the failed match attempt
        self.log_service.log_interaction(
            user_id=telegram_id,
            username=username,
            chat_id=chat_id,
            chat_type=chat_type,
            message_type=message_type,
            user_message=text,
            bot_response=default_response,
            command_matched=best_match if highest_score > 0 else None,
            match_score=highest_score if highest_score > 0 else None,
            match_method=match_method,
            processing_time=matching_time,
            is_in_conversation=False,
            language=detected_language,
            custom_data=custom_data
        )
                
        return default_response, None
        
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
        # TODO: switch 3.1 with 3.2
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
        elif  hasattr(state, "_from_field_to_update") and state._from_field_to_update:
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