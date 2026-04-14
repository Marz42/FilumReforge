import axios, { AxiosHeaders } from 'axios'

import type { AuthSession } from '@/types/api'
import { clearAuthSession, getAccessToken, getRefreshToken, notifyUnauthorized, setAuthSession } from './session'

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

export const rawHttp = axios.create({
  baseURL,
  timeout: 10_000,
})

export const http = axios.create({
  baseURL,
  timeout: 10_000,
})

http.interceptors.request.use((config) => {
  const accessToken = getAccessToken()
  if (accessToken) {
    config.headers = AxiosHeaders.from(config.headers)
    config.headers.set('Authorization', `Bearer ${accessToken}`)
  }
  return config
})

let refreshPromise: Promise<string | null> | null = null

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = getRefreshToken()
  if (!refreshToken) {
    return null
  }

  if (!refreshPromise) {
    refreshPromise = rawHttp
      .post<AuthSession>('/auth/refresh', {
        refresh_token: refreshToken,
      })
      .then(({ data }) => {
        setAuthSession(data.access_token, data.refresh_token)
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

http.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config as (typeof error.config & RetriableRequest) | undefined

    if (error.response?.status === 401 && originalRequest && !originalRequest._retry) {
      originalRequest._retry = true
      const nextAccessToken = await refreshAccessToken()
      if (nextAccessToken) {
        originalRequest.headers = AxiosHeaders.from(originalRequest.headers)
        originalRequest.headers.set('Authorization', `Bearer ${nextAccessToken}`)
        return http.request(originalRequest)
      }
    }

    return Promise.reject(error)
  },
)
