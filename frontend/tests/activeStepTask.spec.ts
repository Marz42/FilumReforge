import { describe, expect, it } from 'vitest'

import { resolveActiveStepTaskId } from '@/domain/workflow-graph/activeStepTask'

describe('resolveActiveStepTaskId', () => {
  it('prefers current node task', () => {
    const taskId = resolveActiveStepTaskId({
      current_node_key: 'N3_SCRIPT_WRITE',
      node_instances: [
        {
          node_key: 'N3_SCRIPT_WRITE',
          engine_state: 'activated',
          assignee_user_id: 'user-a',
          task_id: 'task-n3',
        },
        {
          node_key: 'N5_VO_UPLOAD',
          engine_state: 'pending',
          task_id: 'task-n5',
        },
      ],
    })
    expect(taskId).toBe('task-n3')
  })

  it('prefers assignee match when current node has no task', () => {
    const taskId = resolveActiveStepTaskId(
      {
        current_node_key: 'N5_VO_UPLOAD',
        node_instances: [
          {
            node_key: 'N3_SCRIPT_WRITE',
            engine_state: 'activated',
            assignee_user_id: 'author-1',
            task_id: 'task-n3',
          },
        ],
      },
      { preferAssigneeUserId: 'author-1' },
    )
    expect(taskId).toBe('task-n3')
  })
})
