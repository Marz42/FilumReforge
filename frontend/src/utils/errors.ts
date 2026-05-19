import axios, { type AxiosError } from 'axios'

import { extractValidationDetail } from '@/utils/formErrors'
import { PASSWORD_POLICY_FALLBACK } from '@/utils/passwordPolicy'

type ErrorPayload = {
  detail?: string
  message?: string
  request_id?: string
}

function appendRequestId(message: string, error: AxiosError): string {
  const payload = error.response?.data as ErrorPayload | undefined
  if (payload?.request_id) {
    return `${message}（请求编号：${payload.request_id}）`
  }

  const headerRequestId =
    error.response?.headers?.['x-request-id'] ?? error.response?.headers?.['X-Request-ID']
  if (typeof headerRequestId === 'string' && headerRequestId) {
    return `${message}（请求编号：${headerRequestId}）`
  }

  return message
}

function resolveAxiosMessage(error: AxiosError): string {
  const validationMessage = extractValidationDetail(error)
  if (validationMessage) {
    return validationMessage
  }

  const payload = error.response?.data as ErrorPayload | undefined
  const baseMessage = payload?.detail ?? payload?.message ?? error.message

  if (typeof baseMessage === 'string' && baseMessage.trim()) {
    return baseMessage.trim()
  }

  if (error.response?.status === 422) {
    return PASSWORD_POLICY_FALLBACK
  }

  return error.message || '操作失败，请稍后重试。'
}

export function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    return appendRequestId(resolveAxiosMessage(error), error)
  }

  if (error instanceof Error) {
    return error.message
  }

  return '操作失败，请稍后重试。'
}
