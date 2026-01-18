from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    openai_chat_model: str = Field(default="gpt-4o-mini", validation_alias="OPENAI_CHAT_MODEL")
    openai_embed_model: str = Field(default="text-embedding-3-small", validation_alias="OPENAI_EMBED_MODEL")

    hpo_csv_path: str = Field(default="/data/HPO_depth_ge3.csv", validation_alias="HPO_CSV_PATH")
    faiss_dir: str = Field(default="/app/storage/faiss", validation_alias="FAISS_DIR")
    rebuild_faiss_on_startup: bool = Field(default=False, validation_alias="REBUILD_FAISS_ON_STARTUP")
    allow_no_candidate_fit: bool = Field(default=True, validation_alias="ALLOW_NO_CANDIDATE_FIT")

    pubcasefinder_base_url: str = Field(
        default="https://pubcasefinder.dbcls.jp/api",
        validation_alias="PUBCASEFINDER_BASE_URL",
    )

    cors_origins: str = Field(default="http://localhost:3000", validation_alias="CORS_ORIGINS")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

settings = Settings()
