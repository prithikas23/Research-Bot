export interface Source {
  paper_title?: string;
  page_number?: number | string;
  score?: number;
  rank?: number;
}

export interface ChatResponse {
  conversation_id: number | null;
  answer: string;
  sources: Source[];
}

export interface UploadResponse {
  message?: string;
}
