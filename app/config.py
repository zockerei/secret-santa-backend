import logging
import logging.config
import yaml
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """

    app_name: str = "Secret Santa API"
    app_version: str = "4.2.0"

    database_url: str
    secret_key: str

    debug: bool = False
    log_level: str = "INFO"

    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    access_token_expire_minutes: int = 30

    initial_admin_email: str | None = None
    initial_admin_password: str | None = None
    initial_admin_name: str = "admin"

    class Config:
        env_file = ".env"
        case_sensitive = False


class CustomFormatter(logging.Formatter):
    """
    Custom formatter to add colors to log messages.
    """
    COLORS = {
        'DEBUG': '\033[37m',       # White
        'INFO': '\033[32m',        # Green
        'WARNING': '\033[33m',     # Yellow
        'ERROR': '\033[31m',       # Red
        'CRITICAL': '\033[1;31m',  # Bold Red
        'NAME': '\033[36m'         # Cyan
    }
    RESET = '\033[0m'

    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.RESET)
        name_color = self.COLORS['NAME']
        record.levelname = f"{log_color}{record.levelname:<8}{self.RESET}"
        record.name = f"{name_color}{record.name}{self.RESET}"
        record.msg = f"{log_color}{record.msg}{self.RESET}"
        return super().format(record)


def setup_logging():
    """
    Sets up the logging configuration for the Secret Santa API.

    Reads the logging configuration from a YAML file and applies it.
    Creates necessary log directories and updates file paths.
    """
    try:
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        config_file = Path("logging_config.yaml")
        if config_file.exists():
            with open(config_file, 'r') as file:
                config = yaml.safe_load(file.read())

            api_log_path = log_dir / 'api.log'
            error_log_path = log_dir / 'errors.log'

            api_log_path.touch(exist_ok=True)
            error_log_path.touch(exist_ok=True)

            if 'filename' not in config['handlers']['rotating_file']:
                config['handlers']['rotating_file']['filename'] = str(api_log_path)
            if 'filename' not in config['handlers']['error_file']:
                config['handlers']['error_file']['filename'] = str(error_log_path)

            logging.config.dictConfig(config)

            logger = logging.getLogger(__name__)
            logger.info("Logging configuration loaded successfully")
        else:
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s [%(levelname)-8s] %(name)s: %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            logging.warning("logging_config.yaml not found, using basic logging")

    except PermissionError as e:
        logging.error(f"Permission error setting up log files: {e}")
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)-8s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    except yaml.YAMLError as e:
        logging.error(f"Error parsing logging YAML file: {e}")
        logging.basicConfig(level=logging.INFO)
    except Exception as e:
        logging.error(f"Unexpected error in logging configuration: {e}")
        logging.basicConfig(level=logging.INFO)


settings = Settings()
