import sys
import io
from pathlib import Path
import fitz  # PyMuPDF

# Add backend to path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.models import Document, Conversation, Message, MessageSource


def create_sample_pdf() -> bytes:
    """Create a 3-page research paper PDF in-memory using PyMuPDF."""
    doc = fitz.open()

    # Page 1: Introduction to Attention and Transformers
    page1 = doc.new_page()
    page1.insert_text(
        fitz.Point(50, 72),
        "Attention Is All You Need\n\n"
        "Abstract\n"
        "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks. "
        "We propose the Transformer, a model architecture eschewing recurrence and relying entirely on an attention mechanism "
        "to draw global dependencies between input and output. The Transformer allows for significantly more parallelization.\n\n"
        "1. Introduction\n"
        "Recurrent neural networks typically factor computation along the symbol positions of the input and output sequences. "
        "This inherently sequential nature precludes parallelization within training examples. "
        "The Transformer solves this sequential constraint using multi-head self-attention.",
        fontsize=11,
    )

    # Page 2: Attention Mechanism and Architecture
    page2 = doc.new_page()
    page2.insert_text(
        fitz.Point(50, 72),
        "2. The Attention Mechanism\n\n"
        "An attention function can be described as mapping a query and a set of key-value pairs to an output. "
        "The output is computed as a weighted sum of the values, where the weight assigned to each value is computed by a "
        "compatibility function of the query with the corresponding key.\n\n"
        "Scaled Dot-Product Attention computes the attention scores by dividing queries and keys by the square root of the dimension dk. "
        "Multi-Head Attention allows the model to jointly attend to information from different representation subspaces at different positions.",
        fontsize=11,
    )

    # Page 3: Retrieval-Augmented Generation and Limitations
    page3 = doc.new_page()
    page3.insert_text(
        fitz.Point(50, 72),
        "3. Retrieval Augmented Generation and Results\n\n"
        "Retrieval Augmented Generation (RAG) improves LLM responses by retrieving relevant external context documents "
        "before generating an answer. This grounds the language model output in factual research evidence and dramatically reduces hallucinations.\n\n"
        "4. Limitations and Future Work\n"
        "The limitations of the proposed approach include computational complexity with long document contexts and dependence on retriever accuracy. "
        "Future work suggests exploring sparse attention patterns, hybrid dense-lexical retrieval, and multi-modal integration.",
        fontsize=11,
    )

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def run_tests():
    client = TestClient(app)

    print("--- 1. Testing Health Endpoint ---")
    res = client.get("/api/health")
    assert res.status_code == 200, f"Health check failed: {res.text}"
    health_data = res.json()
    print("Health:", health_data)
    assert health_data["status"] == "ok"
    assert health_data["database"] == "connected"
    assert health_data["chroma"] == "connected"

    print("\n--- 2. Testing Document Upload ---")
    pdf_bytes = create_sample_pdf()
    files = {
        "file": ("Attention_And_RAG_Survey.pdf", io.BytesIO(pdf_bytes), "application/pdf")
    }
    upload_res = client.post("/api/documents/upload", files=files)
    print("Upload response status:", upload_res.status_code)
    assert upload_res.status_code == 201, f"Upload failed: {upload_res.text}"
    upload_data = upload_res.json()
    doc_id = upload_data["document"]["id"]
    print("Uploaded document ID:", doc_id)
    print("Status message:", upload_data["message"])
    assert upload_data["document"]["page_count"] == 3
    assert upload_data["document"]["status"] == "not_refreshed"

    print("\n--- 2b. Explicitly Refresh Document for Indexing ---")
    refresh_res = client.post(f"/api/documents/{doc_id}/refresh")
    assert refresh_res.status_code == 200, f"Refresh failed: {refresh_res.text}"
    refresh_data = refresh_res.json()
    assert refresh_data["document"]["status"] == "refreshed"
    print("Refresh message:", refresh_data["message"])

    print("\n--- 3. Testing Documents Listing ---")
    docs_res = client.get("/api/documents")
    assert docs_res.status_code == 200
    docs = docs_res.json()
    print(f"Total documents in DB: {len(docs)}")
    assert any(d["id"] == doc_id for d in docs)

    print("\n--- 4. Testing Document Details ---")
    detail_res = client.get(f"/api/documents/{doc_id}")
    assert detail_res.status_code == 200
    print("Doc details:", detail_res.json()["original_filename"])

    print("\n--- 5. Testing Conversations CRUD ---")
    conv_res = client.post("/api/conversations", json={"title": "Test RAG Research Session"})
    assert conv_res.status_code == 201
    conv_data = conv_res.json()
    conv_id = conv_data["id"]
    print(f"Created conversation ID: {conv_id}")

    print("\n--- 6. Testing Chat API: Question 1 (Attention) ---")
    chat_payload = {
        "conversation_id": conv_id,
        "question": "What is the role of attention in Transformers?"
    }
    chat_res = client.post("/api/chat", json=chat_payload)
    assert chat_res.status_code == 200, f"Chat failed: {chat_res.text}"
    chat_data = chat_res.json()
    ans1_safe = chat_data["answer"][:100].encode("ascii", "replace").decode("ascii")
    print("\nQuestion 1 Answer:\n", ans1_safe)
    print("\nQuestion 1 Sources:")
    for s in chat_data["sources"]:
        print(f"  Rank {s['rank']} | Page {s['page_number']} | Score {s['score']} | {s['paper_title']}")
    assert len(chat_data["sources"]) > 0, "Expected at least 1 source"
    assert chat_data["sources"][0]["page_number"] in [1, 2, 3]

    print("\n--- 7. Testing Chat API: Question 2 (RAG) ---")
    chat_payload2 = {
        "conversation_id": conv_id,
        "question": "How does RAG improve LLM responses?"
    }
    chat_res2 = client.post("/api/chat", json=chat_payload2)
    assert chat_res2.status_code == 200
    chat_data2 = chat_res2.json()
    ans2_safe = chat_data2["answer"][:100].encode("ascii", "replace").decode("ascii")
    print("\nQuestion 2 Answer:\n", ans2_safe)
    print("\nQuestion 2 Sources:")
    for s in chat_data2["sources"]:
        print(f"  Rank {s['rank']} | Page {s['page_number']} | Score {s['score']} | {s['paper_title']}")
    assert len(chat_data2["sources"]) > 0

    print("\n--- 8. Testing Chat API: Question 3 (Hallucination Resistance / Refusal) ---")
    chat_payload3 = {
        "conversation_id": conv_id,
        "question": "What is quantum entanglement cellular teleportation across black holes?"
    }
    chat_res3 = client.post("/api/chat", json=chat_payload3)
    assert chat_res3.status_code == 200
    chat_data3 = chat_res3.json()
    ans3_safe = chat_data3["answer"][:100].encode("ascii", "replace").decode("ascii")
    print("\nQuestion 3 Answer (Missing context test):\n", ans3_safe)

    print("\n--- 9. Verify PostgreSQL Records in messages and message_sources ---")
    with SessionLocal() as db:
        messages = db.query(Message).filter(Message.conversation_id == conv_id).all()
        print(f"Total messages in conversation {conv_id}: {len(messages)}")
        assert len(messages) >= 6, f"Expected at least 6 messages, got {len(messages)}"

        sources_count = db.query(MessageSource).count()
        print(f"Total message_sources saved in PostgreSQL: {sources_count}")
        assert sources_count > 0, "Expected saved message_sources in DB"

    print("\n--- 10. Testing Conversation Retrieval with Messages and Sources ---")
    conv_detail_res = client.get(f"/api/conversations/{conv_id}")
    assert conv_detail_res.status_code == 200
    detail = conv_detail_res.json()
    print(f"Conversation fetched with {len(detail['messages'])} messages.")
    for m in detail["messages"]:
        if m["sources"]:
            print(f"  Assistant message {m['id']} has {len(m['sources'])} cited sources in PostgreSQL.")

    print("\n=======================================================")
    print("ALL BACKEND VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=======================================================")


if __name__ == "__main__":
    run_tests()
