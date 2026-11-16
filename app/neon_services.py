import os
from functools import lru_cache
from pathlib import Path

import boto3
from botocore.config import Config
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env.local")
load_dotenv(ROOT / ".env")


@lru_cache
def database_engine():
    url = make_url(os.environ["DATABASE_URL"]).set(drivername="postgresql+psycopg")
    return create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 5})


@lru_cache
def storage():
    client = boto3.client(
        "s3",
        endpoint_url=os.environ["AWS_ENDPOINT_URL_S3"],
        region_name=os.environ["AWS_REGION"],
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            connect_timeout=5,
            read_timeout=5,
            retries={"total_max_attempts": 2},
        ),
    )
    return client, os.getenv("NEON_STORAGE_BUCKET", "comercio")


def check_postgres():
    with database_engine().connect() as connection:
        connection.execute(text("SELECT 1")).scalar_one()


def check_storage():
    client, bucket = storage()
    client.list_objects_v2(Bucket=bucket, MaxKeys=1)
