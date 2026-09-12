export interface Source {
  paper_title?: string;
  page_number?: number | string;
  score?: number;
  rank?: number;
}

export interface DocumentItem {
  id: number;
  original_filename: string;
  stored_filename: string;
  file_size?: number;
  page_count?: number;
  status: "uploaded" | "processing" | "completed" | "failed";
  created_at: string;
}

export interface MessageItem {
  id: number;
  conversation_id: number;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  sources?: Source[];
}

export interface ConversationItem {
  id: number;
  title: string;
  created_at: string;
  updated_at: string;
  message_count?: number;
}

export interface ChatResponse {
  conversation_id: number;
  answer: string;
  sources: Source[];
}

export interface UploadResponse {
  message?: string;
  document?: DocumentItem;
}
