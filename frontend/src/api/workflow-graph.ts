import type { WorkflowGraphInstanceDetail } from '@/types/api'
import { http } from './http'

export async function getWorkflowGraphInstance(
  instanceId: string,
): Promise<WorkflowGraphInstanceDetail> {
  const { data } = await http.get<WorkflowGraphInstanceDetail>(
    `/workflow-graph/instances/${instanceId}`,
  )
  return data
}
