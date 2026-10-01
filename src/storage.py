import os

import boto3
from botocore.config import Config


class StorageConfigurationError(RuntimeError):
    pass


def get_s3_client():
    required = (
        'AWS_ACCESS_KEY_ID',
        'AWS_SECRET_ACCESS_KEY',
        'AWS_ENDPOINT_URL_S3',
        'AWS_REGION',
    )
    if any(not os.getenv(name) for name in required):
        raise StorageConfigurationError('Object storage environment variables are missing')

    return boto3.client(
        's3',
        endpoint_url=os.environ['AWS_ENDPOINT_URL_S3'],
        region_name=os.environ['AWS_REGION'],
        aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
        aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
        config=Config(s3={'addressing_style': 'path'}),
    )