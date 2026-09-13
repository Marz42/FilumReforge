import axios, { AxiosError, AxiosHeaders, type InternalAxiosRequestConfig } from 'axios'
import { flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { http, rawHttp, uploadHttp } from '@/api/http'
import { clearAuthSession, getAccessToken, setAccessToken, setUnauthorizedHandler } from '@/api/session'

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => { resolve = done })
  return { promise, resolve }
}
function response(config: InternalAxiosRequestConfig, data: unknown, status = 200) {
  return { config, data, status, statusText: String(status), headers: new AxiosHeaders() }
}
function denied(config: InternalAxiosRequestConfig, status = 401) {
  return new AxiosError('denied', 'ERR_BAD_REQUEST', config, undefined, response(config, {}, status))
}

describe('HTTP session ownership', () => {
  const unauthorized = vi.fn()
  beforeEach(() => {
    clearAuthSession()
    setAccessToken('old-token')
    unauthorized.mockClear()
    setUnauthorizedHandler(unauthorized)
  })

  it.each(['read', 'upload'])('cancels old %s requests immediately and rejects late success', async (kind) => {
    const pending = deferred<unknown>()
    const client = kind === 'upload' ? uploadHttp : http
    let config!: InternalAxiosRequestConfig
    client.defaults.adapter = async (request) => { config = request; return response(request, await pending.promise) }
    const result = client.post('/tasks', {}).catch((error: unknown) => error)
    const signal = config.signal!
    clearAuthSession()
    setAccessToken('new-token')
    expect(signal.aborted).toBe(true)
    pending.resolve({ account: 'old' })
    expect(axios.isCancel(await result)).toBe(true)
    expect(getAccessToken()).toBe('new-token')
    expect(unauthorized).not.toHaveBeenCalled()
  })

  it('does not join an old refresh or let its finally clear the new refresh', async () => {
    const first = deferred<unknown>()
    const second = deferred<unknown>()
    let refreshes = 0
    rawHttp.defaults.adapter = async (config) => {
      refreshes += 1
      return response(config, await (refreshes === 1 ? first.promise : second.promise))
    }
    http.defaults.adapter = async (config) => {
      if (!(config as InternalAxiosRequestConfig & { _retry?: boolean })._retry) throw denied(config)
      return response(config, config.headers.get('Authorization'))
    }
    const old = http.get('/old').catch((error: unknown) => error)
    await flushPromises()
    clearAuthSession()
    setAccessToken('new-token')
    const current = http.get('/current')
    await flushPromises()
    first.resolve({ access_token: 'stale-refresh' })
    expect(axios.isCancel(await old)).toBe(true)
    const another = http.get('/another')
    await flushPromises()
    expect(refreshes).toBe(2)
    second.resolve({ access_token: 'current-refresh' })
    expect((await current).data).toBe('Bearer current-refresh')
    expect((await another).data).toBe('Bearer current-refresh')
    expect(getAccessToken()).toBe('current-refresh')
    expect(unauthorized).not.toHaveBeenCalled()
  })

  it('reports a real current-session refresh rejection', async () => {
    http.defaults.adapter = async (config) => { throw denied(config) }
    rawHttp.defaults.adapter = async (config) => { throw denied(config) }
    await expect(http.get('/protected')).rejects.toMatchObject({ response: { status: 401 } })
    expect(getAccessToken()).toBeNull()
    expect(unauthorized).toHaveBeenCalledOnce()
  })

  it('preserves the session on a refresh server failure', async () => {
    http.defaults.adapter = async (config) => { throw denied(config) }
    rawHttp.defaults.adapter = async (config) => { throw denied(config, 503) }
    await expect(http.get('/protected')).rejects.toMatchObject({ response: { status: 503 } })
    expect(getAccessToken()).toBe('old-token')
    expect(unauthorized).not.toHaveBeenCalled()
  })

  it('does not send protected work after logout', async () => {
    const adapter = vi.fn()
    http.defaults.adapter = adapter
    clearAuthSession()
    expect(axios.isCancel(await http.get('/late').catch((error: unknown) => error))).toBe(true)
    expect(adapter).not.toHaveBeenCalled()
  })

  it('does not retry a caller-cancelled request after a shared refresh', async () => {
    const pending = deferred<unknown>()
    rawHttp.defaults.adapter = async (config) => response(config, await pending.promise)
    const protectedCalls = vi.fn(async (config: InternalAxiosRequestConfig) => { throw denied(config) })
    http.defaults.adapter = protectedCalls
    const caller = new AbortController()
    const result = http.get('/cancelled', { signal: caller.signal }).catch((error: unknown) => error)
    await flushPromises()
    caller.abort()
    pending.resolve({ access_token: 'fresh-token' })
    expect(axios.isCancel(await result)).toBe(true)
    expect(protectedCalls).toHaveBeenCalledOnce()
    expect(getAccessToken()).toBe('fresh-token')
  })
})
