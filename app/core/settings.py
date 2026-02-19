from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    azure_openai_endpoint: str = Field(alias="AZURE_OPENAI_ENDPOINT")
    azure_openai_api_key: str = Field(alias="AZURE_OPENAI_API_KEY")
    azure_openai_deployment: str = Field(alias="AZURE_OPENAI_DEPLOYMENT")
    azure_openai_api_version: str = Field(alias="AZURE_OPENAI_API_VERSION")


settings = Settings()
