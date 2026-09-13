export type FileStatus =
  | "not_refreshed"
  | "refreshing"
  | "refreshed"
  | "failed"
  | "uploaded"
  | "completed";

export interface FileItem {
  id: number;
  original_filename: string;
  stored_filename: string;
  file_size?: number;
  page_count?: number;
  status: FileStatus;
  created_at: string;
}

export interface SourceItem {
  paper_title?: string;
  page_number?: number | string;
  score?: number;
  rank?: number;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  sources?: SourceItem[];
}

export interface ChatConversation {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messages: ChatMessage[];
}

export interface UploadResponse {
  message: string;
  document: FileItem;
}

export interface ChatApiResponse {
  conversation_id?: number;
  answer: string;
  sources: SourceItem[];
}
