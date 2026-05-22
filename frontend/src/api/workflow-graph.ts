import type { WorkflowGraphInstanceDetail } from '@/types/api'
import type {
  CreateGraphTemplateRunRequest,
  CreateGraphTemplateRunResponse,
  ForkProductionRunsResponse,
  RejectCapturesRequest,
  RejectCapturesResponse,
  FinalizeTopicsResponse,
  InstanceSubmissionsResponse,
  PreviewParticipantsResponse,
  TopicCaptureSubmitResponse,
} from '@/types/workflowVideo'
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

export async function submitTaskTopicCapture(
  taskId: string,
  topics: Array<{ topic_id?: string; title: string; content?: string | null; reason?: string | null }>,
): Promise<TopicCaptureSubmitResponse> {
  const { data } = await http.post<TopicCaptureSubmitResponse>(
    `/workflow-graph/tasks/${taskId}/submit-capture`,
    { topics },
  )
  return data
}

export async function listInstanceSubmissions(
  instanceId: string,
  nodeKey: string,
): Promise<InstanceSubmissionsResponse> {
  const { data } = await http.get<InstanceSubmissionsResponse>(
    `/workflow-graph/instances/${instanceId}/submissions`,
    { params: { node_key: nodeKey } },
  )
  return data
}

export async function finalizeInstanceTopics(
  instanceId: string,
  approvedTopics: Array<{
    topic_id: string
    title: string
    script_author_id: string
    content?: string | null
    reason?: string | null
  }>,
  rejectedTopics: Array<Record<string, unknown>> = [],
): Promise<FinalizeTopicsResponse> {
  const { data } = await http.post<FinalizeTopicsResponse>(
    `/workflow-graph/instances/${instanceId}/finalize-topics`,
    { approved_topics: approvedTopics, rejected_topics: rejectedTopics },
  )
  return data
}

export async function forkProductionRuns(
  instanceId: string,
): Promise<ForkProductionRunsResponse> {
  const { data } = await http.post<ForkProductionRunsResponse>(
    `/workflow-graph/instances/${instanceId}/fork-production`,
  )
  return data
}

export async function rejectInstanceCaptures(
  instanceId: string,
  payload: RejectCapturesRequest,
): Promise<RejectCapturesResponse> {
  const { data } = await http.post<RejectCapturesResponse>(
    `/workflow-graph/instances/${instanceId}/reject-captures`,
    payload,
  )
  return data
}

export async function createGraphTemplateRun(
  templateId: string,
  payload: CreateGraphTemplateRunRequest,
): Promise<CreateGraphTemplateRunResponse> {
  const { data } = await http.post<CreateGraphTemplateRunResponse>(
    `/workflow-graph/templates/${templateId}/runs`,
    payload,
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
