import { defineComponent, ref } from 'vue'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import TaskDetailWorkflowPresentation from '@/components/task-detail/TaskDetailWorkflowPresentation.vue'
import type { Task, User, WorkflowGraphInstanceDetail } from '@/types/api'
import type { TaskDetailProfile } from '@/domain/task-detail/profile'
import type { WorkflowRunEventItem } from '@/types/workflowVideo'

const deliverableSubmit = vi.fn()
const DeliverableStub = defineComponent({
  name: 'WorkflowDeliverablePanel',
  setup(_, { expose }) {
    expose({ submit: deliverableSubmit, submitting: ref(true) })
    return () => '交付面板'
  },
})

const panelStubs = {
  WorkflowTrackingPanel: { template: '<div data-testid="tracking-panel">跟踪面板</div>' },
  BatchRunDashboard: { template: '<div data-testid="run-dashboard">运行看板</div>' },
  WorkflowCaptureProgressPanel: { template: '<div data-testid="capture-progress">采集进度</div>' },
  CapturePanel: { template: '<div data-testid="capture-panel">采集表单</div>' },
  WorkflowDeliverablePanel: DeliverableStub,
  TemplateAggregatePanel: { template: '<div data-testid="aggregate-panel">汇总面板</div>' },
  RouterLink: { template: '<a data-testid="stats-link"><slot /></a>' },
}

function taskFixture(overrides: Partial<Task> = {}): Task {
  return {
    id: 'task-1',
    title: '工作流展示任务',
    description: null,
    creator_id: 'user-1',
    assignee_id: 'user-2',
    department_id: 'department-1',
    status: 'doing',
    priority: 'medium',
    due_date: null,
    started_at: null,
    completed_at: null,
    parent_task_id: null,
    source_type: 'template',
    extra_metadata: {},
    created_at: '2026-08-12T00:00:00Z',
    updated_at: '2026-08-12T00:00:00Z',
    ...overrides,
  }
}

function graphFixture(context: Record<string, unknown> = {}): WorkflowGraphInstanceDetail {
  return {
    id: 'instance-1',
    template_id: 'template-1',
    initiator_user_id: 'user-1',
    department_id: 'department-1',
    source_type: 'task',
    status: 'active',
    current_node_key: null,
    context,
    result: null,
    diagnostics: {},
    context_version: 1,
    max_iterations: 3,
    completed_at: null,
    created_at: '2026-08-12T00:00:00Z',
    node_instances: [],
    total_node_count: 0,
    completed_node_count: 0,
    active_node_count: 0,
    pending_node_count: 0,
    progress_percent: 0,
  }
}

function profileFixture(overrides: Partial<TaskDetailProfile> = {}): TaskDetailProfile {
  return {
    id: 'workflow_collection',
    surface: 'collection',
    statePolicy: 'collection',
    variant: null,
    features: {},
    rootVisibility: 'normal',
    submitMode: 'form',
    hideDeliverable: true,
    hideHandshakeFields: true,
    hideWatchers: true,
    collapseComments: true,
    compactMetadata: true,
    showCaptureProgress: false,
    ...overrides,
  }
}

function eventFixture(index: number): WorkflowRunEventItem {
  return {
    id: `event-${index}`,
    instance_id: 'instance-1',
    event_type: index === 4 ? 'capture_rejected' : 'node_completed',
    event_version: index,
    aggregate_version: null,
    command_id: null,
    causation_id: null,
    correlation_id: null,
    actor_user_id: null,
    payload: { reason: `原因 ${index}` },
    occurred_at: `2026-08-12T00:0${index}:00Z`,
    created_at: `2026-08-12T00:0${index}:00Z`,
  }
}

const users: User[] = []

function mountPresentation(options: {
  task?: Task
  graphInstance?: WorkflowGraphInstanceDetail
  profile?: TaskDetailProfile
  events?: WorkflowRunEventItem[]
  compactTelemetry?: boolean
} = {}) {
  return mount(TaskDetailWorkflowPresentation, {
    props: {
      task: options.task ?? taskFixture(),
      graphInstance: options.graphInstance ?? graphFixture(),
      profile: options.profile ?? profileFixture(),
      users,
      canManageReject: true,
      currentUserId: 'user-2',
      runEvents: options.events ?? [],
      compactTelemetry: options.compactTelemetry ?? true,
    },
    global: {
      plugins: [ElementPlus],
      stubs: panelStubs,
    },
  })
}

describe('TaskDetailWorkflowPresentation', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('selects collection panels from profile capabilities without video-specific gates', () => {
    const wrapper = mountPresentation({
      graphInstance: graphFixture({ aggregate_mode: 'batch' }),
      profile: profileFixture({
        features: {
          tracking: true,
          run_dashboard: true,
          capture_progress: true,
          aggregate: true,
        },
      }),
    })

    expect(wrapper.find('[data-testid="tracking-panel"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="run-dashboard"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="capture-progress"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="aggregate-panel"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="capture-panel"]').exists()).toBe(false)
  })

  it('keeps the header-facing deliverable submit handle', () => {
    const wrapper = mountPresentation({
      profile: profileFixture({
        id: 'workflow_deliverable',
        surface: 'deliverable',
        statePolicy: 'deliverable',
        variant: 'multi',
        submitMode: 'file',
      }),
    })
    const exposed = wrapper.vm as unknown as { submit: () => void; submitting: boolean }

    expect(exposed.submitting).toBe(true)
    exposed.submit()
    expect(deliverableSubmit).toHaveBeenCalledOnce()
  })

  it('keeps compact run events limited to three and links to task statistics', () => {
    const wrapper = mountPresentation({
      events: [eventFixture(1), eventFixture(2), eventFixture(3), eventFixture(4)],
      compactTelemetry: true,
    })

    expect(wrapper.find('[data-testid="workflow-run-events-compact"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="stats-link"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('最近事件')
    expect(wrapper.text().match(/节点已完成/g)).toHaveLength(3)
    expect(wrapper.text()).not.toContain('采集已打回')
    expect(wrapper.text()).not.toContain('原因 1')
  })
})
