from pathlib import Path
import fitz  # PyMuPDF


class PDFService:
    """Service to extract text and metadata page-by-page from PDF files."""

    @staticmethod
    def extract_pages(file_path: str | Path) -> list[dict]:
        """
        Extract text page-by-page from a PDF file.
        Returns a list of dictionaries with 1-indexed page_number and extracted text.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF file not found at: {path}")

        pages_data = []
        doc = fitz.open(str(path))
        try:
            for index, page in enumerate(doc):
                raw_text = page.get_text("text") or ""
                # Normalize line breaks and clean whitespace
                cleaned_text = " ".join(raw_text.split())
                pages_data.append({
                    "page_number": index + 1,
                    "text": cleaned_text
                })
        finally:
            doc.close()

        return pages_data

    @staticmethod
    def get_pdf_metadata(file_path: str | Path) -> dict:
        """
        Get document metadata including page count and optional document title.
        """
        path = Path(file_path)
        doc = fitz.open(str(path))
        try:
            page_count = len(doc)
            title = doc.metadata.get("title", "").strip()
            return {
                "page_count": page_count,
                "title": title if title else None
            }
        finally:
            doc.close()


pdf_service = PDFService()
