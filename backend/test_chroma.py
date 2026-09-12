from app.services.vector_service import add_documents, search_documents, collection_count

# Temporary fixed-size vectors only for testing Chroma.
# Replace these with real Hugging Face/OpenAI embeddings in the RAG pipeline.

add_documents(
    ids=["test_chunk_1", "test_chunk_2"],
    documents=[
        "Retrieval Augmented Generation retrieves relevant context before generation.",
        "Transformers use attention mechanisms to process sequence information."
    ],
    metadatas=[
        {
            "document_id": 1,
            "paper_title": "RAG Test Paper",
            "page_number": 1,
            "chunk_index": 0
        },
        {
            "document_id": 2,
            "paper_title": "Transformer Test Paper",
            "page_number": 2,
            "chunk_index": 0
        }
    ],
    embeddings=[
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0]
    ]
)

print("Chroma document count:", collection_count())

result = search_documents([1.0, 0.0, 0.0], top_k=2)
print(result)
