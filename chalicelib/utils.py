import uuid
import os
import json
from functools import wraps

import boto3
import wget
from loguru import logger
from telegram import ChatAction


def send_typing_action(func):
    """Sends typing action while processing func command."""

    @wraps(func)
    def command_func(update, context, *args, **kwargs):
        context.bot.send_chat_action(
            chat_id=update.effective_message.chat_id, action=ChatAction.TYPING
        )
        return func(update, context, *args, **kwargs)

    return command_func


def generate_transcription(file):

    # AWS needed clients
    s3_client = boto3.client("s3")
    transcribe_client = boto3.client("transcribe")

    local_path = "/tmp/voice_message.ogg"
    message_id = str(uuid.uuid4())

    s3_bucket = os.environ["VOICE_MESSAGES_BUCKET"]
    s3_prefix = os.path.join(message_id, "audio_file.ogg")
    remote_s3_path = os.path.join("s3://", s3_bucket, s3_prefix)

    file.download(local_path)
    s3_client.upload_file(local_path, s3_bucket, s3_prefix)

    job_name = f"transcription_job_{message_id}"
    transcribe_client.start_transcription_job(
        TranscriptionJobName=job_name,
        IdentifyLanguage=True,
        MediaFormat="ogg",
        Media={"MediaFileUri": remote_s3_path},
    )

    # Wait for the transcription job to complete
    job_status = None
    while job_status != "COMPLETED":
        status = transcribe_client.get_transcription_job(TranscriptionJobName=job_name)
        job_status = status["TranscriptionJob"]["TranscriptionJobStatus"]

    # Get the transcript once the job is completed
    transcript = status["TranscriptionJob"]["Transcript"]["TranscriptFileUri"]
    logger.info(transcript)

    output_location = f"/tmp/output_{message_id}.json"
    wget.download(transcript, output_location)

    with open(output_location) as f:
        output = json.load(f)
    return output["results"]["transcripts"][0]["transcript"]
