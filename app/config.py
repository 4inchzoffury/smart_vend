from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "sqlite:///./smart_vend.db"
    google_sheets_creds_file: str = "./secrets/service_account.json"
    spreadsheet_id: str = ""
    debug: bool = False
    app_title: str = "Prime Vending"

    # AI / Lead generation
    anthropic_api_key: str = ""
    tavily_api_key: str = ""
    gmail_user: str = ""
    gmail_app_password: str = ""
    calendly_url: str = ""
    calendly_api_key: str = ""

    # Additional AI providers for the customer service chatbot
    groq_api_key: str = ""
    gemini_api_key: str = ""
    openai_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434/v1"

    company_blurb: str = (
        "Prime Vending is a veteran-owned smart cooler vending company "
        "serving Bay County, FL. We provide modern, cashless smart cooler "
        "machines to gyms, hotels, corporate offices, and other high-traffic venues."
    )

    # Google OAuth (for staff authentication)
    google_client_id: str = ""
    google_client_secret: str = ""
    # Generate with: python -c "import secrets; print(secrets.token_hex(32))"
    session_secret_key: str = "change-me-in-production"
    # Comma-separated Gmail addresses allowed to access internal app.
    # Leave empty to allow any Google-authenticated user (not recommended for production).
    allowed_emails: str = ""


settings = Settings()
