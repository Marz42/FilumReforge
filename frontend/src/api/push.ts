import type { PushSubscription } from '@/types/api'
import { http } from './http'

export interface CreatePushSubscriptionPayload {
  endpoint: string
  p256dh_key: string
  auth_key: string
  user_agent?: string | null
}

export interface PushTestNotificationResult {
  message_id: string
  status: string
  detail: string
}

export interface PushSubscriptionConfigResult {
  public_key: string | null
  is_enabled: boolean
}

export async function listPushSubscriptions(): Promise<PushSubscription[]> {
  const { data } = await http.get<PushSubscription[]>('/push-subscriptions')
  return data
}

export async function getPushSubscriptionConfig(): Promise<PushSubscriptionConfigResult> {
  const { data } = await http.get<PushSubscriptionConfigResult>('/push-subscriptions/config')
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

export async function sendPushTestNotification(): Promise<PushTestNotificationResult> {
  const { data } = await http.post<PushTestNotificationResult>('/push-subscriptions/test')
  return data
}
