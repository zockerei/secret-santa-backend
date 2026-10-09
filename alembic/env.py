"""Alembic environment: runs the migrations against DATABASE_URL, using the API's models."""
import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import create_engine, make_url, pool
from sqlmodel import SQLModel

# Importing the models registers their tables on SQLModel.metadata
import app.models  # noqa: F401

load_dotenv()

config = context.config

# The API runs migrations itself and has its own logging, so it turns this off
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def database_url():
    """DATABASE_URL with the sync psycopg driver, whatever driver the URL names."""
    url = os.getenv("DATABASE_URL")
    if not url:
        raise ValueError("DATABASE_URL is not set. Add it to the .env file.")
    return make_url(url).set(drivername="postgresql+psycopg")


def run_migrations_offline() -> None:
    """Write the migrations as SQL to stdout instead of running them ('alembic upgrade --sql')."""
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run the migrations against the database."""
    engine = create_engine(database_url(), poolclass=pool.NullPool)

    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
