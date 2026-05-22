import { describe, expect, it, vi } from 'vitest'

import { finalizeInstanceTopics, submitTaskTopicCapture } from '@/api/workflow-graph'
import { http } from '@/api/http'

vi.mock('@/api/http', () => ({
  http: {
    post: vi.fn(),
    get: vi.fn(),
  },
}))

describe('workflow video WF API client', () => {
  it('submits topic capture for a task', async () => {
    vi.mocked(http.post).mockResolvedValueOnce({
      data: {
        task_id: 't1',
        node_instance_id: 'n1',
        topic_count: 1,
        topics: [{ topic_id: 'topic-1', title: 'A' }],
      },
    })

    const result = await submitTaskTopicCapture('t1', [{ title: 'A' }])
    expect(http.post).toHaveBeenCalledWith('/workflow-graph/tasks/t1/submit-capture', {
      topics: [{ title: 'A' }],
    })
    expect(result.topic_count).toBe(1)
  })

  it('finalizes approved topics on an instance', async () => {
    vi.mocked(http.post).mockResolvedValueOnce({
      data: {
        instance_id: 'run-1',
        approved_count: 2,
        fork_status: 'pending',
        fork_deferred: true,
      },
    })

    const result = await finalizeInstanceTopics('run-1', [
      { topic_id: 'a', title: 'A', script_author_id: 'u1' },
      { topic_id: 'b', title: 'B', script_author_id: 'u2' },
    ])
    expect(result.approved_count).toBe(2)
    expect(result.fork_deferred).toBe(true)
  })
})
