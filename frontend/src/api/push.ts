import type { PushSubscription } from '@/types/api'
import { http } from './http'

export interface CreatePushSubscriptionPayload {
  endpoint: string
  p256dh_key: string
  auth_key: string
  user_agent?: string | null
}

export async function listPushSubscriptions(): Promise<PushSubscription[]> {
  const { data } = await http.get<PushSubscription[]>('/push-subscriptions')
  return data
}

export async function createPushSubscription(
  payload: CreatePushSubscriptionPayload,
): Promise<PushSubscription> {
  const { data } = await http.post<PushSubscription>('/push-subscriptions', payload)
  return data
}

export async function revokePushSubscription(subscriptionId: string): Promise<PushSubscription> {
  const { data } = await http.delete<PushSubscription>(`/push-subscriptions/${subscriptionId}`)
  return data
}
