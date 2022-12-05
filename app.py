import os
import json

from loguru import logger
from chalice import Chalice
from telegram.ext import (
    Dispatcher,
    MessageHandler,
    Filters,
    ContextTypes,
    CommandHandler,
)
from telegram import ParseMode, Update, Bot

from chalicelib.utils import send_typing_action
from chalicelib.chatgpt import ChatGPT

TOKEN = os.environ["TELEGRAM_TOKEN"]

app = Chalice(app_name="chatgpt-telegram-bot-lambda")
app.debug = True

bot = Bot(token=TOKEN)
dispatcher = Dispatcher(bot, None, use_context=True)

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
def process_message(update, context):
    chat_id = update.message.chat_id
    chat_text = update.message.text

    response_msg = chat_gpt.ask(chat_text)
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

    try:
        dispatcher.process_update(Update.de_json(json.loads(event["body"]), bot))
    except Exception as e:
        print(e)
        return {"statusCode": 500}

    return {"statusCode": 200}
