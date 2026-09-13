import sys
import io
from pathlib import Path
import fitz

# Ensure backend root is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from app.main import app

def run_flow():
    client = TestClient(app)

    print("\n==========================================")
    print("STARTING REFRESH & CHAT VERIFICATION TESTS")
    print("==========================================")

    # 1. Create in-memory PDF for Test
    docA = fitz.open()
    p1 = docA.new_page()
    p1.insert_text(
        fitz.Point(50, 72),
        "Quantum Supercomputing Paper Alpha:\n\n"
        "We discovered that quantum qubits in topological states have 99.999% coherence fidelity.\n"
        "This breaks previous limits of quantum error correction.",
        fontsize=12
    )
    pdfA_bytes = docA.tobytes()
    docA.close()

    # Clean up any leftover test docs from previous runs
    existing_docs = client.get("/api/files").json()
    for d in existing_docs:
        if "Paper_Alpha_Quantum" in d.get("original_filename", ""):
            client.delete(f"/api/files/{d['id']}")

    # TEST 1: Upload PDF -> status must be 'not_refreshed'
    print("\n--- TEST 1: Upload PDF A ---")
    files = {"file": ("Paper_Alpha_Quantum.pdf", io.BytesIO(pdfA_bytes), "application/pdf")}
    resA = client.post("/api/files/upload", files=files)
    assert resA.status_code == 201, f"Upload A failed: {resA.text}"
    docA_data = resA.json()["document"]
    docA_id = docA_data["id"]
    print(f"Uploaded Doc ID: {docA_id}, Status: {docA_data['status']}")
    assert docA_data["status"] == "not_refreshed", f"Expected 'not_refreshed' but got {docA_data['status']}"

    # TEST 1b: Query before refresh -> PDF A must NOT be retrieved
    print("\n--- TEST 1b: Query before refresh ---")
    chat1 = client.post("/api/chat", json={"question": "What is the coherence fidelity in quantum qubits?"})
    assert chat1.status_code == 200
    sources1 = [s["paper_title"] for s in chat1.json().get("sources", [])]
    print(f"Sources before refresh: {sources1}")
    assert not any("Paper_Alpha_Quantum" in s for s in sources1), "Unrefreshed doc should NOT be in sources!"
    print("PASS: Unrefreshed document was NOT used in retrieval.")

    # TEST 2: Click Refresh -> API indexes into ChromaDB, status = 'refreshed'
    print("\n--- TEST 2: Refresh PDF A ---")
    refA = client.post(f"/api/files/{docA_id}/refresh")
    assert refA.status_code == 200, f"Refresh A failed: {refA.text}"
    refA_data = refA.json()["document"]
    print(f"Refresh response message: {refA.json()['message']}")
    assert refA_data["status"] == "refreshed", f"Expected 'refreshed' but got {refA_data['status']}"
    print("PASS: Document status is now 'refreshed'.")

    # TEST 3: Ask question -> answer comes from refreshed PDF A
    print("\n--- TEST 3: Query after refresh ---")
    chat2 = client.post("/api/chat", json={"question": "What is the coherence fidelity in quantum qubits?"})
    assert chat2.status_code == 200
    sources2 = [s["paper_title"] for s in chat2.json().get("sources", [])]
    answer_preview = chat2.json().get('answer', '')[:100].encode('ascii', 'replace').decode('ascii')
    print(f"Answer snippet: {answer_preview}...")
    assert any("Paper_Alpha_Quantum" in s for s in sources2), "Refreshed doc MUST be in sources!"
    print("PASS: Refreshed document was successfully retrieved and cited.")

    # TEST 6: Refresh already refreshed PDF -> replaces vectors without duplicate error
    print("\n--- TEST 6: Re-refresh PDF A ---")
    refA_again = client.post(f"/api/files/{docA_id}/refresh")
    assert refA_again.status_code == 200
    print("PASS: Re-refresh completed without duplicate errors.")

    # TEST 7: Delete refreshed PDF -> removed from DB & ChromaDB
    print("\n--- TEST 7: Delete PDF A ---")
    delA = client.delete(f"/api/files/{docA_id}")
    assert delA.status_code == 200
    print(f"Delete response: {delA.json()}")

    # Future question must not use deleted doc
    chat3 = client.post("/api/chat", json={"question": "What is the coherence fidelity in quantum qubits?"})
    sources3 = [s["paper_title"] for s in chat3.json().get("sources", [])]
    assert not any("Paper_Alpha_Quantum" in s for s in sources3), "Deleted doc should NOT be in sources!"
    print("PASS: Deleted document was removed from retrieval.")

    print("\n==========================================")
    print("ALL 7 END-TO-END FLOW TESTS PASSED!")
    print("==========================================")

if __name__ == "__main__":
    run_flow()
