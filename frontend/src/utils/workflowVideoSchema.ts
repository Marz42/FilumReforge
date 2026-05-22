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
