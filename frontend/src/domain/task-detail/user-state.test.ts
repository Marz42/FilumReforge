import { describe, expect, it } from 'vitest'

import {
  resolveTaskUserFacingState,
  TASK_USER_FACING_STATE_LABELS,
} from './user-state'
import type { Task } from '@/types/api'

function makeTask(overrides: Partial<Task> = {}): Task {
  return {
    id: 'task-1',
    title: '提交选题',
    description: null,
    creator_id: 'creator-1',
    assignee_id: 'user-1',
    department_id: 'dept-1',
    status: 'doing',
    priority: 'medium',
    source_type: 'template',
    due_date: null,
    started_at: null,
    completed_at: null,
    parent_task_id: null,
    created_at: '2026-06-18T00:00:00Z',
    updated_at: '2026-06-18T00:00:00Z',
    extra_metadata: {},
    ...overrides,
  }
}

describe('resolveTaskUserFacingState', () => {
  it('maps batch root to in_progress', () => {
    const state = resolveTaskUserFacingState(makeTask(), 'video_batch_root')
    expect(state).toBe('in_progress')
    expect(TASK_USER_FACING_STATE_LABELS[state]).toBe('进行中')
  })

  it('maps done tasks to completed', () => {
    const state = resolveTaskUserFacingState(makeTask({ status: 'done' }), 'video_n1_capture')
    expect(state).toBe('completed')
  })

  it('maps rework metadata to returned', () => {
    const state = resolveTaskUserFacingState(
      makeTask({
        extra_metadata: { latest_rework_reason: '请补充说明' },
      }),
      'video_n1_capture',
    )
    expect(state).toBe('returned')
  })

  it('maps capture reject metadata to returned', () => {
    const state = resolveTaskUserFacingState(
      makeTask({
        extra_metadata: { latest_capture_state: 'rejected' },
      }),
      'video_n1_capture',
    )
    expect(state).toBe('returned')
  })
})
