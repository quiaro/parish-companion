import json
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", ".env.dev"), extra="ignore")

    environment: Literal["production", "development"] = "production"

    telegram_bot_token: str = ""
    telegram_webhook_secret: str = ""
    telegram_webhook_url: str = ""

    @model_validator(mode="after")
    def must_have_telegram_configured(self) -> "Settings":
        # There's no legitimate way to run this app without a Telegram connection.
        missing = []
        if not self.telegram_bot_token:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not self.telegram_webhook_url:
            missing.append("TELEGRAM_WEBHOOK_URL")
        if not self.telegram_webhook_secret:
            missing.append("TELEGRAM_WEBHOOK_SECRET")
        if missing:
            raise ValueError(f"{', '.join(missing)} must be set.")
        return self

    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_embedding_model: str = ""
    openrouter_chat_model: str = ""

    schedules_google_credentials_path: str = ""
    schedules_google_spreadsheet_id: str = ""
    schedules_regular_tab: str = "Regular Schedule"
    schedules_special_tab: str = "Special Schedules"
    schedules_cache_ttl_seconds: int = 3600

    information_google_credentials_path: str = ""
    information_google_spreadsheet_id: str = ""
    information_topics_tab: str = "Information"
    information_cache_ttl_seconds: int = 3600

    redis_url: str

    database_url: str

    local_timezone: str

    session_ttl_seconds: int = 86_400

    default_language: str = "en"

    contact_email_recipients: str = ""
    contact_phone: str = ""
    contact_request_types: str = (
        '["Speak with a priest", "Spiritual director appointment",'
        ' "Pastoral minister", "General question"]'
    )
    contact_request_types_es: str = ""

    @field_validator("contact_request_types")
    @classmethod
    def must_be_non_empty_json_list(cls, v: str) -> str:
        try:
            parsed = json.loads(v)
        except json.JSONDecodeError:
            raise ValueError("CONTACT_REQUEST_TYPES must be a valid JSON array")
        if not isinstance(parsed, list) or not parsed:
            raise ValueError("CONTACT_REQUEST_TYPES must be a non-empty JSON array")
        return v

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_from_address: str = ""

    @model_validator(mode="after")
    def must_have_email_configured_in_production(self) -> "Settings":
        if self.environment != "production":
            return self
        missing = []
        if not self.smtp_host:
            missing.append("SMTP_HOST")
        try:
            recipients = json.loads(self.contact_email_recipients)
        except (json.JSONDecodeError, TypeError):
            recipients = []
        if not isinstance(recipients, list) or not recipients:
            missing.append("CONTACT_EMAIL_RECIPIENTS")
        if missing:
            raise ValueError(
                f"{', '.join(missing)} must be set in production; set ENVIRONMENT=development "
                "to bypass this for local development."
            )
        return self

    comfort_notification_dedup_window_hours: int = 24
    comfort_frequency_window_hours: int = 24
    comfort_escalation_passage_threshold: int = 10
    comfort_similarity_threshold: float = 0.2

    qdrant_url: str = "http://qdrant:6333"
    qdrant_collection_name: str = "bible_verses"

    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_base_url: str = ""


settings = Settings()  # type: ignore[call-arg]

