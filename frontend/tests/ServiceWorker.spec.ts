// @vitest-environment node
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { describe, expect, it, vi } from 'vitest'

function worker() {
  const handlers: Record<string, (event: Record<string, unknown>) => void> = {}
  const self = { addEventListener: (name: string, handler: typeof handlers[string]) => { handlers[name] = handler },
    registration: { showNotification: vi.fn().mockResolvedValue(undefined) },
    clients: { matchAll: vi.fn().mockResolvedValue([]), openWindow: vi.fn().mockResolvedValue(undefined) } }
  runInNewContext(readFileSync(new URL('../public/sw.js', import.meta.url), 'utf8'), { self })
  return { self, handlers }
}

describe('WebPush service worker', () => {
  it('shows a fallback for malformed payloads and deduplicates by message id', async () => {
    const { self, handlers } = worker()
    const waitUntil = vi.fn()
    handlers.push!({ data: { json: () => { throw new Error('bad json') } }, waitUntil })
    expect(self.registration.showNotification).toHaveBeenCalledWith('Project Filum', expect.objectContaining({ body: expect.any(String) }))
    handlers.push!({ data: { json: () => ({ message_id: 'm1', title: 'hello' }) }, waitUntil })
    expect(self.registration.showNotification).toHaveBeenLastCalledWith('hello', expect.objectContaining({ tag: 'filum-message-m1' }))
  })

  it('opens a same-origin message detail and ignores an untrusted payload URL', async () => {
    const { self, handlers } = worker()
    let pending: Promise<unknown> = Promise.resolve()
    handlers.notificationclick!({ notification: { close: vi.fn(), data: { message_id: 'm/1', url: 'https://untrusted.test' } },
      waitUntil: (promise: Promise<unknown>) => { pending = promise } })
    await pending
    expect(self.clients.openWindow).toHaveBeenCalledWith('/messages?selected=m%2F1')
  })
})
