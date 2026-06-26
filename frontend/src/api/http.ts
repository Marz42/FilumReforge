import axios, { AxiosHeaders, type AxiosInstance } from 'axios'

import type { AuthSession } from '@/types/api'
import { clearAuthSession, getAccessToken, notifyUnauthorized, setAccessToken } from './session'

type RetriableRequest = {
  _retry?: boolean
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

let refreshPromise: Promise<string | null> | null = null

async function refreshAccessToken(): Promise<string | null> {
  if (!refreshPromise) {
    refreshPromise = rawHttp
      .post<AuthSession>('/auth/refresh')
      .then(({ data }) => {
        setAccessToken(data.access_token)
        return data.access_token
      })
      .catch(() => {
        clearAuthSession()
        notifyUnauthorized()
        return null
      })
      .finally(() => {
        refreshPromise = null
      })
  }

  return refreshPromise
}

function attachAuthInterceptors(instance: AxiosInstance): void {
  instance.interceptors.request.use((config) => {
    const accessToken = getAccessToken()
    if (accessToken) {
      config.headers = AxiosHeaders.from(config.headers)
      config.headers.set('Authorization', `Bearer ${accessToken}`)
    }
    return config
  })

  instance.interceptors.response.use(
    (response) => response,
    async (error) => {
      const originalRequest = error.config as (typeof error.config & RetriableRequest) | undefined

      if (error.response?.status === 401 && originalRequest && !originalRequest._retry) {
        originalRequest._retry = true
        const nextAccessToken = await refreshAccessToken()
        if (nextAccessToken) {
          originalRequest.headers = AxiosHeaders.from(originalRequest.headers)
          originalRequest.headers.set('Authorization', `Bearer ${nextAccessToken}`)
          return instance.request(originalRequest)
        }
      }

      return Promise.reject(error)
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

attachAuthInterceptors(http)
attachAuthInterceptors(uploadHttp)
