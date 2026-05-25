import { describe, expect, it, vi } from 'vitest'

import {
  createGraphTemplateRun,
  finalizeInstanceTopics,
  listGraphTemplates,
  listInstanceChildren,
  submitTaskTopicCapture,
} from '@/api/workflow-graph'
import { http } from '@/api/http'

vi.mock('@/api/http', () => ({
  http: {
    post: vi.fn(),
    get: vi.fn(),
  },
}))

describe('workflow video W10 API regression surface', () => {
  it('exports graph template run lifecycle client methods', () => {
    expect(typeof listGraphTemplates).toBe('function')
    expect(typeof createGraphTemplateRun).toBe('function')
    expect(typeof submitTaskTopicCapture).toBe('function')
    expect(typeof finalizeInstanceTopics).toBe('function')
    expect(typeof listInstanceChildren).toBe('function')
  })
})
