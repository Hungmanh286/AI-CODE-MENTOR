import base64

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from sqlmodel import Session, select
from langfuse.langchain import CallbackHandler


from app.config import settings as ds_settings
from app.schema.mindmap import MindMap
from app.services.datasource import insert_database
from app.services.minio_client import minio_client


router = APIRouter(prefix="/mindmap")

tracer = CallbackHandler()


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


@router.get("/list/{session_id}")
async def list_mindmaps(session_id: str):
    """
    Lấy danh sách mindmaps theo session_id

    Args:
        session_id: ID của session

    Returns:
        List[MindMapResponse]: Danh sách mindmaps
    """
    try:
        with Session(ds_settings._app_db_engine) as session:
            statement = select(MindMap).where(MindMap.session_id == session_id)
            mindmaps = session.exec(statement).all()

            return [
                MindMap(
                    id=mm.id,
                    session_id=mm.session_id,
                    name=mm.name,
                    source_path=mm.source_path,
                    created_at=mm.created_at.isoformat(),
                )
                for mm in mindmaps
            ]

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to list mindmaps: {str(e)}"
        )


@router.get("/mindmap/{mindmap_id}")
async def get_mindmap(
    session_id: str,
    mindmap_id: str,
):
    """
    Lấy ảnh mind map từ MinIO theo session_id
    Trả về base64 encoded image
    """
    try:
        mindmap_path = f"{session_id}/{mindmap_id}_mindmap.png"

        if not minio_client.file_exists(mindmap_path):
            return {"error": "Mind map not found for this session."}

        image_data = minio_client.download_data(mindmap_path)
        if not image_data:
            return {"error": "Failed to download mind map from MinIO."}

        img_base64 = base64.b64encode(image_data).decode("utf-8")

        return JSONResponse(
            {"session_id": session_id, "image_base64": img_base64, "path": mindmap_path}
        )

    except Exception as e:
        return {"error": str(e)}


@router.delete("/{mindmap_id}")
async def delete_mindmap(mindmap_id: int):
    """
    Xóa một mindmap

    Args:
        mindmap_id: ID của mindmap cần xóa

    Returns:
        dict: Thông báo thành công
    """
    try:
        with Session(ds_settings._app_db_engine) as session:
            mindmap = session.get(MindMap, mindmap_id)

            if not mindmap:
                raise HTTPException(status_code=404, detail="Mindmap not found")

            session.delete(mindmap)
            session.commit()

            return {"message": f"Mindmap {mindmap_id} deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete mindmap: {str(e)}"
        )


# @router.get("/get-mindmap-url")
# async def get_mindmap_url(session_id: str, expiry: int = 3600):
#     """
#     Lấy presigned URL của mind map từ MinIO

#     Args:
#         session_id: ID của session
#         expiry: Thời gian URL hợp lệ (giây), mặc định 1 giờ

#     Returns:
#         URL tạm thời để download/view mind map
#     """
#     try:
#         mindmap_path = f"{session_id}/mind_map.png"

#         # Check if file exists
#         if not minio_client.file_exists(mindmap_path):
#             return {"error": "Mind map not found for this session."}

#         # Get presigned URL
#         url = minio_client.get_presigned_url(mindmap_path, expiry_seconds=expiry)

#         return JSONResponse(
#             {
#                 "session_id": session_id,
#                 "url": url,
#                 "expiry_seconds": expiry,
#                 "path": mindmap_path,
#             }
#         )

#     except Exception as e:
#         return {"error": str(e)}
