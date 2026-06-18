import { describe, expect, it } from 'vitest'

import { resolveTaskDetailProfile, isVideoWorkflowProfile } from './profile'
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

describe('resolveTaskDetailProfile', () => {
  it('resolves video_n1_capture for assignee on N1 node', () => {
    const task = makeTask({
      extra_metadata: {
        workflow_graph_instance_id: 'inst-1',
        template_node_key: 'N1_PROPOSE',
      },
    })
    const profile = resolveTaskDetailProfile(task, { currentUserId: 'user-1' })
    expect(profile.id).toBe('video_n1_capture')
    expect(profile.submitMode).toBe('form')
    expect(profile.hideDeliverable).toBe(true)
  })

  it('resolves video_batch_root for batch root task', () => {
    const task = makeTask({
      title: '选题会 / 春季选题会',
      extra_metadata: {
        workflow_graph_instance_id: 'inst-1',
        workflow_graph_root_task: true,
        run_kind: 'batch',
      },
    })
    const profile = resolveTaskDetailProfile(task)
    expect(profile.id).toBe('video_batch_root')
    expect(profile.showCaptureProgress).toBe(true)
  })

  it('resolves video_n2_aggregate for aggregate node', () => {
    const task = makeTask({
      extra_metadata: {
        workflow_graph_instance_id: 'inst-1',
        template_node_key: 'N2_AGGREGATE',
      },
    })
    expect(resolveTaskDetailProfile(task).id).toBe('video_n2_aggregate')
  })

  it('resolves graph_manual for dual-write handshake task', () => {
    const task = makeTask({
      source_type: 'manual',
      status: 'todo',
      extra_metadata: {
        workflow_graph_instance_id: 'inst-1',
        workflow_node_instance_id: 'node-1',
      },
    })
    const profile = resolveTaskDetailProfile(task)
    expect(profile.id).toBe('graph_manual')
    expect(profile.hideDeliverable).toBe(false)
  })

  it('identifies video workflow profiles', () => {
    const task = makeTask({
      extra_metadata: {
        workflow_graph_instance_id: 'inst-1',
        template_node_key: 'N3_SCRIPT_WRITE',
      },
    })
    const profile = resolveTaskDetailProfile(task)
    expect(isVideoWorkflowProfile(profile)).toBe(true)
    expect(profile.id).toBe('video_production_step')
  })
})
