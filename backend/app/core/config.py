from pathlib import Path
from dotenv import load_dotenv
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]
ENV_PATH = BASE_DIR / ".env"

# Explicitly load .env from backend directory using python-dotenv
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "Research Paper Answer Bot"
    APP_ENV: str = "development"
    DEBUG: bool = True

    HOST: str = "127.0.0.1"
    PORT: int = 8000

    DATABASE_URL: str = "postgresql+psycopg2://postgres:sowmi14@localhost:5433/research_bot"

    CHROMA_PATH: str = "./chroma_db"
    CHROMA_COLLECTION: str = "research_papers"

    UPLOAD_DIR: str = "./uploads/papers"
    MAX_FILE_SIZE_MB: int = 50

    EMBEDDING_PROVIDER: str = "huggingface"
    HF_EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"

    GROQ_API_KEY: str = ""
    GROQ_CHAT_MODEL: str = "llama-3.3-70b-versatile"

    OPENAI_API_KEY: str = ""
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_CHAT_MODEL: str = "gpt-4o-mini"

    TOP_K: int = 10
    TOP_SOURCES: int = 3
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 100
    RERANKER_ENABLED: bool = False

    FRONTEND_URL: str = "http://localhost:5173"

    @property
    def resolved_chroma_path(self) -> Path:
        path = Path(self.CHROMA_PATH)
        if not path.is_absolute():
            return (BASE_DIR / path).resolve()
        return path

    @property
    def resolved_upload_dir(self) -> Path:
        path = Path(self.UPLOAD_DIR)
        if not path.is_absolute():
            return (BASE_DIR / path).resolve()
        return path

    @model_validator(mode="after")
    def route_and_isolate_api_keys(self) -> "Settings":
        """
        Enforce separation of provider API keys:
        Keys starting with 'gsk_' belong to Groq and must never be used as OPENAI_API_KEY.
        """
        if not self.GROQ_API_KEY and self.OPENAI_API_KEY and self.OPENAI_API_KEY.startswith("gsk_"):
            self.GROQ_API_KEY = self.OPENAI_API_KEY
            self.OPENAI_API_KEY = ""
        elif self.OPENAI_API_KEY and self.OPENAI_API_KEY.startswith("gsk_"):
            self.OPENAI_API_KEY = ""
        return self


settings = Settings()
