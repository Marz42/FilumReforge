import { onScopeDispose } from 'vue'

const eventName = 'filum:message-receipt-updated'

export function notifyMessageReceiptUpdated(): void {
  window.dispatchEvent(new Event(eventName))
}

/** Refresh mounted inboxes after a successful receipt, including the header badge. */
export function useMessageUpdates(refresh: () => Promise<void>): void {
  const listener = () => { void refresh() }
  window.addEventListener(eventName, listener)
  onScopeDispose(() => window.removeEventListener(eventName, listener))
}
