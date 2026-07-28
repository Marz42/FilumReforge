export const KNOWN_NODE_UI_PROFILES = [
  { value: 'graph_manual', label: '通用图任务' },
  { value: 'video_n1_capture', label: '视频 · 选题采集' },
  { value: 'video_n2_aggregate', label: '视频 · 选题汇总' },
  { value: 'video_batch_root', label: '视频 · 批次根任务' },
  { value: 'video_production_step', label: '视频 · 制作步骤' },
  { value: 'video_production_multi', label: '视频 · 多人制作' },
  { value: 'video_production_platform', label: '视频 · 发布平台' },
  { value: 'video_capture_assign', label: '视频 · 分配采集' },
  { value: 'video_capture_schedule', label: '视频 · 排期采集' },
  { value: 'legacy_task', label: '遗留任务' },
  { value: 'returned', label: '退回态' },
] as const

export type LaunchFieldRow = {
  key: string
  label: string
  type: string
  required: boolean
  policy_ref: string
}

export type ContextFieldRow = {
  key: string
  type: string
  required: boolean
  description: string
}

export type ContextSchemaStyle = 'json_schema' | 'flat'

export type RoutingRuleRow = {
  kind: 'if' | 'else'
  field: string
  operator: string
  valueText: string
  target_node_key: string
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

export function parseLaunchSchema(raw: unknown): {
  rows: LaunchFieldRow[]
  structuredCompatible: boolean
} {
  if (raw === undefined || (isRecord(raw) && Object.keys(raw).length === 0)) {
    return { rows: [], structuredCompatible: true }
  }
  if (!isRecord(raw) || !Array.isArray(raw.fields)) {
    return { rows: [], structuredCompatible: false }
  }
  const rows: LaunchFieldRow[] = []
  for (const field of raw.fields) {
    if (!isRecord(field) || typeof field.key !== 'string' || typeof field.label !== 'string') {
      return { rows: [], structuredCompatible: false }
    }
    if (
      Object.keys(field).some(
        (key) => !['key', 'label', 'type', 'required', 'policy_ref'].includes(key),
      )
    ) {
      return { rows: [], structuredCompatible: false }
    }
    rows.push({
      key: field.key,
      label: field.label,
      type: typeof field.type === 'string' ? field.type : 'text',
      required: field.required === true,
      policy_ref: typeof field.policy_ref === 'string' ? field.policy_ref : '',
    })
  }
  return { rows, structuredCompatible: true }
}

export function buildLaunchSchema(
  rawBase: Record<string, unknown>,
  rows: LaunchFieldRow[],
): Record<string, unknown> {
  const normalizedFields = rows
    .map((field) => ({
      key: field.key.trim(),
      label: field.label.trim(),
      type: field.type || 'text',
      required: field.required,
      ...(field.policy_ref.trim() ? { policy_ref: field.policy_ref.trim() } : {}),
    }))
    .filter((field) => field.key && field.label)
  const next = { ...rawBase }
  if (normalizedFields.length > 0) {
    next.fields = normalizedFields
  } else {
    delete next.fields
  }
  return next
}

export function parseContextSchema(raw: unknown): {
  rows: ContextFieldRow[]
  style: ContextSchemaStyle
  structuredCompatible: boolean
} {
  if (raw === undefined || (isRecord(raw) && Object.keys(raw).length === 0)) {
    return { rows: [], style: 'json_schema', structuredCompatible: true }
  }
  if (!isRecord(raw)) {
    return { rows: [], style: 'json_schema', structuredCompatible: false }
  }

  if (isRecord(raw.properties)) {
    const required = new Set(
      Array.isArray(raw.required)
        ? raw.required.filter((item): item is string => typeof item === 'string')
        : [],
    )
    const rows: ContextFieldRow[] = []
    for (const [key, definition] of Object.entries(raw.properties)) {
      if (!isRecord(definition)) {
        return { rows: [], style: 'json_schema', structuredCompatible: false }
      }
      if (Object.keys(definition).some((key) => !['type', 'description'].includes(key))) {
        return { rows: [], style: 'json_schema', structuredCompatible: false }
      }
      rows.push({
        key,
        type: typeof definition.type === 'string' ? definition.type : 'string',
        required: required.has(key),
        description: typeof definition.description === 'string' ? definition.description : '',
      })
    }
    return { rows, style: 'json_schema', structuredCompatible: true }
  }

  const rows: ContextFieldRow[] = []
  for (const [key, definition] of Object.entries(raw)) {
    if (!isRecord(definition) || typeof definition.type !== 'string') {
      return { rows: [], style: 'json_schema', structuredCompatible: false }
    }
    rows.push({
      key,
      type: definition.type,
      required: definition.required === true,
      description: typeof definition.description === 'string' ? definition.description : '',
    })
  }
  return { rows, style: 'flat', structuredCompatible: true }
}

export function buildContextSchema(
  rows: ContextFieldRow[],
  style: ContextSchemaStyle,
  rawBase: Record<string, unknown> = {},
): Record<string, unknown> {
  const normalized = rows
    .map((field) => ({ ...field, key: field.key.trim(), description: field.description.trim() }))
    .filter((field) => field.key)
  if (normalized.length === 0) {
    if (style === 'flat') {
      return {}
    }
    const emptyBase = { ...rawBase }
    delete emptyBase.properties
    delete emptyBase.required
    return Object.keys(emptyBase).some((key) => key !== 'type') ? emptyBase : {}
  }
  if (style === 'flat') {
    return Object.fromEntries(
      normalized.map((field) => [
        field.key,
        {
          type: field.type || 'string',
          ...(field.required ? { required: true } : {}),
          ...(field.description ? { description: field.description } : {}),
        },
      ]),
    )
  }
  const base = { ...rawBase }
  delete base.properties
  delete base.required
  return {
    ...base,
    type: typeof rawBase.type === 'string' ? rawBase.type : 'object',
    properties: Object.fromEntries(
      normalized.map((field) => [
        field.key,
        {
          type: field.type || 'string',
          ...(field.description ? { description: field.description } : {}),
        },
      ]),
    ),
    ...(normalized.some((field) => field.required)
      ? { required: normalized.filter((field) => field.required).map((field) => field.key) }
      : {}),
  }
}

function formatRuleValue(value: unknown): string {
  if (typeof value === 'string') {
    return value
  }
  return value === undefined ? '' : JSON.stringify(value)
}

export function parseRoutingRules(raw: unknown): {
  rows: RoutingRuleRow[]
  structuredCompatible: boolean
} {
  if (raw === undefined || (Array.isArray(raw) && raw.length === 0)) {
    return { rows: [], structuredCompatible: true }
  }
  if (!Array.isArray(raw)) {
    return { rows: [], structuredCompatible: false }
  }
  const rows: RoutingRuleRow[] = []
  for (const rule of raw) {
    if (!isRecord(rule)) {
      return { rows: [], structuredCompatible: false }
    }
    const target = rule.target_node_key ?? rule.target_step_key
    if (typeof target !== 'string') {
      return { rows: [], structuredCompatible: false }
    }
    const isElse = rule.else === true || rule.type === 'else'
    if (
      Object.keys(rule).some(
        (key) => !['condition', 'target_node_key', 'target_step_key', 'else', 'type'].includes(key),
      )
    ) {
      return { rows: [], structuredCompatible: false }
    }
    if (isElse) {
      rows.push({ kind: 'else', field: '', operator: 'eq', valueText: '', target_node_key: target })
      continue
    }
    const condition = rule.condition
    if (!isRecord(condition) || typeof condition.field !== 'string') {
      return { rows: [], structuredCompatible: false }
    }
    if (Object.keys(condition).some((key) => !['field', 'operator', 'value'].includes(key))) {
      return { rows: [], structuredCompatible: false }
    }
    rows.push({
      kind: 'if',
      field: condition.field,
      operator: typeof condition.operator === 'string' ? condition.operator : 'eq',
      valueText: formatRuleValue(condition.value),
      target_node_key: target,
    })
  }
  return { rows, structuredCompatible: true }
}

function parseRuleValue(valueText: string): unknown {
  const trimmed = valueText.trim()
  if (!trimmed) {
    return ''
  }
  try {
    return JSON.parse(trimmed) as unknown
  } catch {
    return trimmed
  }
}

export function buildRoutingRules(rows: RoutingRuleRow[]): Array<Record<string, unknown>> {
  return rows
    .filter((row) => row.target_node_key.trim())
    .map((row) => {
      if (row.kind === 'else') {
        return { else: true, target_node_key: row.target_node_key.trim() }
      }
      const condition: Record<string, unknown> = {
        field: row.field.trim(),
        operator: row.operator || 'eq',
      }
      if (row.operator !== 'exists') {
        condition.value = parseRuleValue(row.valueText)
      }
      return {
        condition,
        target_node_key: row.target_node_key.trim(),
      }
    })
}
