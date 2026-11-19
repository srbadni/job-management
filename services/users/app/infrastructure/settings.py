from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class LocalSettings(BaseSettings):
    model_config = SettingsConfigDict(
        # Both the checkout and the Docker image retain the services/users layout.
        env_file=Path(__file__).resolve().parents[4] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )
