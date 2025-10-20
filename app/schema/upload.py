from typing import Optional
from sqlmodel import Field, SQLModel


class UploadFileStatus(SQLModel, table=True):
    __tablename__ = "upload_file_status"
    id: Optional[int] = Field(default=None, primary_key=True)
    file_id: str = Field(default=None)
    session_id: str
    file_name: str
    active: bool = Field(default=False)
