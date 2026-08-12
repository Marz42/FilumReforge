import { describe, expect, it } from 'vitest'

import { canUseTaskDetailAction } from '@/domain/task-detail/actions'
import type { Task } from '@/types/api'

function taskFixture(overrides: Partial<Task> = {}): Task {
  return {
    id: 'task-1',
    title: '动作契约测试',
    description: null,
    creator_id: 'creator-1',
    assignee_id: 'assignee-1',
    department_id: 'department-1',
    status: 'todo',
    priority: 'medium',
    due_date: null,
    started_at: null,
    completed_at: null,
    parent_task_id: null,
    source_type: 'manual',
    extra_metadata: {},
    created_at: '2026-08-12T00:00:00Z',
    updated_at: '2026-08-12T00:00:00Z',
    ...overrides,
  }
}

describe('task detail action contract', () => {
  it('treats standalone available_actions as authoritative', () => {
    const task = taskFixture({
      execution_mode: 'standalone',
      available_actions: [],
    })

    expect(canUseTaskDetailAction(task, 'start_work', true)).toBe(false)
    expect(canUseTaskDetailAction(task, 'submit_deliverable', true)).toBe(false)
    expect(canUseTaskDetailAction(task, 'approve_deliverable', true)).toBe(false)
  })

  it('allows only the standalone actions returned by the backend', () => {
    const task = taskFixture({
      execution_mode: 'standalone',
      available_actions: [
        { action: 'start_work', label: '开始处理', button_type: 'primary' },
      ],
    })

    expect(canUseTaskDetailAction(task, 'start_work', false)).toBe(true)
    expect(canUseTaskDetailAction(task, 'submit_deliverable', true)).toBe(false)
  })

  it('keeps the existing workflow fallback until its action contract is migrated', () => {
    const task = taskFixture({
      execution_mode: 'workflow',
      available_actions: [],
    })

    expect(canUseTaskDetailAction(task, 'start_work', true)).toBe(true)
    expect(canUseTaskDetailAction(task, 'start_work', false)).toBe(false)
  })
})
