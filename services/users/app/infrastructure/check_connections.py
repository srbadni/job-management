"""Run read-only, authenticated checks for the optional infrastructure."""

import asyncio
import sys
from urllib.parse import urlsplit

import aio_pika
import urllib3
from minio import Minio
from pydantic import Field, HttpUrl, SecretStr, ValidationError
from redis.asyncio import Redis

from app.infrastructure.settings import LocalSettings

TIMEOUT = 5


class ConnectionSettings(LocalSettings):
    rabbitmq_host: str = Field(default="localhost", min_length=1)
    rabbitmq_port: int = Field(default=5672, ge=1, le=65535)
    rabbitmq_user: str = Field(min_length=1)
    rabbitmq_password: SecretStr = Field(min_length=1)

    redis_host: str = Field(default="localhost", min_length=1)
    redis_port: int = Field(default=6379, ge=1, le=65535)
    redis_password: SecretStr = Field(min_length=1)

    minio_endpoint: HttpUrl = Field(default="http://localhost:9000")
    minio_access_key: SecretStr = Field(min_length=1)
    minio_secret_key: SecretStr = Field(min_length=1)


async def check_rabbitmq(settings: ConnectionSettings) -> None:
    connection = await aio_pika.connect(
        host=settings.rabbitmq_host,
        port=settings.rabbitmq_port,
        login=settings.rabbitmq_user,
        password=settings.rabbitmq_password.get_secret_value(),
        timeout=TIMEOUT,
    )
    await connection.close()


async def check_redis(settings: ConnectionSettings) -> None:
    async with Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        password=settings.redis_password.get_secret_value(),
        socket_connect_timeout=TIMEOUT,
        socket_timeout=TIMEOUT,
    ) as client:
        if not await client.ping():
            raise RuntimeError("Redis did not answer PING")


def check_minio(settings: ConnectionSettings) -> None:
    endpoint = urlsplit(str(settings.minio_endpoint))
    if endpoint.path != "/" or endpoint.query or endpoint.fragment or endpoint.username is not None:
        raise ValueError("MINIO_ENDPOINT must be an HTTP(S) origin")

    pool = urllib3.PoolManager(
        timeout=urllib3.Timeout(connect=TIMEOUT, read=TIMEOUT),
        retries=False,
        cert_reqs="CERT_REQUIRED",
    )
    try:
        client = Minio(
            endpoint.netloc,
            access_key=settings.minio_access_key.get_secret_value(),
            secret_key=settings.minio_secret_key.get_secret_value(),
            secure=endpoint.scheme == "https",
            http_client=pool,
        )
        client.list_buckets()
    finally:
        pool.clear()


async def main() -> int:
    try:
        settings = ConnectionSettings()
    except ValidationError as error:
        fields = ", ".join(str(item["loc"][0]) for item in error.errors(include_input=False))
        print(f"Missing or invalid infrastructure settings: {fields}", file=sys.stderr)
        return 1

    checks = {
        "RabbitMQ": check_rabbitmq(settings),
        "Redis": check_redis(settings),
        "MinIO/S3": asyncio.to_thread(check_minio, settings),
    }
    results = await asyncio.gather(*checks.values(), return_exceptions=True)
    failed = False
    for service, result in zip(checks, results, strict=True):
        if isinstance(result, BaseException):
            print(f"{service} check failed ({type(result).__name__})", file=sys.stderr)
            failed = True
        else:
            print(f"{service} connection OK")
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
