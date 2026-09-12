import { useState } from "react";
import axios from "axios";
import type { ChatResponse, Source, UploadResponse } from "./types";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api";

const api = axios.create({
  baseURL: API_BASE_URL,
});

function App() {
  const [file, setFile] = useState<File | null>(null);
  const [uploadStatus, setUploadStatus] = useState<string>("");
  const [question, setQuestion] = useState<string>("");
  const [answer, setAnswer] = useState<string>("");
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState<boolean>(false);

  async function checkBackend(): Promise<void> {
    try {
      const response = await api.get<{ status: string }>("/health");
      setUploadStatus(`Backend: ${response.data.status}`);
    } catch {
      setUploadStatus("Backend is not reachable");
    }
  }

  async function uploadFile(): Promise<void> {
    if (!file) {
      setUploadStatus("Please select a PDF first.");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    setUploadStatus("Uploading...");

    try {
      const response = await api.post<UploadResponse>(
        "/documents/upload",
        formData
      );
      setUploadStatus(response.data.message || "Upload successful");
    } catch (error: unknown) {
      if (axios.isAxiosError(error)) {
        setUploadStatus(
          error.response?.data?.detail ||
            "Upload endpoint is not implemented yet."
        );
      } else {
        setUploadStatus("Upload failed.");
      }
    }
  }

  async function askQuestion(): Promise<void> {
    if (!question.trim()) return;

    setLoading(true);
    setAnswer("");
    setSources([]);

    try {
      const response = await api.post<ChatResponse>("/chat", {
        conversation_id: null,
        question,
      });

      setAnswer(response.data.answer || "");
      setSources(response.data.sources || []);
    } catch (error: unknown) {
      if (axios.isAxiosError(error)) {
        setAnswer(
          error.response?.data?.detail ||
            "Chat endpoint is not implemented yet."
        );
      } else {
        setAnswer("Chat request failed.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      <header className="header">
        <div>
          <h1>Research Paper Answer Bot</h1>
          <p>Ask questions from your uploaded research papers.</p>
        </div>

        <button className="secondary-btn" onClick={checkBackend}>
          Check Backend
        </button>
      </header>

      <main className="container">
        <section className="card">
          <h2>Upload Research Paper</h2>

          <p className="muted">
            Upload a PDF. The FastAPI backend will store it locally, extract
            pages, create chunks, and index them in ChromaDB.
          </p>

          <div className="upload-row">
            <input
              type="file"
              accept=".pdf,application/pdf"
              onChange={(event) =>
                setFile(event.target.files?.[0] || null)
              }
            />

            <button className="primary-btn" onClick={uploadFile}>
              Upload PDF
            </button>
          </div>

          {file && <p className="file-name">Selected: {file.name}</p>}
          {uploadStatus && <p className="status">{uploadStatus}</p>}
        </section>

        <section className="card chat-card">
          <h2>Ask Your Research Papers</h2>

          <textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Example: What is the main contribution of this paper?"
            rows={5}
          />

          <button
            className="primary-btn ask-btn"
            onClick={askQuestion}
            disabled={loading}
          >
            {loading ? "Searching..." : "Ask Question"}
          </button>

          {answer && (
            <div className="answer">
              <h3>Answer</h3>
              <p>{answer}</p>
            </div>
          )}

          {sources.length > 0 && (
            <div className="sources">
              <h3>Top Sources</h3>

              {sources.slice(0, 3).map((source, index) => (
                <div className="source-card" key={`${source.paper_title}-${source.page_number}-${index}`}>
                  <strong>{source.paper_title || "Research Paper"}</strong>

                  <span>Page {source.page_number ?? "N/A"}</span>

                  <span>
                    Score:{" "}
                    {source.score != null
                      ? Number(source.score).toFixed(4)
                      : "N/A"}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

export default App;
