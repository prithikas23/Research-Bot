import React, { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import type {
  FileItem,
  ChatMessage,
  ChatConversation,
} from "./types";
import { getFiles, uploadFile, refreshFile, deleteFile } from "./api/files";
import { askQuestion } from "./api/chat";
import {
  loadChatHistory,
  saveChatHistory,
  generateChatTitle,
} from "./utils/storage";

function formatBytes(bytes?: number): string {
  if (!bytes) return "0 KB";
  const kb = bytes / 1024;
  if (kb < 1024) return `${Math.round(kb)} KB`;
  return `${(kb / 1024).toFixed(1)} MB`;
}

export default function App() {
  // Navigation: "chat" | "files"
  const [currentTab, setCurrentTab] = useState<"chat" | "files">("chat");
  const [sidebarOpen, setSidebarOpen] = useState<boolean>(false);

  // Files state
  const [files, setFiles] = useState<FileItem[]>([]);
  const [refreshingIds, setRefreshingIds] = useState<Set<number>>(new Set());
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadFeedback, setUploadFeedback] = useState<{
    type: "success" | "error" | "info";
    message: string;
  } | null>(null);
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Chat & History state (persisted via localStorage)
  const [conversations, setConversations] = useState<ChatConversation[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState<string>("");
  const [isThinking, setIsThinking] = useState<boolean>(false);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  // Load files from backend & chat history from localStorage on initial render
  useEffect(() => {
    loadFiles();
    const saved = loadChatHistory();
    setConversations(saved);
    if (saved.length > 0) {
      setActiveConvId(saved[0].id);
      setMessages(saved[0].messages || []);
    }
  }, []);

  // Auto-scroll chat to bottom
  useEffect(() => {
    if (currentTab === "chat") {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isThinking, currentTab]);

  // Refreshed files count for status indicator & header
  const refreshedCount = files.filter(
    (f) => f.status === "refreshed" || f.status === "completed"
  ).length;

  async function loadFiles() {
    try {
      const data = await getFiles();
      setFiles(data);
    } catch (err: unknown) {
      console.error("Failed to load files:", err);
    }
  }

  // Handle uploading PDF
  async function handleFileSelect(selectedFile: File) {
    if (!selectedFile.name.toLowerCase().endsWith(".pdf")) {
      setUploadFeedback({
        type: "error",
        message: "Only PDF files are supported.",
      });
      return;
    }

    setIsUploading(true);
    setUploadFeedback({
      type: "info",
      message: `Uploading ${selectedFile.name}...`,
    });

    try {
      const newDoc = await uploadFile(selectedFile);
      setFiles((prev) => [newDoc, ...prev.filter((f) => f.id !== newDoc.id)]);
      setUploadFeedback({
        type: "success",
        message: `"${selectedFile.name}" uploaded. Click "Refresh" to index it for chat.`,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to upload file.";
      setUploadFeedback({ type: "error", message: msg });
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  // Handle refreshing / indexing file
  async function handleRefresh(fileId: number) {
    setRefreshingIds((prev) => new Set(prev).add(fileId));
    setFiles((prev) =>
      prev.map((f) => (f.id === fileId ? { ...f, status: "refreshing" } : f))
    );

    try {
      const updated = await refreshFile(fileId);
      setFiles((prev) =>
        prev.map((f) => (f.id === fileId ? updated : f))
      );
      setUploadFeedback({
        type: "success",
        message: `Indexed "${updated.original_filename}" into ChromaDB successfully!`,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Refresh failed.";
      setFiles((prev) =>
        prev.map((f) => (f.id === fileId ? { ...f, status: "failed" } : f))
      );
      setUploadFeedback({ type: "error", message: msg });
    } finally {
      setRefreshingIds((prev) => {
        const next = new Set(prev);
        next.delete(fileId);
        return next;
      });
    }
  }

  // Handle deleting file
  async function handleDeleteFile(fileId: number) {
    const target = files.find((f) => f.id === fileId);
    if (!target) return;

    try {
      await deleteFile(fileId);
      setFiles((prev) => prev.filter((f) => f.id !== fileId));
      setUploadFeedback({
        type: "info",
        message: `"${target.original_filename}" deleted.`,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Delete failed.";
      setUploadFeedback({ type: "error", message: msg });
    }
  }

  // Start a new chat
  function handleNewChat() {
    // If current conversation has messages and wasn't saved, save it
    if (activeConvId && messages.length > 0) {
      persistConversation(activeConvId, messages);
    }
    setActiveConvId(null);
    setMessages([]);
    setQuestion("");
    setCurrentTab("chat");
    setSidebarOpen(false);
  }

  // Select an existing conversation from history
  function handleSelectConversation(conv: ChatConversation) {
    // Persist previous if dirty
    if (activeConvId && activeConvId !== conv.id && messages.length > 0) {
      persistConversation(activeConvId, messages);
    }
    setActiveConvId(conv.id);
    setMessages(conv.messages || []);
    setCurrentTab("chat");
    setSidebarOpen(false);
  }

  // Delete conversation from history
  function handleDeleteConversation(id: string, e: React.MouseEvent) {
    e.stopPropagation();
    const updated = conversations.filter((c) => c.id !== id);
    setConversations(updated);
    saveChatHistory(updated);

    if (activeConvId === id) {
      if (updated.length > 0) {
        setActiveConvId(updated[0].id);
        setMessages(updated[0].messages || []);
      } else {
        setActiveConvId(null);
        setMessages([]);
      }
    }
  }

  // Helper to persist conversation to state & localStorage
  function persistConversation(convId: string, msgs: ChatMessage[]) {
    setConversations((prev) => {
      const existingIdx = prev.findIndex((c) => c.id === convId);
      let updated: ChatConversation[];
      const firstUserMsg = msgs.find((m) => m.role === "user")?.content || "";
      const title = firstUserMsg ? generateChatTitle(firstUserMsg) : "New chat";

      if (existingIdx >= 0) {
        updated = [...prev];
        updated[existingIdx] = {
          ...updated[existingIdx],
          title: updated[existingIdx].title || title,
          updatedAt: new Date().toISOString(),
          messages: msgs,
        };
      } else {
        const newConv: ChatConversation = {
          id: convId,
          title,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
          messages: msgs,
        };
        updated = [newConv, ...prev];
      }
      saveChatHistory(updated);
      return updated;
    });
  }

  // Send a question to RAG
  async function handleSendQuestion(e?: React.FormEvent) {
    if (e) e.preventDefault();
    const cleanQuestion = question.trim();
    if (!cleanQuestion || isThinking) return;

    // Resolve or create conversation ID
    const currentConvId = activeConvId || `chat_${Date.now()}`;
    if (!activeConvId) {
      setActiveConvId(currentConvId);
    }

    const userMsg: ChatMessage = {
      id: `msg_${Date.now()}`,
      role: "user",
      content: cleanQuestion,
      timestamp: new Date().toISOString(),
    };

    const newMessages = [...messages, userMsg];
    setMessages(newMessages);
    setQuestion("");
    setIsThinking(true);

    try {
      const response = await askQuestion(cleanQuestion);

      const assistantMsg: ChatMessage = {
        id: `msg_${Date.now() + 1}`,
        role: "assistant",
        content: response.answer || "No response received.",
        timestamp: new Date().toISOString(),
        sources: response.sources || [],
      };

      const finalMessages = [...newMessages, assistantMsg];
      setMessages(finalMessages);
      persistConversation(currentConvId, finalMessages);
    } catch (err: unknown) {
      const errorMsg =
        err instanceof Error
          ? err.message
          : "Could not generate an answer. Please try again.";

      const assistantErrorMsg: ChatMessage = {
        id: `msg_${Date.now() + 1}`,
        role: "assistant",
        content: `⚠️ ${errorMsg}`,
        timestamp: new Date().toISOString(),
        sources: [],
      };

      const finalMessages = [...newMessages, assistantErrorMsg];
      setMessages(finalMessages);
      persistConversation(currentConvId, finalMessages);
    } finally {
      setIsThinking(false);
    }
  }

  // Active chat title for header
  const activeConversation = conversations.find((c) => c.id === activeConvId);
  const activeChatTitle = activeConversation ? activeConversation.title : "New chat";

  return (
    <div className="app-container">
      {/* Mobile top bar with hamburger menu */}
      <div className="mobile-topbar">
        <button
          className="hamburger-btn"
          onClick={() => setSidebarOpen((prev) => !prev)}
          aria-label="Toggle navigation"
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="3" y1="12" x2="21" y2="12" />
            <line x1="3" y1="6" x2="21" y2="6" />
            <line x1="3" y1="18" x2="21" y2="18" />
          </svg>
        </button>
        <span style={{ fontWeight: 600, fontSize: 16 }}>Research Bot</span>
        <div style={{ width: 22 }} />
      </div>

      {/* Backdrop for mobile drawer */}
      <div
        className={`sidebar-backdrop ${sidebarOpen ? "open" : ""}`}
        onClick={() => setSidebarOpen(false)}
      />

      {/* Sidebar */}
      <aside className={`sidebar ${sidebarOpen ? "open" : ""}`}>
        {/* Brand */}
        <div className="sidebar-brand">
          <div className="brand-icon-box">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="4" />
              <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41" />
            </svg>
          </div>
          <span className="brand-title">Research Bot</span>
        </div>

        {/* Navigation Tabs */}
        <nav className="sidebar-nav">
          <button
            className={`nav-item ${currentTab === "chat" ? "active" : ""}`}
            onClick={() => {
              setCurrentTab("chat");
              setSidebarOpen(false);
            }}
          >
            <div className="nav-item-left">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
              <span>Chat</span>
            </div>
          </button>

          <button
            className={`nav-item ${currentTab === "files" ? "active" : ""}`}
            onClick={() => {
              setCurrentTab("files");
              setSidebarOpen(false);
            }}
          >
            <div className="nav-item-left">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
              </svg>
              <span>Files</span>
            </div>
            <span className="nav-badge">{files.length}</span>
          </button>
        </nav>

        {/* + New Chat Button */}
        <button className="new-chat-button" onClick={handleNewChat}>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          <span>New chat</span>
        </button>

        {/* History Section */}
        <div className="history-section">
          <div className="history-header">HISTORY</div>
          <div className="history-list">
            {conversations.length === 0 ? (
              <div className="history-empty-text">No previous chats</div>
            ) : (
              conversations.map((c) => (
                <div
                  key={c.id}
                  className={`history-item ${c.id === activeConvId ? "active" : ""}`}
                  onClick={() => handleSelectConversation(c)}
                >
                  <div className="history-item-left">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                    </svg>
                    <span className="history-item-title" title={c.title}>
                      {c.title || "Untitled chat"}
                    </span>
                  </div>
                  <button
                    className="history-delete-btn"
                    title="Delete chat"
                    onClick={(e) => handleDeleteConversation(c.id, e)}
                  >
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <line x1="18" y1="6" x2="6" y2="18" />
                      <line x1="6" y1="6" x2="18" y2="18" />
                    </svg>
                  </button>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Ready indicator footer */}
        <div className="sidebar-footer">
          <div className="ready-status-row">
            <span className="ready-dot" />
            <span>{refreshedCount} files ready to search</span>
          </div>
        </div>
      </aside>

      {/* Main Workspace */}
      <main className="main-workspace">
        {/* ===================================================================
            SCREEN 1: CHAT SCREEN
           =================================================================== */}
        {currentTab === "chat" && (
          <div className="chat-screen">
            {/* Top header */}
            <div className="chat-header">
              <h1 className="chat-title">{activeChatTitle}</h1>
              <div className="chat-subtitle">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                  <line x1="16" y1="13" x2="8" y2="13" />
                  <line x1="16" y1="17" x2="8" y2="17" />
                  <polyline points="10 9 9 9 8 9" />
                </svg>
                <span>Answering from {refreshedCount} refreshed files</span>
              </div>
            </div>

            {/* Messages Scroll Area */}
            <div className="chat-messages-container">
              {messages.length === 0 ? (
                <div className="chat-empty-state">
                  <div className="empty-state-icon-box">
                    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <rect x="3" y="11" width="18" height="10" rx="3" />
                      <circle cx="12" cy="5" r="2" />
                      <path d="M12 7v4" />
                      <line x1="8" y1="16" x2="8.01" y2="16" strokeWidth="3" strokeLinecap="round" />
                      <line x1="16" y1="16" x2="16.01" y2="16" strokeWidth="3" strokeLinecap="round" />
                    </svg>
                  </div>
                  <h2 className="empty-state-title">Ask something about your files</h2>
                  <p className="empty-state-desc">
                    Questions are answered only from PDFs marked "Refreshed" in the Files tab.
                  </p>
                </div>
              ) : (
                messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`chat-message-row ${msg.role === "user" ? "user-row" : "assistant-row"}`}
                  >
                    {msg.role === "assistant" && (
                      <div className="message-avatar-box assistant-avatar">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <rect x="3" y="11" width="18" height="10" rx="3" />
                          <circle cx="12" cy="5" r="2" />
                          <path d="M12 7v4" />
                          <line x1="8" y1="16" x2="8.01" y2="16" strokeWidth="3" strokeLinecap="round" />
                          <line x1="16" y1="16" x2="16.01" y2="16" strokeWidth="3" strokeLinecap="round" />
                        </svg>
                      </div>
                    )}

                    <div className={`message-bubble ${msg.role === "user" ? "user-bubble" : "assistant-bubble"}`}>
                      <div className="message-content">
                        <ReactMarkdown>{msg.content}</ReactMarkdown>
                      </div>
                    </div>
                  </div>
                ))
              )}

              {/* Thinking / Loading indicator */}
              {isThinking && (
                <div className="chat-message-row assistant-row">
                  <div className="message-avatar-box assistant-avatar">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <rect x="3" y="11" width="18" height="10" rx="3" />
                      <circle cx="12" cy="5" r="2" />
                      <path d="M12 7v4" />
                    </svg>
                  </div>
                  <div className="message-bubble assistant-bubble" style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <div className="typing-dots">
                      <span />
                      <span />
                      <span />
                    </div>
                    <span style={{ fontSize: 13.5, color: "var(--text-muted)" }}>
                      Searching refreshed documents & generating answer...
                    </span>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Bottom floating composer */}
            <div className="chat-input-wrapper">
              <form className="chat-input-card" onSubmit={handleSendQuestion}>
                <input
                  className="chat-input-field"
                  type="text"
                  placeholder="Ask a question about your uploaded PDFs..."
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  disabled={isThinking}
                />
                <button
                  type="submit"
                  className="chat-send-btn"
                  disabled={!question.trim() || isThinking}
                  title="Send message"
                >
                  <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.3">
                    <line x1="22" y1="2" x2="11" y2="13" />
                    <polygon points="22 2 15 22 11 13 2 9 22 2" />
                  </svg>
                </button>
              </form>
            </div>
          </div>
        )}

        {/* ===================================================================
            SCREEN 2: FILES SCREEN
           =================================================================== */}
        {currentTab === "files" && (
          <div className="files-screen">
            {/* Header */}
            <div className="files-header">
              <h1 className="files-title">Your files</h1>
              <p className="files-subtitle">Upload PDFs to make them searchable in chat</p>
            </div>

            {/* Upload Dropzone */}
            <div
              className={`upload-dropzone ${isDragging ? "dragging" : ""}`}
              onClick={() => fileInputRef.current?.click()}
              onDragOver={(e) => {
                e.preventDefault();
                setIsDragging(true);
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setIsDragging(false);
                if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                  handleFileSelect(e.dataTransfer.files[0]);
                }
              }}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,application/pdf"
                style={{ display: "none" }}
                onChange={(e) => {
                  if (e.target.files && e.target.files[0]) {
                    handleFileSelect(e.target.files[0]);
                  }
                }}
              />
              <div className="upload-icon-box">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="17 8 12 3 7 8" />
                  <line x1="12" y1="3" x2="12" y2="15" />
                </svg>
              </div>
              <span className="upload-prompt-text">
                {isUploading ? "Uploading PDF..." : "Drop a PDF here, or click to browse"}
              </span>
              <span className="upload-prompt-subtext">
                Files are refreshed only when you click Refresh to index for chat
              </span>
            </div>

            {/* Alert / Feedback Banner */}
            {uploadFeedback && (
              <div className={`alert-banner alert-${uploadFeedback.type}`}>
                <span>{uploadFeedback.message}</span>
                <button
                  style={{ background: "none", border: "none", cursor: "pointer", color: "inherit", fontWeight: 700 }}
                  onClick={() => setUploadFeedback(null)}
                >
                  ✕
                </button>
              </div>
            )}

            {/* All Files Table */}
            <div className="files-table-section">
              <h2 className="files-section-title">All files</h2>

              <div className="files-table-container">
                {files.length === 0 ? (
                  <div className="empty-files-placeholder">
                    No PDF documents uploaded yet. Drop a PDF above to get started.
                  </div>
                ) : (
                  <table className="files-table">
                    <thead>
                      <tr>
                        <th>Name</th>
                        <th>Status</th>
                        <th style={{ textAlign: "right", paddingRight: 32 }}>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {files.map((file) => {
                        const isRefreshing = refreshingIds.has(file.id) || file.status === "refreshing";
                        const isRefreshed = file.status === "refreshed" || file.status === "completed";
                        const isFailed = file.status === "failed";
                        const isNotRefreshed = !isRefreshed && !isRefreshing && !isFailed;

                        return (
                          <tr key={file.id}>
                            {/* File Name & Size */}
                            <td>
                              <div className="file-info-cell">
                                <div className={`file-icon-box ${isRefreshed ? "" : "doc-unrefreshed"}`}>
                                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                                    <polyline points="14 2 14 8 20 8" />
                                  </svg>
                                </div>
                                <div className="file-meta-col">
                                  <span className="file-name-text" title={file.original_filename}>
                                    {file.original_filename}
                                  </span>
                                  <span className="file-size-text">
                                    {formatBytes(file.file_size)}
                                    {file.page_count ? ` • ${file.page_count} pages` : ""}
                                  </span>
                                </div>
                              </div>
                            </td>

                            {/* Status Badge */}
                            <td>
                              {isRefreshed && (
                                <span className="status-pill refreshed">
                                  <span className="status-dot" />
                                  Refreshed
                                </span>
                              )}
                              {isNotRefreshed && (
                                <span className="status-pill not_refreshed">
                                  <span className="status-dot" />
                                  Not refreshed
                                </span>
                              )}
                              {isRefreshing && (
                                <span className="status-pill refreshing">
                                  <span className="status-spinner" />
                                  Refreshing...
                                </span>
                              )}
                              {isFailed && (
                                <span className="status-pill failed">
                                  <span className="status-dot" />
                                  Failed
                                </span>
                              )}
                            </td>

                            {/* Action Buttons */}
                            <td className="action-cell">
                              <div className="table-actions" style={{ justifyContent: "flex-end" }}>
                                <button
                                  className="refresh-btn"
                                  onClick={() => handleRefresh(file.id)}
                                  disabled={isRefreshing}
                                  title="Index or re-index file into ChromaDB"
                                >
                                  <svg
                                    width="14"
                                    height="14"
                                    viewBox="0 0 24 24"
                                    fill="none"
                                    stroke="currentColor"
                                    strokeWidth="2"
                                    className={isRefreshing ? "status-spinner" : ""}
                                  >
                                    <polyline points="23 4 23 10 17 10" />
                                    <polyline points="1 20 1 14 7 14" />
                                    <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
                                  </svg>
                                  <span>{isRefreshing ? "Refreshing..." : "Refresh"}</span>
                                </button>

                                <button
                                  className="delete-btn"
                                  onClick={() => handleDeleteFile(file.id)}
                                  title="Delete document and remove vectors"
                                >
                                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                    <polyline points="3 6 5 6 21 6" />
                                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                                    <line x1="10" y1="11" x2="10" y2="17" />
                                    <line x1="14" y1="11" x2="14" y2="17" />
                                  </svg>
                                </button>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
