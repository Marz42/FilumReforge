import axios from 'axios'

type ErrorPayload = {
  detail?: string
  message?: string
}

export function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const payload = error.response?.data as ErrorPayload | undefined
    return payload?.detail ?? payload?.message ?? error.message
  }

  if (error instanceof Error) {
    return error.message
  }

  return '操作失败，请稍后重试。'
}
