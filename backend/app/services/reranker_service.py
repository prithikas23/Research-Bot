import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


class RerankerService:
    """
    Optional reranking service.
    When RERANKER_ENABLED is false, performs safe passthrough.
    When enabled, computes cross-matching score between question and retrieved chunks.
    """

    def __init__(self):
        self.enabled = getattr(settings, "RERANKER_ENABLED", False)

    def rerank(self, query: str, candidates: list[dict], top_n: int = 3) -> list[dict]:
        """
        Rerank retrieved chunk candidates.
        Each candidate is a dict containing:
        {'text': str, 'metadata': dict, 'score': float, 'distance': float}
        """
        if not candidates:
            return []

        if not self.enabled:
            # Sort by existing relevance score descending
            sorted_candidates = sorted(candidates, key=lambda c: c.get("score", 0.0), reverse=True)
            return sorted_candidates[:top_n]

        # Light-weight hybrid/reranker heuristic when enabled
        query_terms = set(query.lower().split())
        for c in candidates:
            text_lower = c.get("text", "").lower()
            overlap = sum(1 for term in query_terms if term in text_lower)
            overlap_ratio = overlap / max(len(query_terms), 1)
            # Combine dense score (70%) with keyword overlap (30%)
            c["score"] = round(c.get("score", 0.0) * 0.7 + overlap_ratio * 0.3, 4)

        sorted_candidates = sorted(candidates, key=lambda c: c.get("score", 0.0), reverse=True)
        return sorted_candidates[:top_n]


reranker_service = RerankerService()
