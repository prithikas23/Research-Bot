from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.routes import router
from app.core.database import init_db
from app.services.vector_service import clean_dummy_test_records


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure local upload directory exists
    settings.resolved_upload_dir.mkdir(parents=True, exist_ok=True)
    # Safely verify PostgreSQL connection and tables
    try:
        init_db()
    except Exception as e:
        print(f"Warning: Database initialization check failed: {e}")
    # Remove dummy test records from Chroma
    clean_dummy_test_records()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="FastAPI backend with local ChromaDB for a research-paper RAG system.",
    debug=settings.DEBUG,
    lifespan=lifespan,
)

cors_origins = [
    settings.FRONTEND_URL,
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
# Remove duplicates while preserving order
cors_origins = list(dict.fromkeys([o.rstrip("/") for o in cors_origins if o]))

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.get("/")
def root():
    return {"message": "Research Paper Answer Bot API is running"}


@app.get("/api/health")
def health():
    db_status = "connected"
    try:
        from app.core.database import SessionLocal
        from sqlalchemy import text
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"error: {str(e)}"

    chroma_status = "connected"
    try:
        from app.services.vector_service import collection_count
        collection_count()
    except Exception as e:
        chroma_status = f"error: {str(e)}"

    return {
        "status": "ok",
        "database": db_status,
        "chroma": chroma_status,
    }
