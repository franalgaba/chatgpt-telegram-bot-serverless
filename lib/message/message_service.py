import os
import uuid

import boto3
from boto3.dynamodb.conditions import Attr


class MessageService:
    def message_guid():
        """Generate a random guid for message key"""
        return str(uuid.uuid4())

    def to_chat_key(chat_id):
        return f"chat_{str(chat_id).replace('-', '')}"

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
