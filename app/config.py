from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Puts .env into os.environ, so LOG_LEVEL reaches setup_logging when running locally
load_dotenv()


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """

    app_name: str = "Secret Santa API"
    app_version: str = "4.2.0"

    database_url: str
    secret_key: str

    debug: bool = False

    cors_origins: list[str]

    access_token_expire_minutes: int = 30

    initial_admin_email: str
    initial_admin_password: str
    initial_admin_name: str

    class Config:
        case_sensitive = False


settings = Settings()
