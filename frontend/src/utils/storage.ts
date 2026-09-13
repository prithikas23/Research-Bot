import type { ChatConversation } from "../types";

export const STORAGE_KEY = "research_bot_chat_history";

/**
 * Load all saved chat conversations from localStorage.
 */
export function loadChatHistory(): ChatConversation[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) {
      return parsed;
    }
    return [];
  } catch (err) {
    console.error("Failed to parse chat history from localStorage:", err);
    return [];
  }
}

/**
 * Save chat conversations array to localStorage.
 */
export function saveChatHistory(conversations: ChatConversation[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
  } catch (err) {
    console.error("Failed to save chat history to localStorage:", err);
  }
}

/**
 * Clean and truncate a question into a concise chat title.
 */
export function generateChatTitle(firstQuestion: string): string {
  const clean = firstQuestion
    .replace(/^what\s+is\s+the\s+/i, "")
    .replace(/^what\s+is\s+/i, "")
    .replace(/^how\s+does\s+/i, "")
    .replace(/^tell\s+me\s+about\s+/i, "")
    .replace(/^explain\s+/i, "")
    .replace(/[?!.]+$/, "")
    .trim();

  if (clean.length > 36) {
    return clean.slice(0, 36) + "...";
  }
  return clean || "New Chat";
}
