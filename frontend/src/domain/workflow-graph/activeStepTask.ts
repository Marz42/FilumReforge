/** Resolve the actionable projection task for a graph instance (prefer current node). */

export interface ActiveStepTaskNode {
  node_key: string
  engine_state: string
  assignee_user_id?: string | null
  task_id?: string | null
}

export interface ActiveStepTaskInstance {
  current_node_key?: string | null
  node_instances?: ActiveStepTaskNode[]
}

const ACTIVE_ENGINE_STATES = new Set(['activated', 'acknowledged'])

export function resolveActiveStepTaskId(
  instance: ActiveStepTaskInstance | null | undefined,
  options: { preferAssigneeUserId?: string | null } = {},
): string | null {
  if (!instance?.node_instances?.length) {
    return null
  }

  const activeNodes = instance.node_instances.filter((node) =>
    ACTIVE_ENGINE_STATES.has(node.engine_state),
  )
  if (activeNodes.length === 0) {
    return null
  }

  const currentKey = instance.current_node_key
  if (currentKey) {
    const current = activeNodes.find(
      (node) => node.node_key === currentKey && typeof node.task_id === 'string' && node.task_id,
    )
    if (current?.task_id) {
      return current.task_id
    }
  }

  const preferAssignee = options.preferAssigneeUserId
  if (preferAssignee) {
    const assigneeMatch = activeNodes.find(
      (node) =>
        node.assignee_user_id === preferAssignee
        && typeof node.task_id === 'string'
        && node.task_id,
    )
    if (assigneeMatch?.task_id) {
      return assigneeMatch.task_id
    }
  }

  const fallback = activeNodes.find((node) => typeof node.task_id === 'string' && node.task_id)
  return fallback?.task_id ?? null
}
