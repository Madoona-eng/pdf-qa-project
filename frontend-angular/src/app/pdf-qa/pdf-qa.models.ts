export interface UploadPdfResponse {
  success: boolean;
  docId: string;
  fileName: string;
  pagesCount: number;
  chunksCount: number;
  message: string;
}

export interface RelevantChunk {
  page: number;
  similarityScore: number;
  text: string;
}

export interface AskPdfRequest {
  docId: string;
  question: string;
  topK: number;
}

export interface AskPdfResponse {
  success: boolean;
  answer?: string | null;
  page?: number | null;
  confidence?: number | null;
  sourceContext?: string | null;
  relevantChunks: RelevantChunk[];
  message?: string | null;
}