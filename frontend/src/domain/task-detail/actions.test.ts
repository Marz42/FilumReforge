import { describe, expect, it } from 'vitest'

import type { Task } from '@/types/api'
import {
  canDelegateStandaloneTask,
  isStandaloneTask,
  taskAvailableActions,
  taskHasAction,
} from '@/domain/task-detail/actions'

function makeTask(overrides: Partial<Task>): Task {
  return {
    id: 't1',
    title: '任务',
    description: null,
    creator_id: 'c1',
    assignee_id: 'a1',
    department_id: null,
    status: 'todo',
    priority: 'medium',
    due_date: null,
    started_at: null,
    completed_at: null,
    parent_task_id: null,
    source_type: 'manual',
    extra_metadata: {},
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

describe('task-detail actions contract', () => {
  it('reads available actions from the backend contract', () => {
    const task = makeTask({
      available_actions: [
        { action: 'start_work', label: '开始处理', button_type: 'primary' },
        { action: 'delegate_assignment', label: '转办', button_type: 'warning' },
      ],
    })
    expect(taskAvailableActions(task)).toEqual(['start_work', 'delegate_assignment'])
    expect(taskHasAction(task, 'delegate_assignment')).toBe(true)
    expect(taskHasAction(task, 'submit_deliverable')).toBe(false)
  })

  it('treats a task without graph execution mode as standalone only when declared', () => {
    expect(isStandaloneTask(makeTask({ execution_mode: 'standalone' }))).toBe(true)
    expect(isStandaloneTask(makeTask({ execution_mode: 'workflow' }))).toBe(false)
    expect(isStandaloneTask(makeTask({}))).toBe(false)
    expect(isStandaloneTask(null)).toBe(false)
  })

  it('allows delegation for a standalone task that exposes delegate_assignment', () => {
    const delegable = makeTask({
      execution_mode: 'standalone',
      available_actions: [{ action: 'delegate_assignment', label: '转办', button_type: 'warning' }],
    })
    expect(canDelegateStandaloneTask(delegable)).toBe(true)
  })

  it('does not infer delegation from graph metadata', () => {
    // A workflow task, even one carrying graph metadata, is not delegated via
    // the standalone path; and a standalone REVIEW task without the action is not delegable.
    const workflow = makeTask({
      execution_mode: 'workflow',
      available_actions: [{ action: 'delegate_assignment', label: '转办', button_type: 'warning' }],
      extra_metadata: { workflow_graph_instance_id: 'g1', workflow_node_instance_id: 'n1' },
    })
    expect(canDelegateStandaloneTask(workflow)).toBe(false)

    const standaloneReview = makeTask({ execution_mode: 'standalone', status: 'review', available_actions: [] })
    expect(canDelegateStandaloneTask(standaloneReview)).toBe(false)
  })
})
