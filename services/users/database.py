"""Keep the existing connection-check command: uv run python -m database."""

import asyncio

from app.infrastructure.database import check_connection


if __name__ == "__main__":
    asyncio.run(check_connection())
