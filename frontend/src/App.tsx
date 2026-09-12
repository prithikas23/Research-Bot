import { useState, useEffect, useRef } from "react";
import axios from "axios";
import ReactMarkdown from "react-markdown";
import type {
  ChatResponse,
  Source,
  UploadResponse,
  DocumentItem,
  ConversationItem,
  MessageItem,
} from "./types";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api";

const api = axios.create({
  baseURL: API_BASE_URL,
});

function App() {
  // Document state
  const [file, setFile] = useState<File | null>(null);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadStatus, setUploadStatus] = useState<string>("");

  // Conversation & Chat state
  const [conversations, setConversations] = useState<ConversationItem[]>([]);
  const [activeConvId, setActiveConvId] = useState<number | null>(null);
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [question, setQuestion] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);

  // Backend Health state
  const [backendStatus, setBackendStatus] = useState<{
    status: string;
    database?: string;
    chroma?: string;
  } | null>(null);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  // Initial load
  useEffect(() => {
    checkBackend();
    fetchDocuments();
    fetchConversations();
  }, []);

  // Auto-scroll messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // Load conversation details when active conversation changes
  useEffect(() => {
    if (activeConvId) {
      loadConversationMessages(activeConvId);
    } else {
      setMessages([]);
    }
  }, [activeConvId]);

  async function checkBackend(): Promise<void> {
    try {
      const response = await api.get<{
        status: string;
        database?: string;
        chroma?: string;
      }>("/health");
      setBackendStatus(response.data);
    } catch {
      setBackendStatus({ status: "offline", database: "disconnected", chroma: "disconnected" });
    }
  }

  async function fetchDocuments(): Promise<void> {
    try {
      const response = await api.get<DocumentItem[]>("/documents");
      setDocuments(response.data);
    } catch (err) {
      console.error("Failed to fetch documents:", err);
    }
  }

  async function fetchConversations(): Promise<void> {
    try {
      const response = await api.get<ConversationItem[]>("/conversations");
      setConversations(response.data);
      if (!activeConvId && response.data.length > 0) {
        setActiveConvId(response.data[0].id);
      }
    } catch (err) {
      console.error("Failed to fetch conversations:", err);
    }
  }

  async function loadConversationMessages(convId: number): Promise<void> {
    try {
      const response = await api.get<{ messages: MessageItem[] }>(`/conversations/${convId}`);
      setMessages(response.data.messages || []);
    } catch (err) {
      console.error(`Failed to load messages for conversation ${convId}:`, err);
    }
  }

  async function handleCreateNewConversation(): Promise<void> {
    try {
      const response = await api.post<ConversationItem>("/conversations", {
        title: "New Research Discussion",
      });
      setConversations([response.data, ...conversations]);
      setActiveConvId(response.data.id);
      setMessages([]);
    } catch (err) {
      console.error("Failed to create conversation:", err);
    }
  }

  async function handleDeleteConversation(convId: number, e: React.MouseEvent): Promise<void> {
    e.stopPropagation();
    try {
      await api.delete(`/conversations/${convId}`);
      const updated = conversations.filter((c) => c.id !== convId);
      setConversations(updated);
      if (activeConvId === convId) {
        setActiveConvId(updated.length > 0 ? updated[0].id : null);
      }
    } catch (err) {
      console.error("Failed to delete conversation:", err);
    }
  }

  async function handleDeleteDocument(docId: number): Promise<void> {
    try {
      await api.delete(`/documents/${docId}`);
      setDocuments(documents.filter((d) => d.id !== docId));
      setUploadStatus("Document deleted successfully.");
    } catch (err) {
      console.error("Failed to delete document:", err);
      setUploadStatus("Failed to delete document.");
    }
  }

  async function uploadFile(): Promise<void> {
    if (!file) {
      setUploadStatus("Please select a research paper PDF first.");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    setIsUploading(true);
    setUploadStatus("Uploading and extracting page chunks into ChromaDB...");

    try {
      const response = await api.post<UploadResponse>("/documents/upload", formData);
      setUploadStatus(response.data.message || "Paper indexed successfully!");
      setFile(null);
      await fetchDocuments();
    } catch (error: unknown) {
      if (axios.isAxiosError(error)) {
        setUploadStatus(error.response?.data?.detail || "Upload failed.");
      } else {
        setUploadStatus("Upload encountered an unexpected error.");
      }
    } finally {
      setIsUploading(false);
    }
  }

  async function askQuestion(e?: React.FormEvent): Promise<void> {
    if (e) e.preventDefault();
    const cleanQuestion = question.trim();
    if (!cleanQuestion || loading) return;

    const userMessage: MessageItem = {
      id: Date.now(),
      conversation_id: activeConvId || 0,
      role: "user",
      content: cleanQuestion,
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setQuestion("");
    setLoading(true);

    try {
      const response = await api.post<ChatResponse>("/chat", {
        conversation_id: activeConvId,
        question: cleanQuestion,
      });

      const newConvId = response.data.conversation_id;
      if (!activeConvId && newConvId) {
        setActiveConvId(newConvId);
        await fetchConversations();
      }

      const assistantMessage: MessageItem = {
        id: Date.now() + 1,
        conversation_id: newConvId,
        role: "assistant",
        content: response.data.answer || "No answer generated.",
        created_at: new Date().toISOString(),
        sources: response.data.sources || [],
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error: unknown) {
      const errorText = axios.isAxiosError(error)
        ? error.response?.data?.detail || "Chat request failed."
        : "Failed to connect to backend.";
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          conversation_id: activeConvId || 0,
          role: "assistant",
          content: `⚠️ ${errorText}`,
          created_at: new Date().toISOString(),
          sources: [],
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  const sampleQuestions = [
    "What is Retrieval Augmented Generation?",
    "What is the role of attention in Transformers?",
    "How does RAG improve LLM responses?",
    "What are the main limitations and future work suggested?",
  ];

  return (
    <div className="app-layout">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="logo-badge">
            <span className="logo-icon">📄</span>
            <div>
              <h2>Research Bot</h2>
              <span className="app-subtitle">Capstone RAG System</span>
            </div>
          </div>
          <button
            id="new-chat-btn"
            className="primary-btn new-chat-btn"
            onClick={handleCreateNewConversation}
          >
            + New Chat
          </button>
        </div>

        {/* Conversations List */}
        <div className="sidebar-section">
          <h3>Conversations</h3>
          <div className="conversations-list">
            {conversations.length === 0 ? (
              <p className="empty-text">No conversations yet.</p>
            ) : (
              conversations.map((c) => (
                <div
                  key={c.id}
                  id={`conv-item-${c.id}`}
                  className={`conversation-item ${c.id === activeConvId ? "active" : ""}`}
                  onClick={() => setActiveConvId(c.id)}
                >
                  <span className="conv-title" title={c.title}>
                    💬 {c.title || `Chat #${c.id}`}
                  </span>
                  <button
                    className="delete-icon-btn"
                    title="Delete conversation"
                    onClick={(e) => handleDeleteConversation(c.id, e)}
                  >
                    ×
                  </button>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Uploaded Documents List */}
        <div className="sidebar-section documents-section">
          <div className="section-title-row">
            <h3>Uploaded Papers ({documents.length})</h3>
          </div>
          <div className="documents-list">
            {documents.length === 0 ? (
              <p className="empty-text">No research papers uploaded yet.</p>
            ) : (
              documents.map((doc) => (
                <div key={doc.id} className="doc-item" id={`doc-item-${doc.id}`}>
                  <div className="doc-info">
                    <span className="doc-name" title={doc.original_filename}>
                      {doc.original_filename}
                    </span>
                    <div className="doc-meta-tags">
                      <span className={`status-badge ${doc.status}`}>
                        {doc.status}
                      </span>
                      {doc.page_count && (
                        <span className="meta-tag">{doc.page_count} pages</span>
                      )}
                    </div>
                  </div>
                  <button
                    className="delete-icon-btn"
                    title="Delete document"
                    onClick={() => handleDeleteDocument(doc.id)}
                  >
                    ×
                  </button>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Backend Status Footer */}
        <div className="sidebar-footer">
          <div className="health-status">
            <span
              className={`health-dot ${backendStatus?.status === "ok" ? "online" : "offline"}`}
            />
            <span>
              Backend: <strong>{backendStatus?.status || "Checking..."}</strong>
            </span>
          </div>
          <button className="text-link-btn" onClick={checkBackend}>
            Refresh
          </button>
        </div>
      </aside>

      {/* Main Workspace */}
      <main className="main-content">
        {/* Top Navbar */}
        <header className="top-nav">
          <div>
            <h1>Research Paper Answer Bot</h1>
            <p>
              Retrieval-Augmented Generation with page-aware citations and Groq LLM
            </p>
          </div>
        </header>

        {/* PDF Upload Card */}
        <section className="upload-banner-card" id="upload-section">
          <div className="upload-card-content">
            <div className="upload-instructions">
              <h3>Upload Research Paper</h3>
              <p>
                Upload a research PDF. It will be stored locally, parsed page-by-page,
                chunked with page numbers, and indexed in ChromaDB.
              </p>
            </div>

            <div className="upload-action-row">
              <input
                id="pdf-file-input"
                type="file"
                accept=".pdf,application/pdf"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                disabled={isUploading}
              />
              <button
                id="upload-btn"
                className="primary-btn"
                onClick={uploadFile}
                disabled={!file || isUploading}
              >
                {isUploading ? "Processing..." : "Upload & Index PDF"}
              </button>
            </div>
          </div>

          {uploadStatus && (
            <div
              className={`upload-alert ${
                uploadStatus.includes("failed") || uploadStatus.includes("Error")
                  ? "alert-error"
                  : "alert-info"
              }`}
            >
              {uploadStatus}
            </div>
          )}
        </section>

        {/* Chat Stream & Interaction */}
        <section className="chat-container">
          <div className="messages-stream">
            {messages.length === 0 ? (
              <div className="empty-chat-placeholder">
                <div className="welcome-card">
                  <h2>Welcome to Research Paper Answer Bot</h2>
                  <p>
                    Ask questions grounded in the context of your uploaded papers.
                    Every answer is strictly supported with Top-3 source citations
                    including Paper Title, Page Number, and Relevance Score.
                  </p>
                  <div className="suggested-queries">
                    <h4>Sample Research Questions:</h4>
                    <div className="query-pills">
                      {sampleQuestions.map((sq, i) => (
                        <button
                          key={i}
                          className="query-pill"
                          onClick={() => {
                            setQuestion(sq);
                          }}
                        >
                          {sq}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`message-row ${msg.role === "user" ? "user-row" : "assistant-row"}`}
                >
                  <div className="message-avatar">
                    {msg.role === "user" ? "👤" : "🤖"}
                  </div>
                  <div className="message-bubble">
                    <div className="message-header">
                      <span className="sender-name">
                        {msg.role === "user" ? "You" : "Research Assistant"}
                      </span>
                      <span className="message-time">
                        {new Date(msg.created_at).toLocaleTimeString([], {
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </span>
                    </div>

                    <div className="message-text">
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>

                    {/* Top-3 Sources Display */}
                    {msg.sources && msg.sources.length > 0 && (
                      <div className="sources-container" id="sources-display">
                        <div className="sources-header">
                          <span className="sources-icon">📚</span>
                          <h4>Top {msg.sources.length} Cited Sources</h4>
                        </div>

                        <div className="sources-grid">
                          {msg.sources.slice(0, 3).map((source, sIdx) => (
                            <div
                              className="source-card"
                              key={sIdx}
                              id={`source-card-${sIdx + 1}`}
                            >
                              <div className="source-rank-badge">
                                Rank #{source.rank || sIdx + 1}
                              </div>
                              <div className="source-details">
                                <h5 className="source-paper-title" title={source.paper_title}>
                                  {source.paper_title || "Research Paper"}
                                </h5>
                                <div className="source-meta-row">
                                  <span className="source-page-tag">
                                    Page {source.page_number ?? "N/A"}
                                  </span>
                                  <span className="source-score-tag">
                                    Relevance:{" "}
                                    <strong>
                                      {source.score != null
                                        ? Number(source.score).toFixed(4)
                                        : "N/A"}
                                    </strong>
                                  </span>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}

            {loading && (
              <div className="message-row assistant-row">
                <div className="message-avatar">🤖</div>
                <div className="message-bubble loading-bubble">
                  <div className="typing-indicator">
                    <span />
                    <span />
                    <span />
                  </div>
                  <span className="loading-text">
                    Retrieving research chunks & generating grounded answer...
                  </span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Chat Input Bar */}
          <form className="chat-input-bar" onSubmit={askQuestion}>
            <textarea
              id="question-input"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask a question about the uploaded research papers (e.g., What is the role of attention?)..."
              rows={2}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  askQuestion();
                }
              }}
            />
            <button
              id="send-question-btn"
              type="submit"
              className="primary-btn send-btn"
              disabled={loading || !question.trim()}
            >
              {loading ? "Searching..." : "Ask Question"}
            </button>
          </form>
        </section>
      </main>
    </div>
  );
}

export default App;
