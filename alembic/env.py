from logging.config import fileConfig

import app.models  # noqa: F401 — registers all models with Base
from alembic import context
from app.database import DATABASE_URL, Base
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    # Use the app's resolved DATABASE_URL (env-driven, psycopg-normalized) rather
    # than the SQLite default hardcoded in alembic.ini, so migrations target the
    # same database the app does — Postgres on Render, SQLite locally.
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    # Override the alembic.ini default with the env-driven DATABASE_URL (see above).
    section["sqlalchemy.url"] = DATABASE_URL
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
