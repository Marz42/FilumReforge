import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { User, WorkflowDefinition, WorkflowInstance, WorkflowStepRun } from '@/types/api'

vi.mock('@/api/workflows', () => ({
  actWorkflowStepRun: vi.fn(),
  createWorkflowDefinition: vi.fn(),
  listPendingWorkflowStepRuns: vi.fn(),
  listWorkflowDefinitions: vi.fn(),
  listWorkflowInstances: vi.fn(),
  startWorkflow: vi.fn(),
}))

import {
  actWorkflowStepRun,
  listPendingWorkflowStepRuns,
  listWorkflowDefinitions,
  listWorkflowInstances,
  startWorkflow,
} from '@/api/workflows'
import { useAuthStore } from '@/stores/auth'
import ApprovalsView from '@/views/ApprovalsView.vue'

const mockUser: User = {
  id: 'user-1',
  email: 'admin@example.com',
  role: 'admin',
  status: 'active',
  last_login_at: null,
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
}

const mockDefinition: WorkflowDefinition = {
  id: 'definition-1',
  code: 'purchase-flow',
  name: '采购审批',
  scope_type: 'task',
  status: 'active',
  version: 1,
  config: {},
  created_by: 'user-1',
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
  steps: [
    {
      id: 'step-1',
      definition_id: 'definition-1',
      step_key: 'manager',
      name: '直属审批',
      step_type: 'approval',
      approval_mode: 'single',
      assignee_rule: { type: 'department_manager' },
      reject_target_step_key: null,
      sort_order: 1,
      config: {},
      created_at: '2025-01-01T00:00:00Z',
      updated_at: '2025-01-01T00:00:00Z',
    },
  ],
}

const mockStepRun: WorkflowStepRun = {
  id: 'run-1',
  instance_id: 'instance-1',
  step_id: 'step-1',
  assignee_user_id: 'user-1',
  delegated_from_user_id: null,
  status: 'pending',
  acted_at: null,
  comment: null,
  payload: {},
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
  step: mockDefinition.steps[0]!,
}

const mockInstance: WorkflowInstance = {
  id: 'instance-1',
  definition_id: 'definition-1',
  source_type: 'task_request',
  source_id: null,
  initiator_user_id: 'user-1',
  status: 'in_progress',
  current_step_key: 'manager',
  payload: {},
  started_at: '2025-01-01T00:00:00Z',
  completed_at: null,
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
  step_runs: [mockStepRun],
  definition: mockDefinition,
}

describe('Approvals view', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()

    const authStore = useAuthStore()
    authStore.initialized = true
    authStore.accessToken = 'test-access-token'
    authStore.refreshToken = 'test-refresh-token'
    authStore.user = mockUser

    vi.mocked(listPendingWorkflowStepRuns).mockResolvedValue([mockStepRun])
    vi.mocked(listWorkflowDefinitions).mockResolvedValue([mockDefinition])
    vi.mocked(listWorkflowInstances).mockResolvedValue([mockInstance])
    vi.mocked(actWorkflowStepRun).mockResolvedValue({
      ...mockInstance,
      status: 'approved',
    })
    vi.mocked(startWorkflow).mockResolvedValue(mockInstance)
  })

  it('starts workflows and submits approval actions', async () => {
    const wrapper = mount(ApprovalsView, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('采购审批')
    expect(wrapper.text()).toContain('直属审批')

    const approveButton = wrapper.findAll('button').find((node) => node.text().includes('通过'))
    expect(approveButton).toBeTruthy()
    await approveButton?.trigger('click')
    await flushPromises()

    expect(actWorkflowStepRun).toHaveBeenCalledWith('run-1', 'approve')

    const startButton = wrapper.findAll('button').find((node) => node.text().includes('发起审批'))
    expect(startButton).toBeTruthy()
    await startButton?.trigger('click')
    await flushPromises()

    expect(startWorkflow).toHaveBeenCalledWith({
      definition_id: 'definition-1',
      source_type: 'task_request',
      payload: {},
    })
  })
})
