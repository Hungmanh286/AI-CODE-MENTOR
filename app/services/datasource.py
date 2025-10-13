from typing import Dict


from dotenv import load_dotenv
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.engine import Engine
from sqlmodel import SQLModel, Session, inspect, Table

from app.config import settings


load_dotenv()


def insert_database(
    data: Dict,
    table: str | SQLModel,
    schema: str = settings.APP_DB,
    engine: Engine = settings._app_db_engine,
) -> None:
    """Insert one record to PostgreSQL datatable."""
    if not data:
        return
    SQLModel.metadata.create_all(engine)
    target_table = table
    if isinstance(table, str):
        base = automap_base()
        with engine.connect() as connection:
            base.prepare(connection, reflect=True, schema=schema)
            target_table = Table(
                table, base.metadata, schema=schema, autoload_with=connection
            )

    with Session(engine) as session:
        try:
            stmt = insert(target_table).values(data)
            session.exec(stmt)
            session.commit()
        except Exception:
            print(
                f"Error inserting data to {schema}.{table if isinstance(table, str) else table.__tablename__}",
            )
            session.rollback()
            raise


def update_database(
    data: Dict,
    table: str | SQLModel,
    schema: str = settings.APP_DB,
    engine: Engine = settings._app_db_engine,
) -> None:
    """Update one record in PostgreSQL datatable using upsert (on conflict do update)."""
    if not data:
        return
    SQLModel.metadata.create_all(engine)
    target_table = table
    if isinstance(table, str):
        base = automap_base()
        with engine.connect() as connection:
            base.prepare(connection, reflect=True, schema=schema)
            target_table = Table(
                table, base.metadata, schema=schema, autoload_with=connection
            )

    primary_keys = [key.name for key in inspect(target_table).primary_key]
    table_name = table if isinstance(table, str) else table.__tablename__

    with Session(engine) as session:
        try:
            stmt = insert(target_table).values(data)
            update_dict = {c.name: c for c in stmt.excluded if not c.primary_key}
            if update_dict:
                stmt = stmt.on_conflict_do_update(
                    index_elements=primary_keys, set_=update_dict
                )
            session.exec(stmt)
            session.commit()
        except Exception:
            print(
                f"Error updating data to {schema}.{table_name}",
            )
            session.rollback()
            raise
