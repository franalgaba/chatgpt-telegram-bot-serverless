import boto3


class BotService:
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
