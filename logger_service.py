import json
import os
import time
import logging
from datetime import datetime
import langdetect
from typing import Dict, Any, Optional, Union
import uuid

class LoggerService:
    """Advanced structured logging for telegram bot interactions."""
    
    def __init__(self, log_dir="logs"):
        """Initialize the logger service.
        
        Args:
            log_dir: Directory to store log files
        """
        self.log_dir = log_dir
        
        # Create logs directory if it doesn't exist
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        # Setup file paths
        date_str = datetime.now().strftime("%Y-%m-%d")
        self.log_file = os.path.join(log_dir, f"bot_interactions_{date_str}.jsonl")
        
        # Configure standard logging
        self.logger = logging.getLogger("bot_logger")
        if not self.logger.handlers:
            self.logger.setLevel(logging.INFO)
            handler = logging.FileHandler(os.path.join(log_dir, f"bot_system_{date_str}.log"))
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            
        self.logger.info("Logger service initialized")
    
    def detect_language(self, text: str) -> str:
        """Detect the language of the input text.
        
        Args:
            text: The text to analyze
            
        Returns:
            ISO language code (e.g., 'en', 'fr', 'ar')
        """
        try:
            return langdetect.detect(text)
        except:
            return "unknown"
    
    def log_interaction(self, 
                       user_id: str,
                       username: Optional[str] = None,
                       chat_id: Optional[int] = None,
                       chat_type: Optional[str] = None,
                       message_type: str = "text",
                       user_message: Optional[str] = None,
                       bot_response: Optional[str] = None,
                       command_matched: Optional[str] = None,
                       match_score: Optional[float] = None,
                       match_method: Optional[str] = None,
                       processing_time: Optional[float] = None,
                       is_in_conversation: bool = False,
                       conversation_state: Optional[Dict[str, Any]] = None,
                       language: Optional[str] = None,
                       custom_data: Optional[Dict[str, Any]] = None) -> None:
        """Log a detailed record of a bot interaction.
        
        Args:
            user_id: Telegram user ID
            username: Telegram username if available
            chat_id: The ID of the chat
            chat_type: Type of chat (private, group, etc.)
            message_type: Type of message (text, voice, etc.)
            user_message: The actual message from the user
            bot_response: The response sent by the bot
            command_matched: Which command was matched
            match_score: Confidence score of the match
            match_method: How the match was determined (semantic, fuzzy, combined)
            processing_time: How long it took to process the message (ms)
            is_in_conversation: Whether this is part of a multi-step conversation
            conversation_state: Current state of the conversation if applicable
            language: Detected language of the message
            custom_data: Any additional data to log
        """
        # Detect language if not provided and message exists
        if language is None and user_message:
            language = self.detect_language(user_message)
            
        # Create a structured log entry
        log_entry = {
            "interaction_id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "unix_timestamp": time.time(),
            "user": {
                "user_id": user_id,
                "username": username
            },
            "chat": {
                "chat_id": chat_id,
                "chat_type": chat_type
            },
            "message": {
                "type": message_type,
                "content": user_message,
                "language": language,
                "length": len(user_message) if user_message else 0
            },
            "bot_response": {
                "content": bot_response,
                "length": len(bot_response) if bot_response else 0
            },
            "matching": {
                "command_matched": command_matched,
                "score": match_score,
                "method": match_method,
                "processing_time_ms": processing_time
            },
            "conversation": {
                "is_in_conversation": is_in_conversation,
                "state": conversation_state
            }
        }
        
        # Add any custom data
        if custom_data:
            log_entry["custom"] = custom_data
            
        # Write to the JSONL file
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        except Exception as e:
            self.logger.error(f"Failed to write interaction log: {str(e)}")
            
    def log_error(self, error_type: str, error_message: str, 
                 user_id: Optional[str] = None, 
                 chat_id: Optional[int] = None,
                 context: Optional[Dict[str, Any]] = None) -> None:
        """Log an error that occurred during bot operation.
        
        Args:
            error_type: Type of error
            error_message: Error message
            user_id: User ID if applicable
            chat_id: Chat ID if applicable
            context: Additional context for the error
        """
        log_entry = {
            "error_id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "unix_timestamp": time.time(),
            "error": {
                "type": error_type,
                "message": error_message
            },
            "user_id": user_id,
            "chat_id": chat_id,
            "context": context or {}
        }
        
        # Log to both the structured log and the system log
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        except Exception as e:
            pass  # If we can't write to the file, there's not much we can do
            
        self.logger.error(f"Error: {error_type} - {error_message} - User: {user_id} - Chat: {chat_id}")
        
    def get_daily_stats(self) -> Dict[str, Any]:
        """Calculate daily statistics from the current log file.
        
        Returns:
            Dictionary containing statistics about today's interactions
        """
        stats = {
            "total_interactions": 0,
            "unique_users": set(),
            "message_types": {},
            "languages": {},
            "commands_matched": {},
            "avg_processing_time": 0,
            "errors": 0
        }
        
        try:
            if not os.path.exists(self.log_file):
                return stats
                
            total_time = 0
            with open(self.log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        stats["total_interactions"] += 1
                        
                        # Add user ID to unique users
                        if "user" in entry and "user_id" in entry["user"]:
                            stats["unique_users"].add(entry["user"]["user_id"])
                            
                        # Count message types
                        if "message" in entry and "type" in entry["message"]:
                            msg_type = entry["message"]["type"]
                            stats["message_types"][msg_type] = stats["message_types"].get(msg_type, 0) + 1
                            
                        # Count languages
                        if "message" in entry and "language" in entry["message"]:
                            lang = entry["message"]["language"]
                            if lang:
                                stats["languages"][lang] = stats["languages"].get(lang, 0) + 1
                                
                        # Count commands matched
                        if "matching" in entry and "command_matched" in entry["matching"]:
                            cmd = entry["matching"]["command_matched"]
                            if cmd:
                                stats["commands_matched"][cmd] = stats["commands_matched"].get(cmd, 0) + 1
                                
                        # Sum processing times
                        if "matching" in entry and "processing_time_ms" in entry["matching"]:
                            time_ms = entry["matching"]["processing_time_ms"]
                            if time_ms:
                                total_time += time_ms
                                
                        # Count errors
                        if "error" in entry:
                            stats["errors"] += 1
                    except:
                        continue
                        
            # Calculate average processing time
            if stats["total_interactions"] > 0:
                stats["avg_processing_time"] = total_time / stats["total_interactions"]
                
            # Convert set to count for unique users
            stats["unique_users"] = len(stats["unique_users"])
            
            return stats
        except Exception as e:
            self.logger.error(f"Failed to generate daily stats: {str(e)}")
            return stats
            
    def export_logs(self, start_date: str, end_date: str, output_file: str) -> bool:
        """Export logs for a specific date range to a single file.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            output_file: Path to output file
            
        Returns:
            True if export was successful, False otherwise
        """
        try:
            # Convert dates to datetime objects
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
            
            # Create a list of dates in the range
            dates = []
            current = start
            while current <= end:
                dates.append(current.strftime("%Y-%m-%d"))
                current = current.replace(day=current.day + 1)
                
            # Open output file
            with open(output_file, 'w', encoding='utf-8') as out:
                # Iterate over each date
                for date in dates:
                    log_file = os.path.join(self.log_dir, f"bot_interactions_{date}.jsonl")
                    if os.path.exists(log_file):
                        with open(log_file, 'r', encoding='utf-8') as f:
                            for line in f:
                                out.write(line)
                                
            return True
        except Exception as e:
            self.logger.error(f"Failed to export logs: {str(e)}")
            return False 