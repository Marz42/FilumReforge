self.addEventListener('install', (event) => {
  event.waitUntil(self.skipWaiting())
})

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim())
})

self.addEventListener('push', (event) => {
  let payload = {}
  try { payload = event.data ? event.data.json() : {} } catch { payload = {} }
  if (!payload || typeof payload !== 'object') payload = {}
  const title = payload.title || 'Project Filum'
  const options = {
    body: payload.body || '你有一条新的系统消息。',
    data: payload,
    tag: payload.message_id ? `filum-message-${payload.message_id}` : undefined,
  }

  event.waitUntil(self.registration.showNotification(title, options))
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const id = event.notification.data?.message_id
  const targetUrl = typeof id === 'string' ? `/messages?selected=${encodeURIComponent(id)}` : '/messages'

  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(async (clients) => {
      for (const client of clients) {
        if ('focus' in client) {
          const navigated = await client.navigate(targetUrl)
          return (navigated || client).focus()
        }
      }

      if (self.clients.openWindow) {
        return self.clients.openWindow(targetUrl)
      }

      return undefined
    }),
  )
})
