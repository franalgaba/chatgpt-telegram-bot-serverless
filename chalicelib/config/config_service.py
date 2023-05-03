import json
import os

import boto3
from botocore.exceptions import ClientError


class ConfigService:
    @staticmethod
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
