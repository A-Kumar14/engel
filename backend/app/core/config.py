from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Engel Backend"
    api_prefix: str = "/api"
    env: str = "dev"
    database_url: str = "sqlite:///./engel.db"
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # OpenRouter — chat completions (auto-tag, ledger chat)
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "meta-llama/llama-3.3-70b-instruct:free"

    # Groq — audio transcription (Whisper-compatible)
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_whisper_model: str = "whisper-large-v3-turbo"

    # Twilio Verify (SMS 2FA)
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_verify_service_sid: str = ""

    # Waitlist (Resend)
    resend_api_key: str = ""
    waitlist_from_email: str = "Engel <onboarding@resend.dev>"
    waitlist_reply_to: str = "arssh.kumar10@gmail.com"
    public_api_base_url: str = "http://127.0.0.1:8000"
    waitlist_success_url: str = "https://a-kumar14.github.io/engel/confirmed.html"
    cors_origins: str = "https://a-kumar14.github.io,http://127.0.0.1:8080,http://localhost:8080"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
