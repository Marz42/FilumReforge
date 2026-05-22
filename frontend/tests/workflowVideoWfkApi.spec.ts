import { describe, expect, it, vi } from 'vitest'

import { forkProductionRuns } from '@/api/workflow-graph'
import { http } from '@/api/http'

vi.mock('@/api/http', () => ({
  http: {
    post: vi.fn(),
    get: vi.fn(),
  },
}))

describe('workflow video WFK API client', () => {
  it('forks production runs for a batch instance', async () => {
    vi.mocked(http.post).mockResolvedValueOnce({
      data: {
        batch_instance_id: 'batch-1',
        forked_count: 5,
        skipped_count: 0,
        child_instance_ids: ['c1', 'c2', 'c3', 'c4', 'c5'],
        fork_status: 'completed',
      },
    })

    const result = await forkProductionRuns('batch-1')
    expect(http.post).toHaveBeenCalledWith('/workflow-graph/instances/batch-1/fork-production')
    expect(result.forked_count).toBe(5)
    expect(result.fork_status).toBe('completed')
  })
})
