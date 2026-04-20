export type BeforeInstallPromptEvent = Event & {
  prompt: () => Promise<void>
  userChoice: Promise<{
    outcome: 'accepted' | 'dismissed'
    platform: string
  }>
}

export function getWebPushPublicKey(): string {
  return import.meta.env.VITE_WEB_PUSH_PUBLIC_KEY?.trim() ?? ''
}

export function isPushSupported(): boolean {
  return (
    typeof window !== 'undefined' &&
    typeof Notification !== 'undefined' &&
    'serviceWorker' in navigator &&
    'PushManager' in window
  )
}

export function getNotificationPermission(): NotificationPermission {
  if (typeof Notification === 'undefined') {
    return 'default'
  }

  return Notification.permission
}

export async function requestNotificationPermission(): Promise<NotificationPermission> {
  if (typeof Notification === 'undefined') {
    return 'default'
  }

  return Notification.requestPermission()
}

export async function registerPwaServiceWorker(): Promise<ServiceWorkerRegistration | null> {
  if (!('serviceWorker' in navigator)) {
    return null
  }

  return navigator.serviceWorker.register('/sw.js')
}

export function urlBase64ToUint8Array(base64String: string): ArrayBuffer {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
  const normalized = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
  const rawData = atob(normalized)
  const outputBuffer = new ArrayBuffer(rawData.length)
  const outputArray = new Uint8Array(outputBuffer)

  for (let index = 0; index < rawData.length; index += 1) {
    outputArray[index] = rawData.charCodeAt(index)
  }

  return outputBuffer
}

export function encodeSubscriptionKey(value: ArrayBuffer | null): string {
  if (!value) {
    return ''
  }

  let binaryString = ''
  const bytes = new Uint8Array(value)
  for (const byte of bytes) {
    binaryString += String.fromCharCode(byte)
  }

  return btoa(binaryString).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '')
}
