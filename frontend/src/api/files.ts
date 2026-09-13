import { apiClient, getErrorMessage } from "./client";
import type { FileItem, UploadResponse } from "../types";

/**
 * Fetch all uploaded documents from the backend.
 */
export async function getFiles(): Promise<FileItem[]> {
  try {
    const response = await apiClient.get<FileItem[]>("/files");
    return response.data;
  } catch (error) {
    throw new Error(getErrorMessage(error, "Failed to fetch files from server."));
  }
}

/**
 * Upload a PDF file to the backend without indexing.
 * The backend saves the file and marks it as 'not_refreshed'.
 */
export async function uploadFile(file: File): Promise<FileItem> {
  const formData = new FormData();
  formData.append("file", file);

  try {
    const response = await apiClient.post<UploadResponse>("/files/upload", formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    });
    return response.data.document;
  } catch (error) {
    throw new Error(getErrorMessage(error, "Failed to upload PDF file."));
  }
}

/**
 * Explicitly trigger indexing/refreshing a file into ChromaDB.
 */
export async function refreshFile(fileId: number): Promise<FileItem> {
  try {
    const response = await apiClient.post<UploadResponse>(`/files/${fileId}/refresh`);
    return response.data.document;
  } catch (error) {
    throw new Error(getErrorMessage(error, `Failed to refresh file ${fileId}.`));
  }
}

/**
 * Delete a file and remove its vectors from ChromaDB.
 */
export async function deleteFile(fileId: number): Promise<void> {
  try {
    await apiClient.delete(`/files/${fileId}`);
  } catch (error) {
    throw new Error(getErrorMessage(error, `Failed to delete file ${fileId}.`));
  }
}
