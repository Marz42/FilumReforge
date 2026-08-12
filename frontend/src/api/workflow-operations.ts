import type {
  WorkflowOperationAction,
  WorkflowOperationsDashboard,
  WorkflowTraceFilters,
  WorkflowTraceList,
} from '@/types/workflowOperations'

import { http } from './http'

function commandHeaders(): Record<string, string> {
  const commandId = typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID()
    : `web-${Date.now()}-${Math.random().toString(16).slice(2)}`
  return { 'X-Command-ID': commandId }
}

export async function getWorkflowOperationsDashboard(
  stalledMinutes = 30,
): Promise<WorkflowOperationsDashboard> {
  const { data } = await http.get<WorkflowOperationsDashboard>('/workflow-graph/admin/operations', {
    params: { stalled_minutes: stalledMinutes },
  })
  return data
}

export async function searchWorkflowTraces(
  filters: WorkflowTraceFilters,
): Promise<WorkflowTraceList> {
  const { data } = await http.get<WorkflowTraceList>('/workflow-graph/admin/operations/traces', {
    params: filters,
  })
  return data
}

export async function replayWorkflowOutbox(
  outboxEventId: string,
  reason: string,
): Promise<WorkflowOperationAction> {
  const { data } = await http.post<WorkflowOperationAction>(
    `/workflow-graph/admin/operations/outbox/${outboxEventId}/replay`,
    { reason },
    { headers: commandHeaders() },
  )
  return data
}

export async function updateWorkflowIncident(
  incidentId: string,
  status: 'resolved' | 'ignored',
  reason: string,
): Promise<WorkflowOperationAction> {
  const { data } = await http.patch<WorkflowOperationAction>(
    `/workflow-graph/admin/operations/incidents/${incidentId}`,
    { status, reason },
    { headers: commandHeaders() },
  )
  return data
}

export async function operateWorkflowNode(
  nodeInstanceId: string,
  action: 'retry' | 'suspend' | 'resume',
  reason: string,
): Promise<WorkflowOperationAction> {
  const { data } = await http.post<WorkflowOperationAction>(
    `/workflow-graph/admin/operations/node-instances/${nodeInstanceId}/${action}`,
    { reason },
    { headers: commandHeaders() },
  )
  return data
}
