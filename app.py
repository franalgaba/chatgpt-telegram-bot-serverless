import os
import json

from loguru import logger
from chalice import Chalice
from telegram.ext import (
    Dispatcher,
    MessageHandler,
    Filters,
    CommandHandler,
)
from telegram import ParseMode, Update, Bot

from chalicelib.utils import generate_transcription, send_typing_action
from chalicelib.chatgpt import ChatGPT

# Telegram token
TOKEN = os.environ["TELEGRAM_TOKEN"]

# Chalice Lambda app
app = Chalice(app_name="chatgpt-telegram-bot-lambda")
app.debug = True

# Telegram bot
bot = Bot(token=TOKEN)
dispatcher = Dispatcher(bot, None, use_context=True)

# ChatGPT handler class
chat_gpt = ChatGPT(session_token=os.environ["CHATGPT_SESSION_TOKEN"])


#####################
# Telegram Handlers #
#####################


def reset(update, context) -> None:
    chat_gpt.reset_chat()
    context.bot.send_message(
        chat_id=update.message.chat_id, text="Conversation has been reset!"
    )


@send_typing_action
def process_voice_message(update, context):
    # Get the voice message from the update object
    voice_message = update.message.voice
    # Get the file ID of the voice message
    file_id = voice_message.file_id
    # Use the file ID to get the voice message file from Telegram
    file = bot.get_file(file_id)
    # Download the voice message file
    transcript_msg = generate_transcription(file)
    message = chat_gpt.ask(transcript_msg)

    chat_id = update.message.chat_id
    context.bot.send_message(
        chat_id=chat_id,
        text=message,
        parse_mode=ParseMode.MARKDOWN,
    )


@send_typing_action
def process_message(update, context):
    chat_id = update.message.chat_id
    chat_text = update.message.text

    try:
        response_msg = chat_gpt.ask(chat_text)
    except Exception:
        context.bot.send_message(
            chat_id=chat_id,
            text="There was an exception handling your message :(",
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        context.bot.send_message(
            chat_id=chat_id,
            text=response_msg,
            parse_mode=ParseMode.MARKDOWN,
        )


############################
# Lambda Handler functions #
############################


@app.lambda_function()
def index(event, context):

    chat_gpt.set_lambda_name(context.function_name)

    dispatcher.add_handler(MessageHandler(Filters.text, process_message))
    dispatcher.add_handler(CommandHandler("reset", reset, filters=Filters.command))
    dispatcher.add_handler(MessageHandler(Filters.voice, process_voice_message))

    try:
        dispatcher.process_update(Update.de_json(json.loads(event["body"]), bot))
    except Exception as e:
        print(e)
        return {"statusCode": 500}

    return {"statusCode": 200}
