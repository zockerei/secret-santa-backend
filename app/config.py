from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Puts .env into os.environ, so LOG_LEVEL reaches setup_logging when running locally
load_dotenv()


class Settings(BaseSettings):
    """Application settings, read from environment variables (see .env.example)."""

    database_url: str
    secret_key: str

    access_token_expire_minutes: int = 7 * 24 * 60

    # Creates this admin on startup if there is no admin yet
    initial_admin_name: str | None = None
    initial_admin_email: str | None = None
    initial_admin_password: str | None = None


settings = Settings()
