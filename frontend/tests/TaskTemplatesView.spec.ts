import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { Department, Task, TaskSchedule, TaskTemplate, User } from '@/types/api'

vi.mock('@/api/task-templates', () => ({
  createTaskSchedule: vi.fn(),
  createTaskTemplate: vi.fn(),
  instantiateTaskTemplate: vi.fn(),
  listTaskSchedules: vi.fn(),
  listTaskTemplates: vi.fn(),
}))

vi.mock('@/api/departments', () => ({
  listDepartments: vi.fn(),
}))

import { listDepartments } from '@/api/departments'
import {
  createTaskSchedule,
  instantiateTaskTemplate,
  listTaskSchedules,
  listTaskTemplates,
} from '@/api/task-templates'
import { useAuthStore } from '@/stores/auth'
import TaskTemplatesView from '@/views/TaskTemplatesView.vue'

const mockUser: User = {
  id: 'user-1',
  email: 'admin@example.com',
  role: 'admin',
  status: 'active',
  last_login_at: null,
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
}

const mockDepartment: Department = {
  id: 'dept-1',
  name: '运营部',
  code: 'ops',
  parent_id: null,
  manager_id: 'user-1',
  sort_order: 1,
  is_active: true,
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
}

const mockTemplate: TaskTemplate = {
  id: 'template-1',
  code: 'onboard-basic',
  name: '入职模板',
  category: 'hr',
  description: '用于员工入职',
  trigger_type: 'manual',
  config: {},
  is_active: true,
  created_by: 'user-1',
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
  steps: [
    {
      id: 'step-1',
      template_id: 'template-1',
      step_key: 'collect',
      title: '收集资料',
      description: null,
      step_type: 'task',
      default_assignee_rule: { type: 'initiator' },
      default_due_offset_hours: null,
      sort_order: 1,
      config: {},
      created_at: '2025-01-01T00:00:00Z',
      updated_at: '2025-01-01T00:00:00Z',
      depends_on_step_keys: [],
    },
  ],
  schedules: [],
}

const mockSchedule: TaskSchedule = {
  id: 'schedule-1',
  template_id: 'template-1',
  owner_user_id: 'user-1',
  cron_expr: '0 9 * * 1-5',
  timezone: 'UTC',
  next_run_at: '2025-01-06T09:00:00Z',
  is_active: true,
  payload: {},
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
}

const mockTask: Task = {
  id: 'task-1',
  title: '办理账号',
  description: null,
  creator_id: 'user-1',
  assignee_id: 'user-1',
  department_id: 'dept-1',
  status: 'todo',
  priority: 'medium',
  due_date: null,
  started_at: null,
  completed_at: null,
  parent_task_id: null,
  source_type: 'template',
  extra_metadata: {},
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
}

describe('TaskTemplates view', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()

    const authStore = useAuthStore()
    authStore.initialized = true
    authStore.accessToken = 'test-access-token'
    authStore.refreshToken = 'test-refresh-token'
    authStore.user = mockUser

    vi.mocked(listTaskTemplates).mockResolvedValue([mockTemplate])
    vi.mocked(listTaskSchedules).mockResolvedValue([mockSchedule])
    vi.mocked(listDepartments).mockResolvedValue([mockDepartment])
    vi.mocked(instantiateTaskTemplate).mockResolvedValue({
      template: mockTemplate,
      tasks: [mockTask],
    })
    vi.mocked(createTaskSchedule).mockResolvedValue(mockSchedule)
  })

  it('renders template details and instantiates a template', async () => {
    const wrapper = mount(TaskTemplatesView, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('入职模板')
    expect(wrapper.text()).toContain('周期调度')

    const button = wrapper
      .findAll('button')
      .find((node) => node.text().includes('实例化模板'))
    expect(button).toBeTruthy()
    await button?.trigger('click')
    await flushPromises()

    expect(instantiateTaskTemplate).toHaveBeenCalledWith('template-1', {
      department_id: null,
      payload: {},
    })
    expect(wrapper.text()).toContain('办理账号')
  })
})
