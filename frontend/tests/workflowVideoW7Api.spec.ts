import { describe, expect, it, vi } from 'vitest'

import { listGraphTemplates, listInstanceChildren } from '@/api/workflow-graph'
import { http } from '@/api/http'

vi.mock('@/api/http', () => ({
  http: {
    post: vi.fn(),
    get: vi.fn(),
  },
}))

describe('workflow video W7 API client', () => {
  it('lists active graph templates', async () => {
    vi.mocked(http.get).mockResolvedValueOnce({
      data: [
        {
          id: 'tpl-batch',
          code: 'topic_meeting_batch_v1',
          name: '选题会',
          status: 'active',
          version: 1,
          run_kind: 'batch',
          config: { launch_schema: { fields: [] } },
        },
      ],
    })

    const templates = await listGraphTemplates()
    expect(http.get).toHaveBeenCalledWith('/workflow-graph/templates', { params: {} })
    expect(templates[0]?.run_kind).toBe('batch')
    expect(templates[0]?.config).toEqual({ launch_schema: { fields: [] } })
  })

  it('lists child production runs for a batch instance', async () => {
    vi.mocked(http.get).mockResolvedValueOnce({
      data: [
        {
          id: 'child-1',
          template_id: 'tpl-prod',
          status: 'active',
          current_node_key: 'N3_SCRIPT_WRITE',
          context: { topic_title: '选题 A', root_task_id: 'task-1' },
          node_instances: [
            { engine_state: 'completed' },
            { engine_state: 'activated' },
          ],
        },
      ],
    })

    const children = await listInstanceChildren('batch-1')
    expect(http.get).toHaveBeenCalledWith('/workflow-graph/instances/batch-1/children', {
      params: { limit: 50 },
    })
    expect(children[0]?.progress_percent).toBe(50)
  })
})
