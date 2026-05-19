import axios from 'axios'

type ValidationErrorItem = {
  loc?: (string | number)[]
  msg?: string
  type?: string
}

type ErrorPayload = {
  detail?: string | ValidationErrorItem[]
  message?: string
}

function normalizeValidationMessage(message: string): string {
  return message.replace(/^Value error,\s*/i, '').trim()
}

export function extractValidationDetail(error: unknown): string | null {
  if (!axios.isAxiosError(error) || error.response?.status !== 422) {
    return null
  }

  const payload = error.response.data as ErrorPayload | undefined
  const detail = payload?.detail

  if (typeof detail === 'string' && detail.trim()) {
    return detail.trim()
  }

  if (!Array.isArray(detail)) {
    return null
  }

  const messages = detail
    .map((item: string | ValidationErrorItem) => {
      if (typeof item === 'string') {
        return item.trim()
      }
      if (typeof item.msg === 'string' && item.msg.trim()) {
        return normalizeValidationMessage(item.msg)
      }
      return ''
    })
    .filter(Boolean)

  return messages.length > 0 ? messages.join('；') : null
}
