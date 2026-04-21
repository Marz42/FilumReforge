import axios from 'axios'

type ErrorPayload = {
  detail?: string
  message?: string
  request_id?: string
}

export function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const payload = error.response?.data as ErrorPayload | undefined
    const baseMessage = payload?.detail ?? payload?.message ?? error.message
    if (payload?.request_id) {
      return `${baseMessage}（请求编号：${payload.request_id}）`
    }
    const headerRequestId =
      error.response?.headers?.['x-request-id'] ??
      error.response?.headers?.['X-Request-ID']
    if (typeof headerRequestId === 'string' && headerRequestId) {
      return `${baseMessage}（请求编号：${headerRequestId}）`
    }
    return baseMessage
  }

  if (error instanceof Error) {
    return error.message
  }

  return '操作失败，请稍后重试。'
}
