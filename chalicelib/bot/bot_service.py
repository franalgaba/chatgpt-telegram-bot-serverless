import os

import boto3

ERROR_PROMPT = "There has been an error. Please notify the user that there was an issue fetching the bot prompt."
AUDIO_PROMPT = "Your response will be converted to audio, please limit your response to 100 characters and only use words and symbols that can be read aloud."


class BotService:
    def get_bots(self):
        # Retrieve all bots from DynamoDB
        dynamodb = boto3.resource("dynamodb", region_name=os.environ["REGION"])
        table = dynamodb.Table("bots")
        response = table.scan()
        return {
            bot["key"]: {
                "name": bot.get("name"),
                "secret": bot.get("secret"),
                "prompt": bot.get("prompt"),
                "key": bot.get("key"),
                "voice": bot.get("voice"),
            }
            for bot in response["Items"]
        }

    def get_bot(self, chat_key):
        return self.get_bots().get(chat_key)

    def get_chat_prompt(self, chat_key, voice=False):
        try:
            bot = self.get_bot(chat_key)
            prompt = bot["prompt"]
        except Exception:
            prompt = ERROR_PROMPT
        if voice:
            prompt = f"{prompt}. {AUDIO_PROMPT}"
        return prompt
