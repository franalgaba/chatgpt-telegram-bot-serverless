import os
import json
from functools import wraps

from loguru import logger
from chalice import Chalice
from telegram.ext import Dispatcher, MessageHandler, Filters
from telegram import Update, Bot
from telegram import ChatAction

from chalicelib.chatgpt import ChatGPT

TOKEN = os.environ["TELEGRAM_TOKEN"]

app = Chalice(app_name="chatgpt-telegram-bot-lambda")
app.debug = True

bot = Bot(token=TOKEN)
dispatcher = Dispatcher(bot, None, use_context=True)


def send_typing_action(func):
    """Sends typing action while processing func command."""

    @wraps(func)
    def command_func(update, context, *args, **kwargs):
        context.bot.send_chat_action(
            chat_id=update.effective_message.chat_id, action=ChatAction.TYPING
        )
        return func(update, context, *args, **kwargs)

    return command_func


@send_typing_action
def process_message(update, context):
    chat_id = update.message.chat_id
    chat_text = update.message.text

    chat_gpt = ChatGPT(token=os.environ["CHATGPT_TOKEN"])
    response_msg = chat_gpt.ask(chat_text)
    context.bot.send_message(chat_id=chat_id, text=response_msg)


@app.lambda_function()
def index(event, context):

    dispatcher.add_handler(MessageHandler(Filters.text, process_message))

    try:
        dispatcher.process_update(Update.de_json(json.loads(event["body"]), bot))
    except Exception as e:
        print(e)
        return {"statusCode": 500}

    return {"statusCode": 200}
