from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", ".env.dev"), extra="ignore")

    telegram_bot_token: str = ""
    telegram_webhook_secret: str = ""
    telegram_webhook_url: str = ""

    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_embedding_model: str = ""
    openrouter_chat_model: str = ""

    google_credentials_path: str = ""
    google_spreadsheet_id: str = ""
    regular_schedule_tab: str = "Regular Schedule"
    special_schedule_tab: str = "Special Schedules"
    cached_schedule_ttl: int = 3600

    redis_url: str

    session_ttl_seconds: int = 86_400

    default_language: str = "en"

    contact_email_recipients: str = ""
    contact_phone: str = ""
    contact_request_types: str = (
        '["Speak with a priest", "Spiritual director appointment",'
        ' "Pastoral minister", "General question"]'
    )
    contact_request_types_es: str = ""

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_from_address: str = ""


settings = Settings()  # type: ignore[call-arg]

