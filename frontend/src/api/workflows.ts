import type {
  WorkflowDefinition,
  WorkflowDefinitionStatus,
  WorkflowInstance,
  WorkflowStepRun,
} from '@/types/api'
import { http } from './http'

export interface WorkflowStepPayload {
  step_key: string
  name: string
  step_type: string
  approval_mode?: string | null
  assignee_rule?: Record<string, unknown>
  reject_target_step_key?: string | null
  sort_order?: number | null
  config?: Record<string, unknown>
}

export interface CreateWorkflowDefinitionPayload {
  code: string
  name: string
  scope_type: string
  status?: WorkflowDefinitionStatus
  version?: number
  config?: Record<string, unknown>
  steps: WorkflowStepPayload[]
}

export type UpdateWorkflowDefinitionPayload = Partial<CreateWorkflowDefinitionPayload>

export interface StartWorkflowPayload {
  definition_id: string
  source_type: string
  source_id?: string | null
  payload?: Record<string, unknown>
}

export async function listWorkflowDefinitions(): Promise<WorkflowDefinition[]> {
  const { data } = await http.get<WorkflowDefinition[]>('/workflows/definitions')
  return data
}

export async function createWorkflowDefinition(
  payload: CreateWorkflowDefinitionPayload,
): Promise<WorkflowDefinition> {
  const { data } = await http.post<WorkflowDefinition>('/workflows/definitions', payload)
  return data
}

export async function updateWorkflowDefinition(
  definitionId: string,
  payload: UpdateWorkflowDefinitionPayload,
): Promise<WorkflowDefinition> {
  const { data } = await http.patch<WorkflowDefinition>(
    `/workflows/definitions/${definitionId}`,
    payload,
  )
  return data
}

export async function listWorkflowInstances(): Promise<WorkflowInstance[]> {
  const { data } = await http.get<WorkflowInstance[]>('/workflows/instances')
  return data
}

export async function startWorkflow(payload: StartWorkflowPayload): Promise<WorkflowInstance> {
  const { data } = await http.post<WorkflowInstance>('/workflows/instances/start', payload)
  return data
}

export async function listPendingWorkflowStepRuns(): Promise<WorkflowStepRun[]> {
  const { data } = await http.get<WorkflowStepRun[]>('/workflows/step-runs/pending')
  return data
}

export async function actWorkflowStepRun(
  stepRunId: string,
  action: 'approve' | 'reject' | 'return',
  comment?: string | null,
): Promise<WorkflowInstance> {
  const { data } = await http.post<WorkflowInstance>(
    `/workflows/step-runs/${stepRunId}/actions`,
    {
      action,
      comment: comment ?? null,
    },
  )
  return data
}
