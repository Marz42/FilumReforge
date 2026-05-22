import { describe, expect, it } from 'vitest'

import type { VideoRunContext } from '@/types/workflowVideo'

describe('workflow video v1 W1 context types', () => {
  it('accepts batch run context with approved topics', () => {
    const ctx: VideoRunContext = {
      run_kind: 'batch',
      run_label: '第12周选题会',
      approved_topics: [
        {
          topic_id: '00000000-0000-4000-8000-000000000001',
          title: '年味',
          script_author_id: '00000000-0000-4000-8000-000000000002',
        },
      ],
      fork_status: 'pending',
    }
    expect(ctx.run_kind).toBe('batch')
    expect(ctx.approved_topics).toHaveLength(1)
  })
})
