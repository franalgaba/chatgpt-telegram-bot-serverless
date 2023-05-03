from telegram import Bot, ParseMode, Update


class TelegramService:
    def __init__(self, telegram_context):
        self.ctx = telegram_context

    def send_chat_message(self, chat_id, message):
        self.ctx.bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode=ParseMode.MARKDOWN,
        )

    def get_audio_message(self, update):
        # Get the voice message from the update object
        voice_message = update.message.voice
        # Get the file ID of the voice message
        file_id = voice_message.file_id
        # Use the file ID to get the voice message file from Telegram
        file = self.ctx.bot.get_file(file_id)
        return file

    def send_voice_message(self, chat_id, audio_file_path, duration):
        with open(audio_file_path, "rb") as audio_file:
            self.ctx.bot.send_voice(
                chat_id=chat_id, voice=audio_file, duration=duration
            )
