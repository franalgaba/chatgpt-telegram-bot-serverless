import json
import os
import sys
import traceback
from pathlib import Path

import boto3
import openai
from chalice import Chalice
from loguru import logger
from telegram import Bot, Update
from telegram.ext import Dispatcher, Filters, MessageHandler

from chalicelib.ai.ai_service import AIService
from chalicelib.audio.audio_service import AudioService
from chalicelib.bot.bot_service import BotService
from chalicelib.config.config_service import ConfigService
from chalicelib.message.message_service import MessageService
from chalicelib.telegram.telegram_service import TelegramService
from chalicelib.utils import send_typing_action

sys.path.insert(0, str(Path(__file__).resolve().parent))

APP_NAME = "chatgpt-telegram-bot"
MESSAGE_HANDLER_LAMBDA = "message-handler-lambda"
MESSAGE_PROCESS_LAMBDA = "message-process-lambda"

app = Chalice(app_name=APP_NAME)
app.debug = True

ai_service = AIService()
message_service = MessageService()
audio_service = AudioService()
bot_service = BotService()
config_service = ConfigService()


@send_typing_action
def process_message(update, context):
    chat_id = update.message.chat_id
    chat_text = update.message.text
    telegram_service = TelegramService(context)

    if chat_text == "/clear":
        message_service.clear_chat_history(chat_id)
        telegram_service.send_chat_message(chat_id, "Chat cleared")
        return

    try:
        message = ai_service.orchestrate_message(chat_id, chat_text)
        telegram_service.send_chat_message(chat_id, message)
    except Exception as e:
        app.log.error(e)
        app.log.error(traceback.format_exc())
        telegram_service.send_chat_message(
            chat_id, f"There was an error handling your message :( {e}"
        )


@send_typing_action
def process_voice_message(update, context):
    telegram_service = TelegramService(context)
    try:
        chat_id = update.message.chat_id
        chat_key = message_service.to_chat_key(chat_id)

        file = telegram_service.get_audio_message(update)

        transcript_response = audio_service.transcribe_audio(file)

        response_message = ai_service.orchestrate_message(
            chat_id, transcript_response, voice=True
        )

        bot = bot_service.get_bot(chat_key)

        audio_file_path, duration = audio_service.generate_audio_file(
            response_message, voice=bot.get("voice")
        )
        telegram_service.send_voice_message(chat_id, audio_file_path, duration)
    except Exception as e:
        logger.error(e)
        logger.error(traceback.format_exc())
        telegram_service.send_chat_message(
            chat_id, f"There was an error processing your voice message :( {e}"
        )
    finally:
        audio_service.clean_up()


############################
# Lambda Handler functions #
############################


@app.lambda_function(name=MESSAGE_HANDLER_LAMBDA)
def message_handler(event, context):
    lambda_client = boto3.client("lambda")
    try:
        lambda_client.invoke(
            FunctionName="chatgpt-telegram-bot-dev-message-process-lambda",
            InvocationType="Event",
            Payload=json.dumps(event),
        )
        return {"statusCode": 200}
    except Exception as e:
        app.log.error(e)
        return {"statusCode": 500}


@app.lambda_function(name=MESSAGE_PROCESS_LAMBDA)
def message_process(event, context):
    try:
        logger.info(event)
        json_body = json.loads(event["body"])
        if not json_body.get("message"):
            return

        chat_key = message_service.to_chat_key(json_body["message"]["chat"]["id"])
        bot_config = bot_service.get_bot(chat_key)

        if not bot_config:
            logger.error("Unrecognized bot")
            return

        openai.api_key = config_service.get_secret("OPENAI_API_KEY")
        bot = Bot(token=config_service.get_secret(bot_config.get("secret")))
        dispatcher = Dispatcher(bot, None, use_context=True)
        dispatcher.add_handler(MessageHandler(Filters.text, process_message))
        dispatcher.add_handler(MessageHandler(Filters.voice, process_voice_message))

        dispatcher.process_update(Update.de_json(json_body, bot))
    except Exception as e:
        app.log.error(e)
        app.log.error(traceback.format_exc())
