import type { WorkflowGraphInstanceDetail, WorkflowNodeInstanceSummary } from '@/types/api'
import type {
  CreateGraphTemplateRunRequest,
  CreateGraphTemplateRunResponse,
  ForkProductionRunsResponse,
  GraphTemplateSummary,
  RejectCapturesRequest,
  RejectCapturesResponse,
  RejectProductionStepRequest,
  RejectProductionStepResponse,
  FinalizeTopicsResponse,
  DispatchTopicResponse,
  InstanceSubmissionsResponse,
  ParticipantUserPreview,
  PreviewParticipantsResponse,
  TopicCaptureSubmitResponse,
  WorkflowGraphInstanceSummary,
  WorkflowRunEventListResponse,
} from '@/types/workflowVideo'
import { http } from './http'

export interface PreviewParticipantsPayload {
  mode?: 'all' | 'subset'
  user_ids?: string[]
  department_id?: string | null
}

type GraphInstanceListItem = {
  id: string
  template_id: string | null
  status: string
  current_node_key?: string | null
  run_label?: string | null
  parent_instance_id?: string | null
  context: Record<string, unknown>
  node_instances: WorkflowNodeInstanceSummary[]
}

function mapGraphInstanceSummary(item: GraphInstanceListItem): WorkflowGraphInstanceSummary {
  const total = item.node_instances.length
  const completed = item.node_instances.filter((node) => node.engine_state === 'completed').length
  return {
    id: item.id,
    template_id: item.template_id,
    status: item.status,
    current_node_key: item.current_node_key,
    run_label: item.run_label,
    parent_instance_id: item.parent_instance_id,
    context: item.context,
    progress_percent: total ? Math.round((completed / total) * 100) : 0,
    total_node_count: total,
    completed_node_count: completed,
  }
}

export async function listGraphTemplates(): Promise<GraphTemplateSummary[]> {
  const { data } = await http.get<
    Array<Omit<GraphTemplateSummary, 'config'> & { config?: Record<string, unknown> }>
  >('/workflow-graph/templates')
  return data.map((item) => ({
    ...item,
    config: item.config ?? {},
  }))
}

export async function listInstanceChildren(
  instanceId: string,
  limit = 50,
): Promise<WorkflowGraphInstanceSummary[]> {
  const { data } = await http.get<GraphInstanceListItem[]>(
    `/workflow-graph/instances/${instanceId}/children`,
    { params: { limit } },
  )
  return data.map(mapGraphInstanceSummary)
}

export async function listGraphInstancesForTemplate(
  templateId: string,
  limit = 10,
): Promise<WorkflowGraphInstanceSummary[]> {
  const { data } = await http.get<GraphInstanceListItem[]>(
    `/workflow-graph/templates/${templateId}/instances`,
    { params: { limit } },
  )
  return data.map(mapGraphInstanceSummary)
}

export async function listInstanceEvents(
  instanceId: string,
  params: { limit?: number; offset?: number } = {},
): Promise<WorkflowRunEventListResponse> {
  const { data } = await http.get<WorkflowRunEventListResponse>(
    `/workflow-graph/instances/${instanceId}/events`,
    { params },
  )
  return data
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

export async function dispatchInstanceTopic(
  instanceId: string,
  payload: {
    topic_id: string
    title: string
    script_writer_user_id: string
    source_node_instance_id?: string | null
  },
): Promise<DispatchTopicResponse> {
  const { data } = await http.post<DispatchTopicResponse>(
    `/workflow-graph/instances/${instanceId}/dispatch-topic`,
    payload,
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

export async function rejectProductionStep(
  taskId: string,
  payload: RejectProductionStepRequest,
): Promise<RejectProductionStepResponse> {
  const { data } = await http.post<RejectProductionStepResponse>(
    `/workflow-graph/tasks/${taskId}/reject-production`,
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

export async function listManagedDepartmentMemberOptions(): Promise<ParticipantUserPreview[]> {
  const { data } = await http.get<ParticipantUserPreview[]>(
    '/workflow-graph/managed-department-member-options',
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
