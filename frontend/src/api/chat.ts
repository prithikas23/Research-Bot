import { apiClient, getErrorMessage } from "./client";
import type { ChatApiResponse } from "../types";

/**
 * Ask a research question using RAG retrieval over refreshed documents.
 */
export async function askQuestion(
  question: string,
  conversationId?: number
): Promise<ChatApiResponse> {
  try {
    const payload: { question: string; conversation_id?: number } = {
      question: question.trim(),
    };
    if (conversationId) {
      payload.conversation_id = conversationId;
    }

    const response = await apiClient.post<ChatApiResponse>("/chat", payload);
    return response.data;
  } catch (error) {
    throw new Error(getErrorMessage(error, "Failed to get answer from research bot."));
  }
}
