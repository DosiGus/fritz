from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    app_name: str = "telegram-nutrition-tracker"
    base_url: str = "http://localhost:8000"

    telegram_bot_token: str = ""
    telegram_webhook_secret: str = ""

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/nutrition"
    redis_url: str = "redis://redis:6379/0"

    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_timeout: float = 30.0

    open_food_facts_user_agent: str = "NutritionTracker/0.1 (contact@example.com)"
    open_food_facts_timeout: float = 10.0

    usda_api_key: str = ""
    usda_timeout: float = 10.0

    sentry_dsn: str = ""

    voice_processing_enabled: bool = True
    max_voice_seconds: int = 120
    voice_tmp_dir: str = "/tmp/voice"


settings = Settings()
