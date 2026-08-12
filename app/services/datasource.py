from typing import Dict

import structlog
from dotenv import load_dotenv
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine
from sqlalchemy.ext.automap import automap_base
from sqlmodel import Session, SQLModel, Table, inspect, select

from app.config import settings
from app.schema.upload import UploadFileStatus

logger = structlog.get_logger(__name__)

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
            logger.info(
                f"Error inserting data to {schema}.{table if isinstance(table, str) else table.__tablename__}"
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
            logger.info(f"Error updating data to {schema}.{table_name}")
            session.rollback()
            raise


def get_active_file_id(session_id: str):
    """
    Truy vấn db để tìm tất cả file_id có active=True theo session_id
    """
    engine = settings._app_db_engine
    with Session(engine) as session:
        file_records = session.exec(
            select(UploadFileStatus).where(
                (UploadFileStatus.session_id == session_id) & (UploadFileStatus.active)
            )
        ).all()
        if not file_records:
            return {"error": f"No active file found for session_id {session_id}"}
        return [record.file_id for record in file_records]
