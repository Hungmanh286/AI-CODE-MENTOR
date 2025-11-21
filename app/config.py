import json
from typing import Optional, List

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, PrivateAttr
from sqlalchemy.engine import Engine, create_engine

ENV_FILE = "./.env"


class GlobalConfig(BaseSettings):
    # App
    CORS: Optional[List[str]] = Field(default=["*"])
    VERSION: Optional[str] = Field(default=None)
    APP_ENV: Optional[str] = Field(default="dev")
    TRACING_ENV_FILE: Optional[str] = Field(default="app/config/tracing_env.json")

    # ChatModel
    CHAT_MODEL_KEY: Optional[str] = Field(default=None)
    CHAT_MODEL: Optional[str] = Field(default="gpt-4o-mini")
    CHAT_MODEL_TEMPERATURE: Optional[float] = Field(default=0)

    # Chat mmind map

    # Chat model vision (Openai)
    CHAT_MODEL_VISION_KEY: Optional[str] = Field(default=None)
    CHAT_MODEL_VISION: Optional[str] = Field(default="gpt-5-nano")
    CHAT_MODEL_TEMPERATURE_VISION: Optional[float] = Field(default=0)

    EMBEDDING_KEY: Optional[str] = Field(default=None)
    EMBEDDING_MODEL: Optional[str] = Field(default="voyage-3-large")
    EMBEDDING_DIMS: Optional[int] = Field(default=1024)

    # Ratelimit
    RATELIMIT_REDIS: Optional[str] = Field(default="redis://localhost:6379/0")
    REDIS_MAX_CONNECTION_POOL: Optional[int] = Field(default=100)
    RATELIMIT_WINDOW_MINUTES: Optional[int] = Field(default=24 * 60)

    # Checkpointer
    CHECKPOINT_HOST: Optional[str] = Field(default="localhost")
    CHECKPOINT_PORT: Optional[int] = Field(default=5432)
    CHECKPOINT_DB: Optional[str] = Field(default="checkpointer")
    CHECKPOINT_USER: Optional[str] = Field()
    CHECKPOINT_PASSWORD: Optional[str] = Field()
    HISTORY_CONTEXT_LEN: Optional[int] = Field(default=5)

    # app db
    APP_DB_HOST: Optional[str] = Field(default="localhost")
    APP_DB_PORT: Optional[int] = Field(default=5432)
    APP_DB: Optional[str] = Field(default="mentorbot")
    APP_USER: Optional[str] = Field()
    APP_PASSWORD: Optional[str] = Field()

    # Langfuse
    LANGFUSE_HOST: Optional[str] = Field(default="https://us.cloud.langfuse.com")
    LANGFUSE_SECRET_KEY: Optional[str] = Field(default=None)
    LANGFUSE_PUBLIC_KEY: Optional[str] = Field(default=None)

    # Authentication
    SECRET_KEY: Optional[str] = Field(default=None)
    TOKEN_EXPIRE_HOURS: Optional[int] = Field(default=87600)
    ALGORITHM: Optional[str] = Field(default="HS256")
    ACCOUNT_FILE: Optional[Path] = Field(default=Path("app/config/user.json"))

    # MinIO Storage
    MINIO_ENDPOINT: Optional[str] = Field(default="localhost:9000")
    MINIO_ACCESS_KEY: Optional[str] = Field(default="admin")
    MINIO_SECRET_KEY: Optional[str] = Field(default="admin123")
    MINIO_SECURE: Optional[bool] = Field(default=False)
    MINIO_BUCKET: Optional[str] = Field(default="mybucket")

    _accounts: dict = PrivateAttr()
    _checkpointer_db_uri: str = PrivateAttr()
    _tracing_env: dict = PrivateAttr()
    _tracing_projectid: str = PrivateAttr()
    _app_db_uri: str = PrivateAttr()
    _app_db_engine: Engine = PrivateAttr()

    model_config = SettingsConfigDict(
        extra="ignore", env_file=ENV_FILE, env_file_encoding="utf-8"
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        with open(self.ACCOUNT_FILE, "r") as f:
            self._accounts = json.load(f)

        with open(self.TRACING_ENV_FILE, "r") as f:
            self._tracing_env = json.load(f)
        self._tracing_projectid = self._tracing_env.get(self.APP_ENV.lower())

        self._checkpointer_db_uri = (
            f"postgresql://{self.CHECKPOINT_USER}:{self.CHECKPOINT_PASSWORD}"
            f"@{self.CHECKPOINT_HOST}:{self.CHECKPOINT_PORT}/{self.CHECKPOINT_DB}"
        )

        self._app_db_uri = (
            f"postgresql://{self.APP_USER}:{self.APP_PASSWORD}"
            f"@{self.APP_DB_HOST}:{self.APP_DB_PORT}/{self.APP_DB}"
        )
        self._app_db_engine = create_engine(self._app_db_uri)


settings = GlobalConfig()
