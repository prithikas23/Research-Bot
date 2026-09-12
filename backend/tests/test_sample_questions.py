import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.models import Conversation, Message, MessageSource


def test_10_questions():
    client = TestClient(app)

    # Fetch latest conversation or create one
    with SessionLocal() as db:
        conv = db.query(Conversation).order_by(Conversation.id.desc()).first()
        conv_id = conv.id if conv else None

    if not conv_id:
        c_res = client.post("/api/conversations", json={"title": "Evaluation Session"})
        conv_id = c_res.json()["id"]

    questions = [
        "What is Retrieval Augmented Generation?",
        "How does RAG improve LLM responses?",
        "What problem does the Transformer architecture solve?",
        "What is the role of attention in Transformers?",
        "What are the limitations of the proposed approach?",
        "What datasets were used?",
        "What evaluation metrics were reported?",
        "What are the main contributions of this paper?",
        "How does the proposed method compare with previous approaches?",
        "What future work is suggested?",
    ]

    print(f"=== Running Capstone Evaluation with {len(questions)} Sample Questions ===\n")

    results = []
    for idx, q in enumerate(questions, start=1):
        print(f"--- Question {idx}: {q} ---")
        res = client.post("/api/chat", json={"conversation_id": conv_id, "question": q})
        assert res.status_code == 200, f"Error on question {idx}: {res.text}"
        data = res.json()
        answer = data["answer"]
        sources = data["sources"]

        print(f"Answer: {answer[:200]}..." if len(answer) > 200 else f"Answer: {answer}")
        print("Top Sources:")
        for s in sources:
            print(f"  [Rank {s['rank']}] Page {s['page_number']} (Score: {s['score']}) - {s['paper_title']}")

        results.append({
            "question": q,
            "answer": answer,
            "sources_count": len(sources),
            "top_page": sources[0]["page_number"] if sources else None,
            "top_score": sources[0]["score"] if sources else None,
        })
        print()

    print("=== Capstone Evaluation Summary ===")
    for idx, r in enumerate(results, start=1):
        print(f"{idx}. Q: {r['question']}")
        print(f"   Top Source: Page {r['top_page']} | Score: {r['top_score']}")
        print(f"   Answer summary: {r['answer'][:90]}...\n")

    # Verify message sources in PostgreSQL
    with SessionLocal() as db:
        total_sources = db.query(MessageSource).count()
        total_messages = db.query(Message).count()
        print(f"Verification: PostgreSQL has {total_messages} messages and {total_sources} cited message_sources.")


if __name__ == "__main__":
    test_10_questions()
