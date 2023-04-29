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
from elevenlabs import generate, save
from loguru import logger
from telegram import Bot, ParseMode, Update
from telegram.ext import Dispatcher, Filters, MessageHandler

from chalicelib.utils import send_typing_action

os.environ["PATH"] += os.pathsep + os.path.dirname(os.path.realpath(__file__))

APP_NAME = "chatgpt-telegram-bot"
MESSAGE_HANDLER_LAMBDA = "message-handler-lambda"
MESSAGE_PROCESS_LAMBDA = "message-process-lambda"
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
            "voice": bot.get("voice"),
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


def clear_chat_history(chat_id):
    dynamodb = boto3.resource("dynamodb", region_name=os.environ["REGION"])
    table = dynamodb.Table("message")
    chat_key = to_chat_key(chat_id)
    response = table.scan(
        FilterExpression=Attr("chat_key").eq(chat_key) & Attr("archived").eq(False)
    )
    old_messages = response["Items"]

    for message in old_messages:
        table.update_item(
            Key={
                "message_key": message["message_key"],
                "created_at": message["created_at"],
            },
            UpdateExpression="set archived = :val",
            ExpressionAttributeValues={":val": True},
        )


def handle_database_and_chatgpt(chat_id, chat_text, voice=False):
    dynamodb = boto3.resource("dynamodb", region_name=os.environ["REGION"])
    table = dynamodb.Table("message")
    chat_key = to_chat_key(chat_id)
    created_at = int(datetime.datetime.now().timestamp())
    chat_config = get_bots().get(chat_key)

    response = table.scan(
        FilterExpression=Attr("chat_key").eq(chat_key) & Attr("archived").eq(False)
    )
    old_messages = response["Items"]

    # Check if the newest message is over 1 day old and clear chat history if needed
    if old_messages:
        newest_message_time = max(message["created_at"] for message in old_messages)
        time_diff = created_at - newest_message_time
        one_day = 86400  # Number of seconds in a day
        if time_diff > one_day:
            clear_chat_history(chat_id)
            old_messages = []

    # Store user message
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

    prompt = chat_config["prompt"]
    if prompt:
        if voice:
            prompt = f"{prompt}. Your response will be converted to audio, please limit your response to 100 characters and only use words and symbols that can be read aloud."

        old_messages.insert(0, {"role": "system", "text": prompt})

    message = ask_chatgpt(chat_text, old_messages)

    # Store assistant message
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

    return message


@send_typing_action
def process_message(update, context):
    chat_id = update.message.chat_id
    chat_text = update.message.text

    if chat_text == "/clear":
        clear_chat_history(chat_id)
        context.bot.send_message(
            chat_id=chat_id,
            text="Chat cleared",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    try:
        message = handle_database_and_chatgpt(chat_id, chat_text)
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


def ffmpeg_convert(input_file, output_file):
    output_extension = output_file.split(".")[-1]

    if output_extension == "ogg":
        audio_codec = "-c:a libopus"
    else:
        audio_codec = ""

    command = f"ffmpeg -i {input_file} {audio_codec} {output_file}"
    subprocess.run(command, shell=True)


def ffprobe_get_duration(file_path):
    command = [
        "/opt/bin/ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        file_path,
    ]
    result = subprocess.run(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    output = json.loads(result.stdout)

    return float(output["format"]["duration"])


def remove_file(file_path):
    if os.path.exists(file_path):
        os.remove(file_path)
    else:
        print(f"The file {file_path} does not exist.")


LOCAL_AUDIO_DOWNLOAD_PATH = "/tmp/input_voice_message.ogg"
LOCAL_AUDIO_CONVERTED_PATH = "/tmp/input_voice_message.mp3"
LOCAL_AUDIO_OUTPUT_PATH = "/tmp/output_voice_message.wav"
LOCAL_AUDIO_OUTPUT_CONVERTED_PATH = "/tmp/output_voice_message.ogg"


def process_voice_message(update, context):
    try:
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
            transcript_response = openai.Audio.transcribe("whisper-1", audio_file)
            logger.info("transcript complete", transcript_response)

        chat_id = update.message.chat_id
        chat_text = transcript_response.get("text")
        bots = get_bots()
        bot_config = bots.get(to_chat_key(chat_id)) or {}

        response_message = handle_database_and_chatgpt(chat_id, chat_text, voice=True)

        audio_bytes = generate(
            text=response_message,
            api_key=get_secret("ELEVENLABS_KEY"),
            voice=bot_config.get("voice", "Bella"),
        )

        save(audio_bytes, filename=LOCAL_AUDIO_OUTPUT_PATH)
        # Now convert to ogg, jesus what a mess
        ffmpeg_convert(LOCAL_AUDIO_OUTPUT_PATH, LOCAL_AUDIO_OUTPUT_CONVERTED_PATH)

        # Send the final ogg file back to Telegram
        with open(LOCAL_AUDIO_OUTPUT_CONVERTED_PATH, "rb") as audio_file:
            duration = int(ffprobe_get_duration(LOCAL_AUDIO_OUTPUT_CONVERTED_PATH))
            context.bot.send_voice(
                chat_id=update.message.chat_id, voice=audio_file, duration=duration
            )
    except Exception as e:
        logger.error(e)
        logger.error(traceback.format_exc())
        context.bot.send_message(
            chat_id=update.message.chat_id,
            text=f"There was an error processing your voice message :( {e}",
            parse_mode=ParseMode.MARKDOWN,
        )
    finally:
        # Delete the files
        remove_file(LOCAL_AUDIO_DOWNLOAD_PATH)
        remove_file(LOCAL_AUDIO_CONVERTED_PATH)
        remove_file(LOCAL_AUDIO_OUTPUT_PATH)
        remove_file(LOCAL_AUDIO_OUTPUT_CONVERTED_PATH)


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

        chat_key = to_chat_key(json_body["message"]["chat"]["id"])
        bots = get_bots()
        bot_config = bots.get(chat_key)

        if not bot_config:
            logger.error("Unrecognized bot")
            return

        openai.api_key = get_secret("OPENAI_API_KEY")
        bot = Bot(token=get_secret(bot_config.get("secret")))
        dispatcher = Dispatcher(bot, None, use_context=True)
        dispatcher.add_handler(MessageHandler(Filters.text, process_message))
        dispatcher.add_handler(MessageHandler(Filters.voice, process_voice_message))

        dispatcher.process_update(Update.de_json(json_body, bot))
    except Exception as e:
        app.log.error(e)
        app.log.error(traceback.format_exc())
