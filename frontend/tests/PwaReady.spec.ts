import { afterEach, describe, expect, it, vi } from 'vitest'
import { registerPwaServiceWorker } from '@/utils/pwa'

afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers() })

describe('service worker activation', () => {
  it('waits for activation before exposing a new push manager', async () => {
    let activate!: (registration: ServiceWorkerRegistration) => void
    const active = { active: {} } as ServiceWorkerRegistration
    vi.stubGlobal('navigator', { serviceWorker: {
      register: vi.fn().mockResolvedValue({ active: null }),
      ready: new Promise((resolve) => { activate = resolve }),
    } })
    const pending = registerPwaServiceWorker()
    activate(active)
    expect(await pending).toBe(active)
  })

  it('times out if activation cannot finish', async () => {
    vi.useFakeTimers()
    vi.stubGlobal('navigator', { serviceWorker: { register: vi.fn().mockResolvedValue({ active: null }), ready: new Promise(() => {}) } })
    const failure = registerPwaServiceWorker().catch((error: Error) => error)
    await vi.advanceTimersByTimeAsync(10_000)
    expect(await failure).toEqual(expect.objectContaining({ message: expect.stringContaining('尚未就绪') }))
    expect(vi.getTimerCount()).toBe(0)
  })
})
