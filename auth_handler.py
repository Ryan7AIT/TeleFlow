import json
import time
import logging
import requests
import base64
import pickle
from typing import Tuple, Optional, Dict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def encode_cookies(session):
    return base64.b64encode(pickle.dumps(session.cookies.get_dict())).decode()

def decode_cookies(cookie_str):
    return pickle.loads(base64.b64decode(cookie_str.encode()))

class AuthHandler:
    def __init__(self, auth_file: str = "auth_mapping.json"):
        self.auth_file = auth_file
        self._load_auth_data()

    def _load_auth_data(self) -> None:
        """Load authentication data from file."""
        try:
            with open(self.auth_file, 'r') as f:
                self.auth_data = json.load(f)
        except FileNotFoundError:
            self.auth_data = {"telegram_users": {}}
            self._save_auth_data()

    def _save_auth_data(self) -> None:
        """Save authentication data to file."""
        with open(self.auth_file, 'w') as f:
            json.dump(self.auth_data, f, indent=2)

    def is_user_logged_in(self, telegram_id: str) -> bool:
        """Check if user is logged in and cookies exist."""
        user_data = self.auth_data["telegram_users"].get(str(telegram_id))
        if not user_data or "cookies" not in user_data:
            return False
        return True

    def login_user(self, telegram_id: str, username: str, password: str) -> Tuple[bool, str]:
        """Login user and store their cookies if successful."""
        # Check if already logged in
        if self.is_user_logged_in(telegram_id):
            return True, "You are already logged in! You can start using the bot."

        session = requests.Session()
        try:
            resp = session.post(
                "http://backend-v8.test/authentificate",
                data={"email": username, "password": password},
                timeout=10
            )
            # Try to extract _token and success from response JSON
            current_token = None
            success = False
            try:
                resp_json = resp.json()
                current_token = resp_json.get("_token")
                success = resp_json.get("success", False)
            except Exception:
                current_token = None
                success = False
            # Only treat as successful login if status is 200, success is True, and required cookies exist
            if resp.status_code == 200 and success and "XSRF-TOKEN" in session.cookies and "laravel_session" in session.cookies:
                self.auth_data["telegram_users"][str(telegram_id)] = {
                    "system_username": username,
                    "system_password": password,
                    "cookies": encode_cookies(session),
                    "last_login": time.time(),
                    "current_token": current_token
                }
                self._save_auth_data()
                return True, "Login successful! You can now chat with me and use all available commands."
            else:
                logger.error(f"Login failed: {resp.status_code} {resp.text}")
                return False, "Login failed. Please try again."
        except Exception as e:
            logger.error(f"Login failed: {str(e)}")
            return False, "Sorry, I couldn't log you in. Please try again later."

    def get_user_cookies(self, telegram_id: str) -> Optional[dict]:
        user_data = self.auth_data["telegram_users"].get(str(telegram_id))
        if user_data and "cookies" in user_data:
            return decode_cookies(user_data["cookies"])
        return None

    def logout_user(self, telegram_id: str) -> bool:
        """Logout user by removing their entry from the auth file."""
        if str(telegram_id) in self.auth_data["telegram_users"]:
            del self.auth_data["telegram_users"][str(telegram_id)]
            self._save_auth_data()
            return True
        return False 
    
    def get_user_token(self, telegram_id: str) -> Optional[str]:
        """Get user's current token if they're logged in."""
        user_data = self.auth_data["telegram_users"].get(str(telegram_id))
        if user_data:
            return user_data.get("current_token")
        return None 