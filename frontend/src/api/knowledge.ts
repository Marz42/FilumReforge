import type { DocumentCategory, KnowledgeQueryResult } from '@/types/api'
import { http } from './http'

export interface KnowledgeQueryPayload {
  query: string
  category?: DocumentCategory
  limit?: number
}

export async function queryKnowledge(payload: KnowledgeQueryPayload): Promise<KnowledgeQueryResult> {
  const { data } = await http.post<KnowledgeQueryResult>('/knowledge/query', payload)
  return data
}
