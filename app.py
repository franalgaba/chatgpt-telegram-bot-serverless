import os
import json
import traceback

from loguru import logger
from chalice import Chalice
from telegram.ext import (
    Dispatcher,
    MessageHandler,
    Filters,
    CommandHandler,
)
from telegram import ParseMode, Update, Bot
from chalice.app import Rate

from chalicelib.utils import generate_transcription, send_typing_action
from chalicelib.chatgpt import ChatGPT

# Telegram token
TOKEN = os.environ["TELEGRAM_TOKEN"]

# Chalice Lambda app

APP_NAME = "chatgpt-telegram-bot"
MESSAGE_HANDLER_LAMBDA = "message-handler-lambda"
TOKEN_REFRESH_HANDLER_LAMBDA = "token-refresh-lambda"

app = Chalice(app_name=APP_NAME)
app.debug = True

chat_gpt_message = ChatGPT()

# Telegram bot
bot = Bot(token=TOKEN)
dispatcher = Dispatcher(bot, None, use_context=True)

#####################
# Telegram Handlers #
#####################


def reset(update, context) -> None:
    chat_gpt_message.reset_chat()
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
    message = chat_gpt_message.ask(transcript_msg)

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
        response_msg = chat_gpt_message.ask(chat_text)
    except Exception as e:
        app.log.error(e)
        app.log.error(traceback.format_exc())
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


@app.schedule(Rate(5, unit=Rate.MINUTES), name=TOKEN_REFRESH_HANDLER_LAMBDA)
def token_handler(event):

    # ChatGPT handler class
    chat_gpt_token = ChatGPT()

    # Refresh token for the message handler Lambda
    message_handler_lambda_name = "-".join([APP_NAME, "dev", MESSAGE_HANDLER_LAMBDA])
    token_handler_lambda_name = "-".join(
        [APP_NAME, "dev", TOKEN_REFRESH_HANDLER_LAMBDA]
    )

    app.log.info(f"Refreshing token for Lambda: {message_handler_lambda_name}")
    chat_gpt_token.set_lambda_name(message_handler_lambda_name)
    chat_gpt_token.refresh_session()

    app.log.info(f"Update token handler for Lambda: {token_handler_lambda_name}")
    # Refresh token for the token refresh handler Lambda
    chat_gpt_token.set_lambda_name(token_handler_lambda_name)
    chat_gpt_token.refresh_session()


@app.lambda_function(name=MESSAGE_HANDLER_LAMBDA)
def message_handler(event, context):

    # ChatGPT handler class
    chat_gpt_message.set_lambda_name(context.function_name)

    dispatcher.add_handler(MessageHandler(Filters.text, process_message))
    dispatcher.add_handler(CommandHandler("reset", reset, filters=Filters.command))
    dispatcher.add_handler(MessageHandler(Filters.voice, process_voice_message))

    try:
        dispatcher.process_update(Update.de_json(json.loads(event["body"]), bot))
    except Exception as e:
        print(e)
        return {"statusCode": 500}

    return {"statusCode": 200}
