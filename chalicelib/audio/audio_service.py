import json
import os
import subprocess

import openai
from elevenlabs import generate, save
from loguru import logger

LOCAL_AUDIO_DOWNLOAD_PATH = "/tmp/input_voice_message.ogg"
LOCAL_AUDIO_CONVERTED_PATH = "/tmp/input_voice_message.mp3"
LOCAL_AUDIO_OUTPUT_PATH = "/tmp/output_voice_message.wav"
LOCAL_AUDIO_OUTPUT_CONVERTED_PATH = "/tmp/output_voice_message.ogg"
DEFAULT_VOICE = "Bella"


class AudioService:
    def __init__(self):
        from chalicelib.config.config_service import ConfigService

        self.config_service = ConfigService()

    def ffmpeg_convert(self, input_file, output_file):
        output_extension = output_file.split(".")[-1]

        if output_extension == "ogg":
            audio_codec = "-c:a libopus"
        else:
            audio_codec = ""

        command = f"ffmpeg -i {input_file} {audio_codec} {output_file}"
        subprocess.run(command, shell=True)

    def ffprobe_get_duration(self, file_path):
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

    def remove_file(self, file_path):
        if os.path.exists(file_path):
            os.remove(file_path)
        else:
            print(f"The file {file_path} does not exist.")

    def transcribe_audio(self, telegram_file):
        telegram_file.download(LOCAL_AUDIO_DOWNLOAD_PATH)
        # Now convert to mp3
        self.ffmpeg_convert(LOCAL_AUDIO_DOWNLOAD_PATH, LOCAL_AUDIO_CONVERTED_PATH)

        # Download the voice message file
        with open(LOCAL_AUDIO_CONVERTED_PATH, "rb") as audio_file:
            transcript_response = openai.Audio.transcribe("whisper-1", audio_file)
            logger.info("transcript complete", transcript_response)
            return transcript_response.get("text")

    def generate_audio_file(self, message, voice=DEFAULT_VOICE):
        audio_bytes = generate(
            text=message,
            api_key=self.config_service.get_secret("ELEVENLABS_KEY"),
            voice=voice,
        )

        save(audio_bytes, filename=LOCAL_AUDIO_OUTPUT_PATH)

        self.ffmpeg_convert(LOCAL_AUDIO_OUTPUT_PATH, LOCAL_AUDIO_OUTPUT_CONVERTED_PATH)

        # Send the final ogg file back to Telegram
        with open(LOCAL_AUDIO_OUTPUT_CONVERTED_PATH, "rb") as audio_file:
            duration = int(self.ffprobe_get_duration(LOCAL_AUDIO_OUTPUT_CONVERTED_PATH))

        return LOCAL_AUDIO_OUTPUT_CONVERTED_PATH, duration

    def clean_up(self):
        # Delete the files
        self.remove_file(LOCAL_AUDIO_DOWNLOAD_PATH)
        self.remove_file(LOCAL_AUDIO_CONVERTED_PATH)
        self.remove_file(LOCAL_AUDIO_OUTPUT_PATH)
        self.remove_file(LOCAL_AUDIO_OUTPUT_CONVERTED_PATH)
