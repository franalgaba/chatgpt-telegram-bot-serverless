import datetime
import json
import os
import traceback
import uuid

import boto3
import openai
from boto3.dynamodb.conditions import Attr, Key
from chalice import Chalice
from chalice.app import Rate
from loguru import logger
from telegram import Bot, ParseMode, Update
from telegram.ext import CommandHandler, Dispatcher, Filters, MessageHandler

from chalicelib.utils import generate_transcription, send_typing_action

# Telegram token
TOKEN = os.environ["TELEGRAM_TOKEN"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

# Chalice Lambda app

APP_NAME = "chatgpt-telegram-bot"
MESSAGE_HANDLER_LAMBDA = "message-handler-lambda"

app = Chalice(app_name=APP_NAME)
app.debug = True

# Telegram bot
bot = Bot(token=TOKEN)
dispatcher = Dispatcher(bot, None, use_context=True)


def message_guid():
    """Generate a random guid for message key"""
    return str(uuid.uuid4())


#####################
# Telegram Handlers #
#####################


def ask_chatgpt(text, old_messages):
    formatted_old_messages = [
        {
            "role": message.get("role"),
            "content": message.get("text"),
        }
        for message in old_messages
    ]
    message = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
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
    message = ask_chatgpt(transcript_msg)

    chat_id = update.message.chat_id
    context.bot.send_message(
        chat_id=chat_id,
        text=message,
        parse_mode=ParseMode.MARKDOWN,
    )


@send_typing_action
def process_message(update, context):
    dynamodb = boto3.resource("dynamodb", region_name="ca-central-1")
    table = dynamodb.Table("message")

    chat_id = update.message.chat_id
    db_chat_id = f"chat_{chat_id}"
    chat_text = update.message.text
    created_at = int(datetime.datetime.now().timestamp())

    response = table.scan(FilterExpression=Attr("chat_id").eq(db_chat_id))
    old_messages = response["Items"]

    if chat_text == "/clear":
        for message in old_messages:
            table.delete_item(
                Key={
                    "message_key": message["message_key"],
                    "created_at": message["created_at"],
                }
            )
        context.bot.send_message(
            chat_id=chat_id,
            text="Chat cleared",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    table.put_item(
        Item={
            "message_key": message_guid(),
            "chat_id": db_chat_id,
            "role": "user",
            "text": chat_text,
            "created_at": created_at,
        }
    )

    try:
        message = ask_chatgpt(chat_text, old_messages)
        context.bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        app.log.error(e)
        app.log.error(traceback.format_exc())
        context.bot.send_message(
            chat_id=chat_id,
            text=f"There was an exception handling your message :( {e}",
            parse_mode=ParseMode.MARKDOWN,
        )

    try:
        table.put_item(
            Item={
                "message_key": message_guid(),
                "chat_id": db_chat_id,
                "role": "assistant",
                "text": message,
                "created_at": created_at,
            }
        )
    except Exception as e:
        app.log.error(e)
        app.log.error(traceback.format_exc())
        context.bot.send_message(
            chat_id=chat_id,
            text=f"There was an exception storing the bot message :( {e}",
            parse_mode=ParseMode.MARKDOWN,
        )


############################
# Lambda Handler functions #
############################


@app.lambda_function(name=MESSAGE_HANDLER_LAMBDA)
def message_handler(event, context):
    dispatcher.add_handler(MessageHandler(Filters.text, process_message))
    dispatcher.add_handler(MessageHandler(Filters.voice, process_voice_message))

    try:
        dispatcher.process_update(Update.de_json(json.loads(event["body"]), bot))
    except Exception as e:
        print(e)
        return {"statusCode": 500}

    return {"statusCode": 200}
