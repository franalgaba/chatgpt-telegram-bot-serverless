import uuid
import json

import requests
from loguru import logger


class ChatGPT:
    def __init__(self, token) -> None:
        self.token = token
        self.conversation_id = None
        self.parent_id = str(uuid.uuid4())

    def _refresh_session(self):
        response = requests.get(
            "https://chat.openai.com/api/auth/session",
        )
        logger.info(response.text)
        self.token = response.json()["accessToken"]

    def ask(self, text):
        # self._refresh_session()

        headers = {
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

        logger.info(f"ChatGPT response non parsed: {response}")
        response = response.text.splitlines()[-4]
        logger.info(f"ChatGPT response parsed: {response}")
        if "data: " in response:
            single_response = json.loads(response[6:])
        else:
            single_response = json.loads(response)
        logger.info(f"ChatGPT response: {single_response}")
        self.parent_id = single_response["message"]["id"]
        self.conversation_id = single_response["conversation_id"]
        message = single_response["message"]["content"]["parts"][0]
        logger.info(f"ChatGPT message: {message}")

        return message
