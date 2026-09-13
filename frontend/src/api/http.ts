import axios, { AxiosHeaders, CanceledError, type AxiosInstance, type InternalAxiosRequestConfig } from 'axios'

import type { AuthSession } from '@/types/api'
import { clearAuthSession, getAccessToken, getSessionEpoch, getSessionSignal, isCurrentSession, notifyUnauthorized, setAccessToken } from './session'

type SessionRequest = InternalAxiosRequestConfig & {
  _retry?: boolean
  _sessionEpoch?: number
  _callerSignal?: InternalAxiosRequestConfig['signal']
  _releaseSignal?: () => void
}

function bindRequest(config: SessionRequest, authenticated: boolean): SessionRequest {
  // Logout must finish before a subsequent login, including its cookie response.
  if (!authenticated && config.url === '/auth/logout') return config
  if (authenticated && !getAccessToken()) throw new CanceledError('No active session', config)
  config._sessionEpoch ??= getSessionEpoch()
  if (!isCurrentSession(config._sessionEpoch)) throw new CanceledError('Session changed', config)
  config._callerSignal ??= config.signal
  const sources = [getSessionSignal(), config._callerSignal].filter((signal) => signal != null)
  const controller = new AbortController()
  const abort = () => controller.abort()
  sources.forEach((signal) => {
    if (signal.aborted) abort()
    else signal.addEventListener?.('abort', abort, { once: true })
  })
  config.signal = controller.signal
  config._releaseSignal = () => {
    sources.forEach((signal) => signal.removeEventListener?.('abort', abort))
    config.signal = config._callerSignal
    config._releaseSignal = undefined
  }
  if (authenticated) {
    config.headers = AxiosHeaders.from(config.headers)
    const token = getAccessToken()
    if (token) config.headers.set('Authorization', `Bearer ${token}`)
    else config.headers.delete('Authorization')
  }
  return config
}
function releaseRequest(config?: SessionRequest): void { config?._releaseSignal?.() }
function rejectStale(config?: SessionRequest): void {
  if (config?._sessionEpoch !== undefined && !isCurrentSession(config._sessionEpoch)) {
    throw new CanceledError('Session changed', config)
  }
}

function resolveBaseURL(): string {
  const configuredBaseURL = import.meta.env.VITE_API_BASE_URL
  if (configuredBaseURL) {
    return configuredBaseURL
  }

  if (!import.meta.env.DEV) {
    return '/api/v1'
  }

  const directApiURL = new URL(window.location.origin)
  directApiURL.port = '8000'
  directApiURL.pathname = '/api/v1'
  directApiURL.search = ''
  directApiURL.hash = ''
  return directApiURL.toString().replace(/\/$/, '')
}

const baseURL = resolveBaseURL()

/** Default API calls (JSON). */
const DEFAULT_TIMEOUT_MS = 10_000

/**
 * Large attachment uploads (N5 配音等): single file up to 50MB on slow links needs minutes, not seconds.
 * Keep separate from DEFAULT_TIMEOUT_MS so list/detail APIs fail fast.
 */
export const ATTACHMENT_UPLOAD_TIMEOUT_MS = 600_000

export const rawHttp = axios.create({
  baseURL,
  timeout: DEFAULT_TIMEOUT_MS,
  withCredentials: true,
})

let refreshing: { epoch: number; promise: Promise<string> } | null = null

async function refreshAccessToken(epoch: number): Promise<string> {
  if (!isCurrentSession(epoch)) throw new CanceledError('Session changed')
  if (refreshing?.epoch === epoch) return refreshing.promise
  const promise = rawHttp.post<AuthSession>('/auth/refresh')
    .then(({ data }) => {
      if (!isCurrentSession(epoch)) throw new CanceledError('Session changed')
      setAccessToken(data.access_token)
      return data.access_token
    })
    .catch((error: unknown) => {
      if (!isCurrentSession(epoch)) throw new CanceledError('Session changed')
      if (axios.isAxiosError(error) && [401, 403].includes(error.response?.status ?? 0)) {
        clearAuthSession()
        notifyUnauthorized()
      }
      throw error
    })
    .finally(() => { if (refreshing?.promise === promise) refreshing = null })
  refreshing = { epoch, promise }
  return promise
}

function attachInterceptors(instance: AxiosInstance, authenticated: boolean): void {
  instance.interceptors.request.use((config) => bindRequest(config, authenticated), (error) => { throw error }, { synchronous: true })
  instance.interceptors.response.use(
    (response) => {
      releaseRequest(response.config)
      rejectStale(response.config)
      return response
    },
    async (error: unknown) => {
      const request = axios.isAxiosError(error) ? error.config as SessionRequest | undefined : undefined
      releaseRequest(request)
      rejectStale(request)
      if (axios.isCancel(error)) throw error
      if (authenticated && axios.isAxiosError(error) && error.response?.status === 401 && request) {
        if (request._retry) {
          clearAuthSession()
          notifyUnauthorized()
        } else {
          request._retry = true
          await refreshAccessToken(request._sessionEpoch ?? getSessionEpoch())
          rejectStale(request)
          if (request.signal?.aborted) throw new CanceledError('Request cancelled', request)
          return instance.request(request)
        }
      }
      throw error
    },
  )
}

export const http = axios.create({
  baseURL,
  timeout: DEFAULT_TIMEOUT_MS,
  withCredentials: true,
})

/** Multipart uploads — long timeout, same auth refresh as http. */
export const uploadHttp = axios.create({
  baseURL,
  timeout: ATTACHMENT_UPLOAD_TIMEOUT_MS,
  withCredentials: true,
})

attachInterceptors(rawHttp, false)
attachInterceptors(http, true)
attachInterceptors(uploadHttp, true)
