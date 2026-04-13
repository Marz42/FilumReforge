export function formatDateTime(value: string | null): string {
  if (!value) {
    return '—'
  }

  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

export function formatDate(value: string | null): string {
  if (!value) {
    return '—'
  }

  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'medium',
  }).format(new Date(value))
}
