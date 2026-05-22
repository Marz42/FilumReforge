import { describe, expect, it, vi } from 'vitest'

import { rejectInstanceCaptures } from '@/api/workflow-graph'
import { http } from '@/api/http'

vi.mock('@/api/http', () => ({
  http: {
    post: vi.fn(),
    get: vi.fn(),
  },
}))

describe('workflow video W5 API client', () => {
  it('rejects capture rows on an instance', async () => {
    vi.mocked(http.post).mockResolvedValueOnce({
      data: {
        instance_id: 'inst-1',
        reopened_count: 1,
        reopened_instance_keys: ['user-a'],
      },
    })

    const result = await rejectInstanceCaptures('inst-1', {
      rejections: [{ topic_id: 'topic-1', reason: '需修改' }],
    })

    expect(http.post).toHaveBeenCalledWith('/workflow-graph/instances/inst-1/reject-captures', {
      rejections: [{ topic_id: 'topic-1', reason: '需修改' }],
    })
    expect(result.reopened_count).toBe(1)
  })
})
