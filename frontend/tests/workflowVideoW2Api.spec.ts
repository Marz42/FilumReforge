import { describe, expect, it, vi } from 'vitest'

import { previewWorkflowParticipants } from '@/api/workflow-graph'
import { http } from '@/api/http'

vi.mock('@/api/http', () => ({
  http: {
    post: vi.fn(),
    get: vi.fn(),
  },
}))

describe('workflow video W2 preview participants API client', () => {
  it('posts preview-participants with policy query param', async () => {
    vi.mocked(http.post).mockResolvedValue({
      data: {
        policy_ref: 'copywriters',
        mode: 'subset',
        user_ids: ['u1'],
        users: [{ id: 'u1', email: 'a@example.com', display_name: '甲' }],
        snapshot: { mode: 'subset', user_ids: ['u1'] },
      },
    })

    const result = await previewWorkflowParticipants('tpl-1', 'copywriters', {
      mode: 'subset',
      user_ids: ['u1'],
    })

    expect(http.post).toHaveBeenCalledWith(
      '/workflow-graph/templates/tpl-1/preview-participants',
      { mode: 'subset', user_ids: ['u1'] },
      { params: { policy: 'copywriters' } },
    )
    expect(result.policy_ref).toBe('copywriters')
    expect(result.users).toHaveLength(1)
  })
})
