import type { Message, NotificationReceipt, NotificationReceiptType } from '@/types/api'
import { http } from './http'

export async function listMessages(): Promise<Message[]> {
  const { data } = await http.get<Message[]>('/messages')
  return data
}

export async function listMessageReceipts(messageId: string): Promise<NotificationReceipt[]> {
  const { data } = await http.get<NotificationReceipt[]>(`/messages/${messageId}/receipts`)
  return data
}

export async function createMessageReceipt(
  messageId: string,
  receiptType: NotificationReceiptType,
  note?: string | null,
): Promise<NotificationReceipt> {
  const { data } = await http.post<NotificationReceipt>(`/messages/${messageId}/receipts`, {
    receipt_type: receiptType,
    note: note ?? null,
  })
  return data
}
