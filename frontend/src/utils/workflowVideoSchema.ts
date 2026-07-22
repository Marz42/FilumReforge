import type { CaptureSchema, LaunchSchema } from '@/types/workflowVideo'

export function resolveSchemaSnapshotNodes(
  context: Record<string, unknown> | undefined,
): Record<string, Record<string, unknown>> {
  const snapshot = context?.schema_snapshot
  if (!snapshot || typeof snapshot !== 'object') {
    return {}
  }
  const nodes = (snapshot as Record<string, unknown>).nodes
  if (!nodes || typeof nodes !== 'object') {
    return {}
  }
  return nodes as Record<string, Record<string, unknown>>
}

export function resolveCaptureSchema(
  context: Record<string, unknown> | undefined,
  nodeKey: string,
): CaptureSchema | null {
  const nodeEntry = resolveSchemaSnapshotNodes(context)[nodeKey]
  const raw = nodeEntry?.capture_schema
  if (!raw || typeof raw !== 'object') {
    return null
  }
  return raw as CaptureSchema
}

const DEFAULT_USER_POOL_BY_COLUMN: Record<string, string> = {
  edit_assignee_id: 'post_production',
}

const DEFAULT_USER_POOL_BY_NODE: Record<string, string> = {
  N7_EDIT_ASSIGN: 'post_production',
}

/** Resolve department pool for capture user pickers; fills gaps in stale schema snapshots. */
export function resolveUserPoolKey(
  context: Record<string, unknown> | undefined,
  nodeKey: string,
): string {
  const schema = resolveCaptureSchema(context, nodeKey)
  const userColumn = schema?.columns.find((entry) => entry.type === 'user')
  const fromColumn = userColumn?.pool_key?.trim()
  if (fromColumn) {
    return fromColumn
  }
  if (userColumn?.key) {
    const fromKey = DEFAULT_USER_POOL_BY_COLUMN[userColumn.key]?.trim()
    if (fromKey) {
      return fromKey
    }
  }
  return DEFAULT_USER_POOL_BY_NODE[nodeKey]?.trim() ?? ''
}

export function resolveAggregateSchema(
  context: Record<string, unknown> | undefined,
  nodeKey: string,
): Record<string, unknown> | null {
  const nodeEntry = resolveSchemaSnapshotNodes(context)[nodeKey]
  const raw = nodeEntry?.aggregate_schema
  if (!raw || typeof raw !== 'object') {
    return null
  }
  return raw as Record<string, unknown>
}

export function resolveAggregateMode(
  context: Record<string, unknown> | undefined,
): 'batch' | 'streaming' {
  const snapshot = context?.schema_snapshot
  const fromSnapshot =
    snapshot && typeof snapshot === 'object'
      ? (snapshot as Record<string, unknown>).aggregate_mode
      : undefined
  const raw = context?.aggregate_mode ?? fromSnapshot
  return raw === 'streaming' ? 'streaming' : 'batch'
}

export function isCaptureClosed(context: Record<string, unknown> | undefined): boolean {
  return context?.capture_closed === true
}

export function resolveLaunchSchema(
  templateConfig: Record<string, unknown> | undefined,
): LaunchSchema | null {
  const raw = templateConfig?.launch_schema
  if (!raw || typeof raw !== 'object') {
    return null
  }
  const fields = (raw as LaunchSchema).fields
  if (!Array.isArray(fields)) {
    return null
  }
  return raw as LaunchSchema
}

export function resolveParticipantPolicyRefs(
  templateConfig: Record<string, unknown> | undefined,
): string[] {
  const policies = templateConfig?.participant_policies
  if (!policies || typeof policies !== 'object') {
    return []
  }
  return Object.keys(policies as Record<string, unknown>)
}

export function templateSupportsDirectInstantiation(
  template:
    | {
        run_kind?: string | null
        status?: string
        config?: Record<string, unknown>
        capabilities?: { can_instantiate_directly?: boolean }
      }
    | null
    | undefined,
): boolean {
  if (!template) {
    return false
  }
  if (template.capabilities && typeof template.capabilities.can_instantiate_directly === 'boolean') {
    return template.capabilities.can_instantiate_directly
  }
  if (template.run_kind === 'production') {
    return false
  }
  return template.status === 'active' || template.status === undefined
}
