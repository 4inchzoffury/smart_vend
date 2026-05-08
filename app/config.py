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
    company_blurb: str = (
        "Prime Vending is a veteran-owned smart cooler vending company "
        "serving Bay County, FL. We provide modern, cashless smart cooler "
        "machines to gyms, hotels, corporate offices, and other high-traffic venues."
    )


settings = Settings()
