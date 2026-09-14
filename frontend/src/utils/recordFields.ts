export type RecordFieldDefinition = {
  field_key: string
  label: string
  field_type: string
  storage_target?: string
  is_active?: boolean
}

export function cloneRecord(value: Record<string, unknown> | null | undefined): Record<string, unknown> {
  return { ...(value ?? {}) }
}

export function formatRecordValue(value: unknown): string {
  if (value === null || value === undefined) {
    return ''
  }
  if (typeof value === 'string') {
    return value
  }
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

export function parseRecordValue(text: string, fieldType?: string): unknown {
  const trimmed = text.trim()
  if (fieldType === 'number') {
    if (trimmed === '') {
      return null
    }
    const numeric = Number(trimmed)
    return Number.isFinite(numeric) ? numeric : text
  }
  if (fieldType === 'date' || fieldType === 'uuid' || fieldType === 'string' || fieldType === 'text') {
    return trimmed
  }
  if (trimmed === '') {
    return ''
  }
  if (trimmed === 'true') {
    return true
  }
  if (trimmed === 'false') {
    return false
  }
  if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
    try {
      return JSON.parse(trimmed) as unknown
    } catch {
      return text
    }
  }
  return text
}

export function parseRecordObject(text: string): Record<string, unknown> {
  const parsed = JSON.parse(text) as unknown
  if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') {
    throw new Error('not-object')
  }
  return parsed as Record<string, unknown>
}

export function listedDefinitionKeys(definitions: RecordFieldDefinition[], storageTarget?: string): string[] {
  return definitions
    .filter((item) => item.is_active !== false)
    .filter((item) => !storageTarget || item.storage_target === storageTarget)
    .map((item) => item.field_key)
}

export function extraRecordKeys(
  record: Record<string, unknown>,
  definitions: RecordFieldDefinition[],
  storageTarget?: string,
): string[] {
  const known = new Set(listedDefinitionKeys(definitions, storageTarget))
  return Object.keys(record).filter((key) => !known.has(key))
}
