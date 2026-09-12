# Research Paper Answer Bot - FastAPI + ChromaDB Starter

## 1. Create and activate virtual environment

Windows PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

If PowerShell execution policy blocks activation, use:

```powershell
venv\Scripts\activate.bat
```

## 2. Install packages

```powershell
pip install -r requirements.txt
```

## 3. Create environment file

Copy:

```text
.env.example
```

to:

```text
.env
```

Then update your PostgreSQL credentials later.

## 4. Test ChromaDB

```powershell
python test_chroma.py
```

This creates the local:

```text
chroma_db/
```

directory and inserts two test chunks.

## 5. Start FastAPI

```powershell
uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/docs
```

Health:

```text
GET /api/health
```

Chroma status:

```text
GET /api/chroma/status
```

## Architecture

PDF
  -> PyMuPDF
  -> page-aware chunks
  -> embedding model
  -> ChromaDB
  -> retrieval
  -> reranker (optional)
  -> LLM
  -> answer + top 3 citations

PostgreSQL is intended for application metadata, conversations,
messages and citation records. ChromaDB stores chunk text, embeddings
and retrieval metadata.

## Important

The test uses artificial 3-dimensional vectors only to verify that
Chroma works. Do NOT use those vectors for the real project.

Next implementation steps:
1. PDF upload endpoint
2. Local PDF storage
3. Page-aware extraction
4. Chunking
5. Hugging Face embedding provider
6. Chroma ingestion
7. Query embedding + retrieval
8. LLM/RAG service
9. Top-3 page citations
10. PostgreSQL persistence
11. React frontend
