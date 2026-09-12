from app.core.config import settings


class ChunkingService:
    """
    Page-aware text chunking service.
    Splits text within each page boundary to ensure 100% accurate page attribution.
    """

    def __init__(self, chunk_size: int | None = None, chunk_overlap: int | None = None):
        self.chunk_size = chunk_size or settings.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP

    def _split_text(self, text: str) -> list[str]:
        """
        Split a single block of text into overlapping chunks using sliding window.
        Uses sentence/word boundaries when available.
        """
        if not text or not text.strip():
            return []

        text = text.strip()
        if len(text) <= self.chunk_size:
            return [text]

        chunks = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + self.chunk_size, text_len)
            
            # If not at the end of the text, try to find a natural break point (period, exclamation, newline, space)
            if end < text_len:
                # Look backwards for a sentence boundary
                boundary = -1
                for sep in [". ", "? ", "! ", "\n", "; ", ", ", " "]:
                    pos = text.rfind(sep, start + int(self.chunk_size * 0.6), end)
                    if pos != -1:
                        boundary = pos + len(sep)
                        break
                if boundary != -1 and boundary > start:
                    end = boundary

            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append(chunk_text)

            if end >= text_len:
                break

            # Move start forward with overlap
            step = max(end - start - self.chunk_overlap, 1)
            start += step

        return chunks

    def create_page_aware_chunks(
        self,
        pages_data: list[dict],
        document_id: int,
        paper_title: str,
        source_file: str,
    ) -> list[dict]:
        """
        Produce deterministic, page-attributed chunks for ChromaDB indexing.
        
        Returns a list of dicts:
        {
            "id": f"document_{document_id}_chunk_{chunk_index}",
            "text": chunk_text,
            "metadata": {
                "document_id": document_id,
                "paper_title": paper_title,
                "page_number": page_number,
                "chunk_index": chunk_index,
                "source_file": source_file,
            }
        }
        """
        chunks = []
        global_chunk_index = 0

        for page in pages_data:
            page_num = page["page_number"]
            page_text = page.get("text", "")
            if not page_text or not page_text.strip():
                continue

            page_chunks = self._split_text(page_text)
            for chunk_content in page_chunks:
                chunk_id = f"document_{document_id}_chunk_{global_chunk_index}"
                chunks.append({
                    "id": chunk_id,
                    "text": chunk_content,
                    "metadata": {
                        "document_id": document_id,
                        "paper_title": paper_title,
                        "page_number": page_num,
                        "chunk_index": global_chunk_index,
                        "source_file": source_file,
                    }
                })
                global_chunk_index += 1

        return chunks


chunking_service = ChunkingService()
