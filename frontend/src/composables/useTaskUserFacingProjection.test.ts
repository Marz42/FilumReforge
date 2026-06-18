import { describe, expect, it } from 'vitest'

import {
  groupRowsByUserState,
  projectTaskForWorkspace,
} from '@/composables/useTaskUserFacingProjection'
import type { Task } from '@/types/api'

function buildTask(overrides: Partial<Task> = {}): Task {
  return {
    id: 'task-1',
    title: '选题会 / Run-A',
    description: null,
    creator_id: 'user-1',
    assignee_id: 'user-2',
    department_id: 'dept-1',
    status: 'doing',
    priority: 'medium',
    due_date: '2026-06-20T00:00:00Z',
    started_at: '2026-06-18T08:00:00Z',
    completed_at: null,
    parent_task_id: null,
    source_type: 'template',
    extra_metadata: {
      template_node_key: 'N1_PROPOSE',
      run_kind: 'batch',
    },
    created_at: '2026-06-18T08:00:00Z',
    updated_at: '2026-06-18T08:00:00Z',
    ...overrides,
  }
}

describe('useTaskUserFacingProjection', () => {
  it('projects user-facing state and run label', () => {
    const row = projectTaskForWorkspace(
      buildTask({
        status: 'todo',
        extra_metadata: {
          workflow_graph_instance_id: 'inst-1',
          template_node_key: 'N1_PROPOSE',
          run_kind: 'batch',
        },
      }),
      'user-2',
    )
    expect(row.userState).toBe('pending')
    expect(row.userStateLabel).toBe('待处理')
    expect(row.runLabel).toContain('Run-A')
  })

  it('groups board rows by user state', () => {
    const baseMetadata = {
      workflow_graph_instance_id: 'inst-1',
      template_node_key: 'N1_PROPOSE',
      run_kind: 'batch',
    }
    const rows = [
      projectTaskForWorkspace(
        buildTask({ id: 'a', status: 'todo', extra_metadata: baseMetadata }),
        'user-2',
      ),
      projectTaskForWorkspace(
        buildTask({
          id: 'b',
          status: 'doing',
          extra_metadata: {
            ...baseMetadata,
            latest_rework_reason: 'fix',
            latest_capture_state: 'rejected',
          },
        }),
        'user-2',
      ),
    ]
    const grouped = groupRowsByUserState(rows)
    expect(grouped.pending).toHaveLength(1)
    expect(grouped.returned).toHaveLength(1)
  })
})
