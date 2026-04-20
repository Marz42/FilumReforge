import type { AIRouterResult } from '@/types/api'
import { http } from './http'

export async function routeAICommand(text: string): Promise<AIRouterResult> {
  const { data } = await http.post<AIRouterResult>('/ai/router', {
    text,
  })
  return data
}
