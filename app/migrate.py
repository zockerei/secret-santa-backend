"""
Brings the database schema up to date. The API runs this on startup.

Databases from before migrations were tracked already have the tables, but no
(or an unknown) revision in alembic_version. Those are stamped with the baseline
revision instead of creating the tables again.
"""
import logging
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, make_url
from sqlmodel import SQLModel

from .config import settings
from . import models  # noqa: F401  (registers the tables on SQLModel.metadata)

BASELINE_REVISION = "0001"

logger = logging.getLogger(__name__)


def migrate():
    """Stamp a database from before migrations if needed, then upgrade it to the latest revision."""
    config = Config(Path(__file__).resolve().parent.parent / "alembic.ini")
    config.attributes["configure_logger"] = False

    engine = create_engine(make_url(settings.database_url).set(drivername="postgresql+psycopg"))
    try:
        with engine.connect() as connection:
            current = MigrationContext.configure(connection).get_current_revision()
            has_tables = inspect(connection).has_table("users")

        known_revisions = {script.revision for script in ScriptDirectory.from_config(config).walk_revisions()}
        if has_tables and current not in known_revisions:
            logger.info(f"Existing database without known migration ({current}), stamping it as baseline")
            command.stamp(config, BASELINE_REVISION, purge=True)

        command.upgrade(config, "head")

        with engine.connect() as connection:
            revision = MigrationContext.configure(connection).get_current_revision()
            differences = compare_metadata(MigrationContext.configure(connection), SQLModel.metadata)
        if revision != current:
            logger.info(f"Database schema upgraded from revision {current} to {revision}")
        else:
            logger.info(f"Database schema is at revision {revision}")
        for difference in differences:
            logger.warning(f"Database differs from models.py: {difference}")
    finally:
        engine.dispose()
