import type {
  Document,
  DocumentCategory,
  DocumentSearchResponse,
  DocumentStatus,
  DocumentSummary,
} from '@/types/api'
import { http } from './http'

export interface ListDocumentsPayload {
  category?: DocumentCategory
  status?: DocumentStatus
  query?: string
}

export interface CreateDocumentPayload {
  title: string
  slug?: string | null
  category: DocumentCategory
  content_md: string
  status?: DocumentStatus
}

export interface UpdateDocumentPayload {
  title?: string
  slug?: string | null
  category?: DocumentCategory
  content_md?: string
}

export interface SearchDocumentsPayload {
  query: string
  category?: DocumentCategory
  limit?: number
}

export async function listDocuments(payload: ListDocumentsPayload = {}): Promise<DocumentSummary[]> {
  const { data } = await http.get<DocumentSummary[]>('/documents', {
    params: payload,
  })
  return data
}

export async function searchDocuments(payload: SearchDocumentsPayload): Promise<DocumentSearchResponse> {
  const { data } = await http.get<DocumentSearchResponse>('/documents/search', {
    params: payload,
  })
  return data
}

export async function getDocument(documentId: string): Promise<Document> {
  const { data } = await http.get<Document>(`/documents/${documentId}`)
  return data
}

export async function createDocument(payload: CreateDocumentPayload): Promise<Document> {
  const { data } = await http.post<Document>('/documents', payload)
  return data
}

export async function updateDocument(
  documentId: string,
  payload: UpdateDocumentPayload,
): Promise<Document> {
  const { data } = await http.patch<Document>(`/documents/${documentId}`, payload)
  return data
}

export async function publishDocument(documentId: string): Promise<Document> {
  const { data } = await http.post<Document>(`/documents/${documentId}/publish`)
  return data
}

export async function archiveDocument(documentId: string): Promise<Document> {
  const { data } = await http.post<Document>(`/documents/${documentId}/archive`)
  return data
}
