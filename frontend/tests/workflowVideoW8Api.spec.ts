import { describe, expect, it, vi } from 'vitest'

import { listInstanceEvents } from '@/api/workflow-graph'
import { http } from '@/api/http'

vi.mock('@/api/http', () => ({
  http: {
    post: vi.fn(),
    get: vi.fn(),
  },
}))

describe('workflow video W8 API client', () => {
  it('lists paginated run events for an instance', async () => {
    vi.mocked(http.get).mockResolvedValueOnce({
      data: {
        instance_id: 'inst-1',
        items: [
          {
            id: 'evt-1',
            instance_id: 'inst-1',
            event_type: 'capture_submitted',
            actor_user_id: 'user-1',
            payload: { topic_count: 2 },
            created_at: '2026-05-23T10:00:00Z',
          },
        ],
        total: 1,
        limit: 20,
        offset: 0,
      },
    })

    const page = await listInstanceEvents('inst-1', { limit: 20, offset: 0 })
    expect(http.get).toHaveBeenCalledWith('/workflow-graph/instances/inst-1/events', {
      params: { limit: 20, offset: 0 },
    })
    expect(page.items[0]?.event_type).toBe('capture_submitted')
  })
})
