import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { describe, expect, it } from 'vitest'

import TaskDetailGraphTelemetry from '@/components/task-detail/TaskDetailGraphTelemetry.vue'
import type { WorkflowGraphInstanceDetail, WorkflowNodeInstanceSummary } from '@/types/api'

function nodeFixture(overrides: Partial<WorkflowNodeInstanceSummary> = {}): WorkflowNodeInstanceSummary {
  return {
    id: 'node-1',
    instance_id: 'instance-1',
    template_node_id: 'template-node-1',
    node_key: 'draft',
    title: '撰写初稿',
    node_type: 'task',
    engine_state: 'activated',
    business_state: 'doing',
    assignee_user_id: 'user-1',
    iteration: 1,
    activated_at: '2026-08-12T00:00:00Z',
    completed_at: null,
    terminated_at: null,
    created_at: '2026-08-12T00:00:00Z',
    task_id: 'task-1',
    ...overrides,
  }
}

function graphFixture(): WorkflowGraphInstanceDetail {
  return {
    id: 'instance-1',
    template_id: 'template-1',
    initiator_user_id: 'user-1',
    department_id: 'department-1',
    source_type: 'task',
    status: 'active',
    current_node_key: 'draft',
    context: {},
    result: null,
    diagnostics: {},
    context_version: 1,
    max_iterations: 3,
    completed_at: null,
    created_at: '2026-08-12T00:00:00Z',
    node_instances: [
      nodeFixture(),
      nodeFixture({
        id: 'node-2',
        node_key: 'review',
        title: '评审',
        engine_state: 'terminated',
        business_state: 'cancelled',
        iteration: 2,
        terminated_at: '2026-08-12T00:30:00Z',
      }),
    ],
    total_node_count: 2,
    completed_node_count: 1,
    active_node_count: 1,
    pending_node_count: 0,
    progress_percent: 50,
  }
}

describe('TaskDetailGraphTelemetry', () => {
  it('renders the compact node tracker with state, version and termination hints', () => {
    const wrapper = mount(TaskDetailGraphTelemetry, {
      props: { graphInstance: graphFixture(), compact: true },
      global: { plugins: [ElementPlus] },
    })

    expect(wrapper.find('[data-testid="task-detail-graph-collapse"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="tasks-graph-panel"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('工作流节点追踪（完整日志见任务统计）')
    expect(wrapper.text()).toContain('撰写初稿')
    expect(wrapper.text()).toContain('进行中')
    expect(wrapper.text()).toContain('V2')
    expect(wrapper.text()).toContain('已被系统终止（or-join 撤权或深度打回）')
  })

  it('keeps the expanded node tracker variant', () => {
    const wrapper = mount(TaskDetailGraphTelemetry, {
      props: { graphInstance: graphFixture(), compact: false },
      global: { plugins: [ElementPlus] },
    })

    expect(wrapper.find('[data-testid="task-detail-graph-collapse"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="tasks-graph-panel"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('工作流节点追踪')
    expect(wrapper.text()).toContain('耗时：进行中')
    expect(wrapper.text()).toContain('耗时：30 分钟')
  })
})
