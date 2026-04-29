import type {
  MessageCenterSnapshot,
  MessageStateFilter,
  NotificationChannel,
  NotificationReceipt,
  NotificationDeliveryStatus,
  NotificationReceiptType,
} from '@/types/api'
import { http } from './http'

type GetMessageCenterSnapshotParams = {
  sourceType?: string
  state?: MessageStateFilter
  channel?: NotificationChannel
  deliveryStatus?: NotificationDeliveryStatus
  createdFrom?: string
  createdTo?: string
}

export async function getMessageCenterSnapshot(
  params: GetMessageCenterSnapshotParams = {},
): Promise<MessageCenterSnapshot> {
  const { data } = await http.get<MessageCenterSnapshot>('/messages', {
    params: {
      source_type: params.sourceType,
      state: params.state,
      channel: params.channel,
      delivery_status: params.deliveryStatus,
      created_from: params.createdFrom,
      created_to: params.createdTo,
    },
  })
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
