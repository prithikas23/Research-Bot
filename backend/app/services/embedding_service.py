import logging
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Embedding service abstraction supporting Hugging Face (default BAAI/bge-small-en-v1.5)
    and OpenAI embeddings (text-embedding-3-small).
    Providers and models are dynamically configured via environment variables.
    """

    def __init__(self):
        self.provider = settings.EMBEDDING_PROVIDER.lower()
        self.hf_model_name = settings.HF_EMBEDDING_MODEL
        self.openai_model_name = settings.OPENAI_EMBEDDING_MODEL
        self._hf_embedder = None

    def _get_hf_embedder(self):
        """Lazy load the Hugging Face / FastEmbed model."""
        if self._hf_embedder is None:
            try:
                from fastembed import TextEmbedding
                # Maps BAAI/bge-small-en-v1.5 or equivalent
                self._hf_embedder = TextEmbedding(model_name=self.hf_model_name)
                logger.info(f"Loaded local FastEmbed model: {self.hf_model_name}")
            except Exception as e:
                logger.warning(f"FastEmbed load failed ({e}), falling back to Chroma DefaultEmbeddingFunction.")
                import chromadb.utils.embedding_functions as ef
                self._hf_embedder = ef.DefaultEmbeddingFunction()
        return self._hf_embedder

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Embed a list of text strings into vector representations.
        """
        if not texts:
            return []

        if self.provider == "openai":
            return self._embed_openai(texts)

        # Default: Hugging Face (BAAI/bge-small-en-v1.5)
        return self._embed_huggingface(texts)

    def embed_query(self, query: str) -> list[float]:
        """
        Embed a single search query string.
        """
        vectors = self.embed_texts([query])
        return vectors[0] if vectors else []

    def _embed_huggingface(self, texts: list[str]) -> list[list[float]]:
        embedder = self._get_hf_embedder()
        # If fastembed TextEmbedding
        if hasattr(embedder, "embed"):
            embeddings_iter = embedder.embed(texts)
            return [arr.tolist() if hasattr(arr, "tolist") else list(arr) for arr in embeddings_iter]
        # Fallback to chromadb DefaultEmbeddingFunction
        return embedder(texts)

    def _embed_openai(self, texts: list[str]) -> list[list[float]]:
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY must be provided for provider 'openai'.")

        url = "https://api.openai.com/v1/embeddings"
        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "input": texts,
            "model": self.openai_model_name,
        }

        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return [item["embedding"] for item in data["data"]]


embedding_service = EmbeddingService()
