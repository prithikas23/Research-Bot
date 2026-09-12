import logging
from pathlib import Path
import chromadb
from app.core.config import settings

logger = logging.getLogger(__name__)

client = chromadb.PersistentClient(path=str(settings.resolved_chroma_path))

collection = client.get_or_create_collection(
    name=settings.CHROMA_COLLECTION,
    metadata={"description": "Research paper chunks and embeddings"}
)


def clean_dummy_test_records():
    """
    Remove initial test dummy records (test_chunk_1, test_chunk_2)
    to prevent dummy 3-dim vectors from interfering with real research papers.
    """
    try:
        dummy_ids = ["test_chunk_1", "test_chunk_2"]
        existing = collection.get(ids=dummy_ids)
        if existing and existing["ids"]:
            collection.delete(ids=existing["ids"])
            logger.info(f"Cleaned up dummy test records from ChromaDB: {existing['ids']}")
    except Exception as e:
        logger.warning(f"Error checking/cleaning dummy test records: {e}")


def collection_count() -> int:
    return collection.count()


def add_documents(
    ids: list[str],
    documents: list[str],
    metadatas: list[dict],
    embeddings: list[list[float]] | None = None,
):
    if not (len(ids) == len(documents) == len(metadatas)):
        raise ValueError("ids, documents and metadatas must have the same length")

    kwargs = {
        "ids": ids,
        "documents": documents,
        "metadatas": metadatas,
    }

    if embeddings is not None:
        if len(embeddings) != len(ids):
            raise ValueError("embeddings length must match ids length")
        kwargs["embeddings"] = embeddings

    collection.upsert(**kwargs)


def delete_document_chunks(document_id: int):
    """
    Delete all chunks associated with a specific document_id.
    """
    try:
        collection.delete(where={"document_id": int(document_id)})
        logger.info(f"Deleted ChromaDB chunks for document_id={document_id}")
    except Exception as e:
        logger.error(f"Failed to delete ChromaDB chunks for document_id={document_id}: {e}")
        raise


def search_documents(query_embedding: list[float], top_k: int = 10):
    """
    Query collection with embedding vector and return top_k nearest chunks.
    """
    count = collection.count()
    if count == 0:
        return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, count),
        include=["documents", "metadatas", "distances"],
    )
    return results
