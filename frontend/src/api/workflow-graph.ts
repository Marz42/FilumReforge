import type { WorkflowGraphInstanceDetail, WorkflowNodeInstanceSummary } from '@/types/api'
import type {
  CreateGraphTemplateRunRequest,
  CreateGraphTemplateRunResponse,
  ForkProductionRunsResponse,
  GraphTemplateDesignerDetail,
  GraphTemplateDryRunResult,
  GraphTemplateExportBundle,
  GraphTemplateSummary,
  GraphTemplateValidateResult,
  RejectCapturesRequest,
  RejectCapturesResponse,
  RejectProductionStepRequest,
  RejectProductionStepResponse,
  FinalizeTopicsResponse,
  CloseCaptureResponse,
  DispatchTopicResponse,
  InstanceSubmissionsResponse,
  ParticipantUserPreview,
  PreviewParticipantsResponse,
  TopicCaptureSubmitResponse,
  WorkflowGraphInstanceSummary,
  WorkflowRunEventListResponse,
  DepartmentRunSummary,
} from '@/types/workflowVideo'
import { http } from './http'
import { resolveActiveStepTaskId } from '@/domain/workflow-graph/activeStepTask'

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
  const nodeInstances = item.node_instances.map((node) => ({
    ...node,
    task_id: node.task_id ?? null,
  }))
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
    active_task_id: resolveActiveStepTaskId({
      current_node_key: item.current_node_key,
      node_instances: nodeInstances,
    }),
  }
}

export async function listGraphTemplates(options?: { manage?: boolean }): Promise<GraphTemplateSummary[]> {
  const { data } = await http.get<
    Array<Omit<GraphTemplateSummary, 'config'> & { config?: Record<string, unknown> }>
  >('/workflow-graph/templates', {
    params: options?.manage ? { scope: 'manage' } : undefined,
  })
  return data.map((item) => ({
    ...item,
    config: item.config ?? {},
  }))
}

export interface GraphTemplateDetail extends GraphTemplateSummary {
  nodes: Array<{
    id: string
    node_key: string
    title: string
    sort_order: number
  }>
}

export async function getGraphTemplateDetail(templateId: string): Promise<GraphTemplateDetail> {
  const { data } = await http.get<GraphTemplateDetail>(`/workflow-graph/templates/${templateId}`)
  return {
    ...data,
    config: data.config ?? {},
  }
}

export async function updateGraphTemplate(
  templateId: string,
  payload: { name?: string; description?: string | null; config?: Record<string, unknown> },
): Promise<GraphTemplateDetail> {
  const { data } = await http.patch<GraphTemplateDetail>(`/workflow-graph/templates/${templateId}`, payload)
  return {
    ...data,
    config: data.config ?? {},
  }
}

export async function getGraphTemplateDesigner(templateId: string): Promise<GraphTemplateDesignerDetail> {
  const { data } = await http.get<GraphTemplateDesignerDetail>(
    `/workflow-graph/templates/${templateId}/designer`,
  )
  return {
    ...data,
    config: data.config ?? {},
    nodes: data.nodes ?? [],
    edges: data.edges ?? [],
  }
}

export async function cloneGraphTemplate(
  cloneFromId: string,
  name?: string,
): Promise<GraphTemplateDesignerDetail> {
  const { data } = await http.post<GraphTemplateDesignerDetail>('/workflow-graph/templates', {
    clone_from_id: cloneFromId,
    name,
  })
  return {
    ...data,
    config: data.config ?? {},
    nodes: data.nodes ?? [],
    edges: data.edges ?? [],
  }
}

export async function createBlankGraphTemplate(
  name = '未命名模板',
): Promise<GraphTemplateDesignerDetail> {
  const { data } = await http.post<GraphTemplateDesignerDetail>('/workflow-graph/templates', { name })
  return {
    ...data,
    config: data.config ?? {},
    nodes: data.nodes ?? [],
    edges: data.edges ?? [],
  }
}

export async function saveGraphTemplateDraft(
  templateId: string,
  payload: {
    name: string
    description?: string | null
    config: Record<string, unknown>
    nodes: Array<{
      node_key: string
      title: string
      sort_order: number
      assignment_mode?: string
      join_mode?: string
      assignee_rule?: Record<string, unknown>
      config?: Record<string, unknown>
    }>
    edges?: Array<{
      from_node_key: string
      to_node_key: string
      is_reject_path?: boolean
      condition?: Record<string, unknown>
      priority?: number
    }>
  },
): Promise<GraphTemplateDesignerDetail> {
  const { data } = await http.put<GraphTemplateDesignerDetail>(
    `/workflow-graph/templates/${templateId}/draft`,
    payload,
  )
  return {
    ...data,
    config: data.config ?? {},
    nodes: data.nodes ?? [],
    edges: data.edges ?? [],
  }
}

export async function forkGraphTemplateVersion(templateId: string): Promise<GraphTemplateDesignerDetail> {
  const { data } = await http.post<GraphTemplateDesignerDetail>(
    `/workflow-graph/templates/${templateId}/versions`,
  )
  return {
    ...data,
    config: data.config ?? {},
    nodes: data.nodes ?? [],
    edges: data.edges ?? [],
  }
}

export async function publishGraphTemplate(templateId: string): Promise<GraphTemplateDesignerDetail> {
  const { data } = await http.patch<GraphTemplateDesignerDetail>(
    `/workflow-graph/templates/${templateId}/status`,
    { status: 'active' },
  )
  return {
    ...data,
    config: data.config ?? {},
    nodes: data.nodes ?? [],
    edges: data.edges ?? [],
  }
}

export async function validateGraphTemplate(templateId: string): Promise<GraphTemplateValidateResult> {
  const { data } = await http.get<GraphTemplateValidateResult>(
    `/workflow-graph/templates/${templateId}/validate`,
  )
  return data
}

export async function exportGraphTemplate(templateId: string): Promise<GraphTemplateExportBundle> {
  const { data } = await http.get<GraphTemplateExportBundle>(`/workflow-graph/templates/${templateId}/export`)
  return data
}

export async function importGraphTemplateDraft(
  templateId: string,
  bundle: GraphTemplateExportBundle,
): Promise<GraphTemplateDesignerDetail> {
  const { data } = await http.post<GraphTemplateDesignerDetail>(
    `/workflow-graph/templates/${templateId}/import`,
    { bundle },
  )
  return {
    ...data,
    config: data.config ?? {},
    nodes: data.nodes ?? [],
    edges: data.edges ?? [],
  }
}

export async function dryRunGraphTemplate(
  templateId: string,
  payload: {
    department_id?: string | null
    inputs?: Record<string, unknown>
    draft?: Parameters<typeof saveGraphTemplateDraft>[1]
  } = {},
): Promise<GraphTemplateDryRunResult> {
  const { data } = await http.post<GraphTemplateDryRunResult>(
    `/workflow-graph/templates/${templateId}/dry-run`,
    payload,
  )
  return data
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

export async function listDepartmentRuns(
  departmentId: string,
  options?: { limit?: number; include_completed?: boolean },
): Promise<DepartmentRunSummary[]> {
  const { data } = await http.get<DepartmentRunSummary[]>('/workflow-graph/runs', {
    params: {
      department_id: departmentId,
      limit: options?.limit,
      include_completed: options?.include_completed,
    },
  })
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
  topics: Array<Record<string, string | null | undefined>>,
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

export async function closeInstanceCapture(instanceId: string): Promise<CloseCaptureResponse> {
  const { data } = await http.post<CloseCaptureResponse>(
    `/workflow-graph/instances/${instanceId}/close-capture`,
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

export async function listDepartmentPoolMemberOptions(
  templateId: string,
  poolKey: string,
): Promise<ParticipantUserPreview[]> {
  const { data } = await http.get<ParticipantUserPreview[]>(
    `/workflow-graph/templates/${templateId}/department-pool-member-options`,
    { params: { pool_key: poolKey } },
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
