import uuid
import os
import json

import boto3
import requests
from loguru import logger


class ChatGPT:
    def __init__(self, session_token) -> None:
        self.token = None
        self.session_token = session_token
        self.conversation_id = None
        self.parent_id = str(uuid.uuid4())
        self.lambda_client = boto3.client("lambda")
        self.lambda_name = None

    def set_lambda_name(self, name):
        self.lambda_name = name

    def reset_chat(self):
        self.conversation_id = None
        self.parent_id = str(uuid.uuid4())

    def _refresh_session(self):
        s = requests.Session()
        # Set cookies
        s.cookies.set("__Secure-next-auth.session-token", self.session_token)
        response = s.get("https://chat.openai.com/api/auth/session")
        try:
            self.session_token = response.cookies.get(
                "__Secure-next-auth.session-token"
            )
            self.token = response.json()["accessToken"]
            self.lambda_client.update_function_configuration(
                FunctionName=self.lambda_name,
                Environment={
                    "Variables": {
                        "CHATGPT_TOKEN": self.token,
                        "CHATGPT_SESSION_TOKEN": self.session_token,
                        "TELEGRAM_TOKEN": os.environ["TELEGRAM_TOKEN"],
                        "VOICE_MESSAGES_BUCKET": os.environ["VOICE_MESSAGES_BUCKET"],
                    }
                },
            )
            logger.info("Session token updated!")
        except Exception as e:
            logger.error(e)
            logger.error("Error refreshing session")

    def ask(self, text):
        self._refresh_session()

        headers = {
            "Referer": "https://chat.openai.com/chat",
            "Origin": "https://chat.openai.com",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15",
            "X-OpenAI-Assistant-App-Id": "",
            "Accept": "text/event-stream",
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        data = {
            "action": "next",
            "messages": [
                {
                    "id": str(uuid.uuid4()),
                    "role": "user",
                    "content": {"content_type": "text", "parts": [text]},
                }
            ],
            "parent_message_id": self.parent_id,
            "model": "text-davinci-002-render",
        }
        if self.conversation_id is not None:
            data["conversation_id"] = self.conversation_id
        try:
            response = requests.post(
                "https://chat.openai.com/backend-api/conversation",
                headers=headers,
                data=json.dumps(data),
            )
        except Exception as e:
            logger.info(e)
            raise e

        if response.status_code == 401:
            message = (
                "The token for your ChatGPT session expired! Please, get a new one."
            )
        else:
            response = response.text.splitlines()[-4]
            if "data: " in response:
                single_response = json.loads(response[6:])
            else:
                single_response = json.loads(response)
            self.parent_id = single_response["message"]["id"]
            self.conversation_id = single_response["conversation_id"]
            message = single_response["message"]["content"]["parts"][0]
            logger.info(f"ChatGPT message: {message}")

        return message
