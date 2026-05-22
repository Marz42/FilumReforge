import { describe, expect, it, vi } from 'vitest'

import { createGraphTemplateRun } from '@/api/workflow-graph'
import { http } from '@/api/http'

vi.mock('@/api/http', () => ({
  http: {
    post: vi.fn(),
    get: vi.fn(),
  },
}))

describe('workflow video W3 API client', () => {
  it('creates a graph template run', async () => {
    vi.mocked(http.post).mockResolvedValueOnce({
      data: {
        instance_id: 'inst-1',
        root_task_id: 'root-1',
        run_kind: 'batch',
        activated_task_count: 3,
        node_instance_count: 4,
        current_node_key: 'N1_PROPOSE',
      },
    })

    const result = await createGraphTemplateRun('tpl-1', {
      inputs: { theme: '五月', manager_user_id: 'mgr-1' },
      participants_snapshot: {
        copywriters: { mode: 'subset', user_ids: ['u1', 'u2', 'u3'] },
      },
    })

    expect(http.post).toHaveBeenCalledWith('/workflow-graph/templates/tpl-1/runs', {
      inputs: { theme: '五月', manager_user_id: 'mgr-1' },
      participants_snapshot: {
        copywriters: { mode: 'subset', user_ids: ['u1', 'u2', 'u3'] },
      },
    })
    expect(result.activated_task_count).toBe(3)
    expect(result.current_node_key).toBe('N1_PROPOSE')
  })
})
