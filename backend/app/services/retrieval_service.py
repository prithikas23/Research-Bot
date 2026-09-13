import logging
from app.core.config import settings
from app.services.embedding_service import embedding_service
from app.services.vector_service import search_documents, collection_count
from app.services.reranker_service import reranker_service

logger = logging.getLogger(__name__)


class RetrievalService:
    """
    Retrieves dense vector chunks from ChromaDB, converts distances to relevance scores,
    and returns top-K context chunks and top-N sources with paper title, page number, and score.
    """

    def __init__(self):
        self.default_top_k = settings.TOP_K
        self.default_top_sources = settings.TOP_SOURCES

    def distance_to_score(self, distance: float) -> float:
        """
        Convert ChromaDB distance to a normalized relevance score in [0.0, 1.0].
        For cosine distance d in [0, 2], cosine similarity is (1 - d).
        Normalized relevance score: max(0.0, min(1.0, (2.0 - d) / 2.0)).
        """
        if distance is None:
            return 0.0
        # If distance is negative or zero, perfect match (1.0)
        if distance <= 0.0:
            return 1.0
        # Cosine distance typically ranges from 0 to 2
        score = (2.0 - float(distance)) / 2.0
        return round(max(0.0, min(1.0, score)), 4)

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        top_sources: int | None = None,
        allowed_document_ids: set[int] | list[int] | None = None,
    ) -> tuple[list[str], list[dict]]:
        """
        Execute dense search and return:
        - context_chunks: list of string texts for LLM prompt
        - sources: list of formatted source dicts (paper_title, page_number, score, rank, document_id)
        """
        k = top_k or self.default_top_k
        n_sources = top_sources or self.default_top_sources

        if collection_count() == 0 or not query.strip():
            return [], []

        # 1. Embed query
        query_vector = embedding_service.embed_query(query)
        if not query_vector:
            return [], []

        # 2. Dense search in ChromaDB
        search_res = search_documents(query_embedding=query_vector, top_k=k)

        documents = search_res.get("documents", [[]])[0]
        metadatas = search_res.get("metadatas", [[]])[0]
        distances = search_res.get("distances", [[]])[0]

        candidates = []
        for doc_text, meta, dist in zip(documents, metadatas, distances):
            meta_dict = meta or {}
            doc_id = int(meta_dict.get("document_id", 0))
            if allowed_document_ids is not None and doc_id not in allowed_document_ids:
                continue

            score = self.distance_to_score(dist)
            candidates.append({
                "text": doc_text,
                "metadata": meta_dict,
                "score": score,
                "distance": dist,
            })

        if not candidates:
            return [], []

        # 3. Optional reranking
        selected_candidates = reranker_service.rerank(query, candidates, top_n=n_sources)

        # 4. Extract context strings and distinct structured sources
        context_chunks = [c["text"] for c in selected_candidates]
        sources = []

        seen_sources = set()
        # First pass: pick highest scoring chunk for distinct (document_id, page_number)
        for c in selected_candidates:
            meta = c["metadata"]
            doc_id = int(meta.get("document_id", 0))
            page_num = int(meta.get("page_number", 1))
            key = (doc_id, page_num)
            if key not in seen_sources:
                seen_sources.add(key)
                sources.append({
                    "paper_title": meta.get("paper_title") or meta.get("source_file") or "Research Paper",
                    "page_number": page_num,
                    "score": float(c["score"]),
                    "rank": len(sources) + 1,
                    "document_id": doc_id,
                    "text": c["text"],
                })
            if len(sources) >= n_sources:
                break

        # Fallback if fewer distinct pages than n_sources: add remaining chunks
        if len(sources) < n_sources:
            for c in selected_candidates:
                meta = c["metadata"]
                doc_id = int(meta.get("document_id", 0))
                page_num = int(meta.get("page_number", 1))
                chunk_id = meta.get("chunk_index")
                if len(sources) >= n_sources:
                    break
                if not any(s["document_id"] == doc_id and s["page_number"] == page_num and s["text"] == c["text"] for s in sources):
                    sources.append({
                        "paper_title": meta.get("paper_title") or meta.get("source_file") or "Research Paper",
                        "page_number": page_num,
                        "score": float(c["score"]),
                        "rank": len(sources) + 1,
                        "document_id": doc_id,
                        "text": c["text"],
                    })

        return context_chunks, sources


retrieval_service = RetrievalService()
