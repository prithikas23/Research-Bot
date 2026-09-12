from pathlib import Path
import chromadb

BASE_DIR = Path(__file__).resolve().parents[2]
CHROMA_PATH = BASE_DIR / "chroma_db"

client = chromadb.PersistentClient(path=str(CHROMA_PATH))

collection = client.get_or_create_collection(
    name="research_papers",
    metadata={"description": "Research paper chunks and embeddings"}
)


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


def search_documents(query_embedding: list[float], top_k: int = 5):
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, max(collection.count(), 1)),
        include=["documents", "metadatas", "distances"],
    )
    return results
