import datetime
import os
import uuid

import boto3
from boto3.dynamodb.conditions import Attr


class MessageService:
    @staticmethod
    def message_guid():
        """Generate a random guid for message key"""
        return str(uuid.uuid4())

    @staticmethod
    def to_chat_key(chat_id):
        return f"chat_{str(chat_id).replace('-', '')}"

    @staticmethod
    def timestamp():
        return int(datetime.datetime.now().timestamp())

    def clear_chat_history(self, chat_id):
        dynamodb = boto3.resource("dynamodb", region_name=os.environ["REGION"])
        table = dynamodb.Table("message")
        chat_key = self.to_chat_key(chat_id)
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

    def fetch_old_messages(self, chat_id):
        dynamodb = boto3.resource("dynamodb", region_name=os.environ["REGION"])
        table = dynamodb.Table("message")
        chat_key = self.to_chat_key(chat_id)
        created_at = self.timestamp()

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
                self.clear_chat_history(chat_id)
                old_messages = []
        return old_messages

    def store_message(self, chat_id, chat_text, role):
        dynamodb = boto3.resource("dynamodb", region_name=os.environ["REGION"])
        table = dynamodb.Table("message")
        created_at = self.timestamp()
        chat_key = self.to_chat_key(chat_id)
        # Store user message
        table.put_item(
            Item={
                "message_key": self.message_guid(),
                "chat_key": chat_key,
                "role": role,
                "text": chat_text,
                "created_at": created_at,
                "archived": False,
            }
        )
        return chat_text
