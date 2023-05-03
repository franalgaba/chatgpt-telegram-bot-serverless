import openai
from loguru import logger


class AIService:
    def __init__(self) -> None:
        from chalicelib.bot.bot_service import BotService
        from chalicelib.message.message_service import MessageService

        self.message_service = MessageService()
        self.bot_service = BotService()

    def ask_chatgpt(self, text, old_messages):
        formatted_old_messages = [
            {
                "role": message.get("role"),
                "content": message.get("text"),
            }
            for message in old_messages
        ]
        message = openai.ChatCompletion.create(
            model="gpt-4",
            messages=formatted_old_messages
            + [
                {
                    "role": "assistant",
                    "content": text,
                },
            ],
        )
        logger.info(message)
        return message["choices"][0]["message"]["content"]

    def orchestrate_message(self, chat_id, user_message, voice=False):
        chat_key = self.message_service.to_chat_key(chat_id)
        old_messages = self.message_service.fetch_old_messages(chat_id)

        self.message_service.store_message(chat_id, user_message, "user")

        prompt = self.bot_service.get_chat_prompt(chat_key, voice)
        old_messages.insert(0, {"role": "system", "text": prompt})

        response_message = self.ask_chatgpt(user_message, old_messages)

        self.message_service.store_message(chat_id, response_message, "assistant")

        return response_message
