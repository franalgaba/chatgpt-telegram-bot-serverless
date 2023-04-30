import openai


class AIService:
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
