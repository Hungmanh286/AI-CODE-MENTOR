"""Mind-map persistence helpers shared by the API layer and the agents."""

from fastapi import HTTPException
from sqlmodel import Session, select

from app.core.config import settings as ds_settings
from app.db.datasource import insert_database
from app.db.models.mindmap import MindMap


def create_mindmap(mindmap: MindMap):
    """
    Tạo một mindmap mới

    Args:
        request: Thông tin mindmap cần tạo

    Returns:
        MindMapResponse: Thông tin mindmap đã tạo
    """

    try:
        data = {
            "id": mindmap.id,
            "session_id": mindmap.session_id,
            "name": mindmap.name,
            "source_path": mindmap.source_path,
        }

        insert_database(
            data=data,
            table=MindMap,
            schema=ds_settings.APP_DB,
            engine=ds_settings._app_db_engine,
        )

        # Lấy lại mindmap vừa tạo để trả về
        with Session(ds_settings._app_db_engine) as session:
            statement = (
                select(MindMap)
                .where(
                    MindMap.session_id == mindmap.session_id,
                    MindMap.name == mindmap.name,
                )
                .order_by(MindMap.created_at.desc())
            )
            mindmap = session.exec(statement).first()

            if not mindmap:
                raise HTTPException(
                    status_code=500, detail="Failed to retrieve created mindmap"
                )

            return MindMap(
                id=mindmap.id,
                session_id=mindmap.session_id,
                name=mindmap.name,
                source_path=mindmap.source_path,
                created_at=mindmap.created_at.isoformat(),
            )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to create mindmap: {str(e)}"
        )
