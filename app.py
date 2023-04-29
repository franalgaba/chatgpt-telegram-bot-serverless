import datetime
import json
import os
import subprocess
import traceback
import uuid

import boto3
import openai
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError
from chalice import Chalice
from elevenlabs import generate, play, save
from elevenlabs import set_api_key as set_eleven_api_key
from loguru import logger
from telegram import Bot, ParseMode, Update
from telegram.ext import Dispatcher, Filters, MessageHandler

from chalicelib.utils import send_typing_action

os.environ["PATH"] += os.pathsep + os.path.dirname(os.path.realpath(__file__))

APP_NAME = "chatgpt-telegram-bot"
MESSAGE_HANDLER_LAMBDA = "message-handler-lambda"
LOCAL_AUDIO_DOWNLOAD_PATH = "/tmp/input_voice_message.ogg"
LOCAL_AUDIO_CONVERTED_PATH = "/tmp/output_voice_message.mp3"

app = Chalice(app_name=APP_NAME)
app.debug = True


def message_guid():
    """Generate a random guid for message key"""
    return str(uuid.uuid4())


def to_chat_key(chat_id):
    return f"chat_{str(chat_id).replace('-', '')}"


def get_secret(secret_name):
    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(
        service_name="secretsmanager", region_name=os.environ["REGION"]
    )

    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=os.environ["SECRET_ARN"]
        )
    except ClientError as e:
        # For a list of exceptions thrown, see
        # https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
        raise e

    # Decrypts secret using the associated KMS key.
    secret = json.loads(get_secret_value_response["SecretString"])
    return secret.get(secret_name)


def get_bots():
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
        }
        for bot in response["Items"]
    }


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


@send_typing_action
def process_message(update, context):
    dynamodb = boto3.resource("dynamodb", region_name=os.environ["REGION"])
    table = dynamodb.Table("message")

    chat_id = update.message.chat_id
    chat_key = to_chat_key(chat_id)
    chat_text = update.message.text
    created_at = int(datetime.datetime.now().timestamp())
    chat_config = get_bots().get(chat_key)

    response = table.scan(
        FilterExpression=Attr("chat_key").eq(chat_key) & Attr("archived").eq(False)
    )
    old_messages = response["Items"]

    if chat_text == "/clear":
        for message in old_messages:
            table.update_item(
                Key={
                    "message_key": message["message_key"],
                    "created_at": message["created_at"],
                },
                UpdateExpression="set archived = :val",
                ExpressionAttributeValues={":val": True},
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
            "chat_key": chat_key,
            "role": "user",
            "text": chat_text,
            "created_at": created_at,
            "archived": False,
        }
    )

    if chat_config.get("prompt"):
        old_messages.insert(0, {"role": "system", "text": chat_config["prompt"]})

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
            text=f"There was an error handling your message :( {e}",
            parse_mode=ParseMode.MARKDOWN,
        )
        context.bot.send_message(
            chat_id=chat_id,
            text=message,
        )

    try:
        table.put_item(
            Item={
                "message_key": message_guid(),
                "chat_key": chat_key,
                "role": "assistant",
                "text": message,
                "created_at": created_at,
                "archived": False,
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


def ffmpeg_convert(input_file, output_file):
    cmd = f"/opt/bin/ffmpeg -i {input_file} {output_file}"
    subprocess.run(cmd, shell=True, check=True)


LOCAL_AUDIO_DOWNLOAD_PATH = "/tmp/input_voice_message.ogg"
LOCAL_AUDIO_CONVERTED_PATH = "/tmp/input_voice_message.mp3"
LOCAL_AUDIO_OUTPUT_PATH = "/tmp/output_voice_message.wav"
LOCAL_AUDIO_OUTPUT_CONVERTED_PATH = "/tmp/output_voice_message.ogg"


@send_typing_action
def process_voice_message(update, context):
    # Get the voice message from the update object
    voice_message = update.message.voice
    # Get the file ID of the voice message
    file_id = voice_message.file_id
    # Use the file ID to get the voice message file from Telegram
    file = context.bot.get_file(file_id)
    file.download(LOCAL_AUDIO_DOWNLOAD_PATH)
    # Now convert to mp3
    ffmpeg_convert(LOCAL_AUDIO_DOWNLOAD_PATH, LOCAL_AUDIO_CONVERTED_PATH)

    # Download the voice message file
    with open(LOCAL_AUDIO_CONVERTED_PATH, "rb") as audio_file:
        transcript = openai.Audio.transcribe("whisper-1", audio_file)

    audio_bytes = generate(
        text=transcript,
        api_key=get_secret("ELEVENLABS_KEY"),
        voice="Bella",
    )

    save(audio_bytes, filename=LOCAL_AUDIO_OUTPUT_PATH)
    # Now convert to ogg, jesus what a mess
    ffmpeg_convert(LOCAL_AUDIO_OUTPUT_PATH, LOCAL_AUDIO_OUTPUT_CONVERTED_PATH)

    # Send the final ogg file back to Telegram
    with open(LOCAL_AUDIO_OUTPUT_CONVERTED_PATH, "rb") as audio_file:
        context.bot.send_voice(chat_id=update.message.chat_id, voice=audio_file)


############################
# Lambda Handler functions #
############################


@app.lambda_function(name=MESSAGE_HANDLER_LAMBDA)
def message_handler(event, context):
    try:
        logger.info(event)
        json_body = json.loads(event["body"])
        if not json_body.get("message"):
            return {"statusCode": 200}

        chat_key = to_chat_key(json_body["message"]["chat"]["id"])
        bots = get_bots()
        bot_config = bots.get(chat_key)

        if not bot_config:
            logger.error("Unrecognized bot")
            return {"statusCode": 404}

        openai.api_key = get_secret("OPENAI_API_KEY")
        bot = Bot(token=get_secret(bot_config.get("secret")))
        dispatcher = Dispatcher(bot, None, use_context=True)
        dispatcher.add_handler(MessageHandler(Filters.text, process_message))
        dispatcher.add_handler(MessageHandler(Filters.voice, process_voice_message))

        dispatcher.process_update(Update.de_json(json_body, bot))
    except Exception as e:
        app.log.error(e)
        app.log.error(traceback.format_exc())
        return {"statusCode": 500}

    return {"statusCode": 200}
