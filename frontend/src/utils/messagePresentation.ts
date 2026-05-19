import type { Message, NotificationDeliveryStatus } from '@/types/api'

export function resolveMessageStateLabel(message: Message): string {
  if (message.receipt_state.is_acknowledged) {
    return '已确认'
  }
  if (message.receipt_state.is_read) {
    return '已读'
  }
  return '未读'
}

export function resolveMessageStateTagType(message: Message): 'success' | 'warning' | 'info' {
  if (message.receipt_state.is_acknowledged) {
    return 'success'
  }
  if (message.receipt_state.is_read) {
    return 'warning'
  }
  return 'info'
}

export function resolveDeliveryStateLabel(deliveryState: NotificationDeliveryStatus | null): string {
  if (deliveryState === 'sent') {
    return '投递成功'
  }
  if (deliveryState === 'failed') {
    return '投递失败'
  }
  if (deliveryState === 'retrying') {
    return '重试中'
  }
  if (deliveryState === 'pending') {
    return '等待投递'
  }
  return '暂无投递记录'
}

export function isMessageUnread(message: Message): boolean {
  return !message.receipt_state.is_read
}
