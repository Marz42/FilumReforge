import type { WorkflowGraphInstanceDetail } from '@/types/api'
import type { PreviewParticipantsResponse } from '@/types/workflowVideo'
import { http } from './http'

export interface PreviewParticipantsPayload {
  mode?: 'all' | 'subset'
  user_ids?: string[]
  department_id?: string | null
}

export async function getWorkflowGraphInstance(
  instanceId: string,
): Promise<WorkflowGraphInstanceDetail> {
  const { data } = await http.get<WorkflowGraphInstanceDetail>(
    `/workflow-graph/instances/${instanceId}`,
  )
  return data
}

export async function previewWorkflowParticipants(
  templateId: string,
  policy: string,
  payload: PreviewParticipantsPayload = {},
): Promise<PreviewParticipantsResponse> {
  const { data } = await http.post<PreviewParticipantsResponse>(
    `/workflow-graph/templates/${templateId}/preview-participants`,
    payload,
    { params: { policy } },
  )
  return data
}
