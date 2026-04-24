import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus, { ElMessageBox } from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { Department, Task, TaskSchedule, TaskTemplate, TaskTemplateInstance, User } from '@/types/api'

vi.mock('@/api/task-templates', () => ({
  createTaskSchedule: vi.fn(),
  createTaskTemplate: vi.fn(),
  deleteTaskTemplate: vi.fn(),
  instantiateTaskTemplate: vi.fn(),
  listTaskTemplateInstances: vi.fn(),
  listTaskSchedules: vi.fn(),
  listTaskTemplates: vi.fn(),
  updateTaskSchedule: vi.fn(),
  updateTaskTemplate: vi.fn(),
}))

vi.mock('@/api/departments', () => ({
  listDepartments: vi.fn(),
}))

vi.mock('@/api/users', () => ({
  listUsers: vi.fn(),
}))

import { listDepartments } from '@/api/departments'
import { listUsers } from '@/api/users'
import {
  createTaskSchedule,
  deleteTaskTemplate,
  instantiateTaskTemplate,
  listTaskTemplateInstances,
  listTaskSchedules,
  listTaskTemplates,
  updateTaskSchedule,
  updateTaskTemplate,
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
      assignment_mode: 'single',
      join_mode: 'all',
      default_assignee_rule: { type: 'initiator' },
      default_due_offset_hours: null,
      sort_order: 1,
      config: {},
      created_at: '2025-01-01T00:00:00Z',
      updated_at: '2025-01-01T00:00:00Z',
      depends_on_step_keys: [],
    },
    {
      id: 'step-2',
      template_id: 'template-1',
      step_key: 'review',
      title: '经理复核',
      description: null,
      step_type: 'task',
      assignment_mode: 'single',
      join_mode: 'all',
      default_assignee_rule: { type: 'department_manager' },
      default_due_offset_hours: null,
      sort_order: 2,
      config: {},
      created_at: '2025-01-01T00:00:00Z',
      updated_at: '2025-01-01T00:00:00Z',
      depends_on_step_keys: ['collect'],
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
  title: '入职模板 / 收集资料',
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

const mockTemplateInstance: TaskTemplateInstance = {
  id: 'instance-1',
  template_id: 'template-1',
  initiator_user_id: 'user-1',
  initiator_email: 'admin@example.com',
  department_id: 'dept-1',
  department_name: '运营部',
  status: 'in_progress',
  payload: { department_id: 'dept-1' },
  completed_at: null,
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
  step_snapshots: [
    {
      step: mockTemplate.steps[0],
      status: 'active',
      blocked_dependency_keys: [],
      total_run_count: 1,
      active_run_count: 1,
      completed_run_count: 0,
      step_runs: [
        {
          id: 'run-1',
          instance_id: 'instance-1',
          template_step_id: 'step-1',
          assignee_user_id: 'user-1',
          assignee_email: 'admin@example.com',
          status: 'active',
          completed_at: null,
          created_at: '2025-01-01T00:00:00Z',
          updated_at: '2025-01-01T00:00:00Z',
          task: mockTask,
        },
      ],
    },
    {
      step: mockTemplate.steps[1],
      status: 'blocked',
      blocked_dependency_keys: ['collect'],
      total_run_count: 0,
      active_run_count: 0,
      completed_run_count: 0,
      step_runs: [],
    },
  ],
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
    vi.mocked(listTaskTemplateInstances).mockResolvedValue([])
    vi.mocked(listDepartments).mockResolvedValue([mockDepartment])
    vi.mocked(listUsers).mockResolvedValue([mockUser])
    vi.mocked(instantiateTaskTemplate).mockResolvedValue({
      template: mockTemplate,
      instance: mockTemplateInstance,
      tasks: [mockTask],
    })
    vi.mocked(createTaskSchedule).mockResolvedValue(mockSchedule)
    vi.mocked(deleteTaskTemplate).mockResolvedValue()
    vi.mocked(updateTaskSchedule).mockResolvedValue(mockSchedule)
    vi.mocked(updateTaskTemplate).mockResolvedValue(mockTemplate)
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as never)
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
    expect(wrapper.text()).toContain('入职模板 / 收集资料')
    expect(wrapper.text()).toContain('未激活')
  })

  it('edits an existing template with the structured designer', async () => {
    const updatedTemplate: TaskTemplate = {
      ...mockTemplate,
      name: '入职模板升级版',
      steps: [
        {
          ...mockTemplate.steps[0],
          title: '收集基础资料',
        },
        ...mockTemplate.steps.slice(1),
      ],
    }
    vi.mocked(listTaskTemplates)
      .mockResolvedValueOnce([mockTemplate])
      .mockResolvedValueOnce([updatedTemplate])
    vi.mocked(updateTaskTemplate).mockResolvedValue(updatedTemplate)

    const wrapper = mount(TaskTemplatesView, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()

    const editButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('编辑模板'))
    expect(editButton).toBeTruthy()
    await editButton?.trigger('click')
    await flushPromises()

    const nameInput = wrapper.find('input[placeholder="例如：参与选题会"]')
    expect(nameInput.exists()).toBe(true)
    await nameInput.setValue('入职模板升级版')

    const saveButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('更新模板'))
    expect(saveButton).toBeTruthy()
    await saveButton?.trigger('click')
    await flushPromises()

    expect(updateTaskTemplate).toHaveBeenCalledWith('template-1', {
      code: 'onboard-basic',
      name: '入职模板升级版',
      category: 'hr',
      description: '用于员工入职',
      steps: [
        {
          step_key: 'collect',
          title: '收集资料',
          description: null,
          step_type: 'task',
          assignment_mode: 'single',
          join_mode: 'all',
          default_assignee_rule: { type: 'initiator' },
          default_due_offset_hours: null,
          sort_order: 1,
          config: {},
          depends_on_step_keys: [],
        },
        {
          step_key: 'review',
          title: '经理复核',
          description: null,
          step_type: 'task',
          assignment_mode: 'single',
          join_mode: 'all',
          default_assignee_rule: { type: 'department_manager' },
          default_due_offset_hours: null,
          sort_order: 2,
          config: {},
          depends_on_step_keys: ['collect'],
        },
      ],
    })
    expect(wrapper.text()).toContain('入职模板升级版')
  })

  it('edits an existing schedule inline', async () => {
    const updatedSchedule: TaskSchedule = {
      ...mockSchedule,
      cron_expr: '0 10 * * *',
      timezone: 'Asia/Shanghai',
      is_active: false,
    }
    vi.mocked(listTaskSchedules)
      .mockResolvedValueOnce([mockSchedule])
      .mockResolvedValueOnce([updatedSchedule])
    vi.mocked(updateTaskSchedule).mockResolvedValue(updatedSchedule)

    const wrapper = mount(TaskTemplatesView, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()

    const editScheduleButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('编辑调度'))
    expect(editScheduleButton).toBeTruthy()
    await editScheduleButton?.trigger('click')
    await flushPromises()

    const cronInput = wrapper
      .findAll('input')
      .find((node) => (node.element as HTMLInputElement).value === '0 9 * * 1-5')
    expect(cronInput).toBeTruthy()
    await cronInput?.setValue('0 10 * * *')

    const timezoneInput = wrapper
      .findAll('input')
      .find((node) => (node.element as HTMLInputElement).value === 'UTC')
    expect(timezoneInput).toBeTruthy()
    await timezoneInput?.setValue('Asia/Shanghai')

    const switchInput = wrapper.find('input[role="switch"]')
    expect(switchInput.exists()).toBe(true)
    await switchInput.setValue(false)

    const saveButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('更新调度'))
    expect(saveButton).toBeTruthy()
    await saveButton?.trigger('click')
    await flushPromises()

    expect(updateTaskSchedule).toHaveBeenCalledWith('schedule-1', {
      cron_expr: '0 10 * * *',
      timezone: 'Asia/Shanghai',
      payload: {},
      is_active: false,
    })
    expect(wrapper.text()).toContain('0 10 * * *')
    expect(wrapper.text()).toContain('Asia/Shanghai')
    expect(wrapper.text()).toContain('停用')
  })

  it('toggles template active state from the detail header', async () => {
    const inactiveTemplate: TaskTemplate = {
      ...mockTemplate,
      is_active: false,
    }
    vi.mocked(listTaskTemplates)
      .mockResolvedValueOnce([mockTemplate])
      .mockResolvedValueOnce([inactiveTemplate])
    vi.mocked(updateTaskTemplate).mockResolvedValue(inactiveTemplate)

    const wrapper = mount(TaskTemplatesView, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()

    const toggleButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('停用模板'))
    expect(toggleButton).toBeTruthy()
    await toggleButton?.trigger('click')
    await flushPromises()

    expect(updateTaskTemplate).toHaveBeenCalledWith('template-1', {
      is_active: false,
    })
    expect(wrapper.text()).toContain('启用模板')
    expect(wrapper.text()).toContain('停用')
  })

  it('locks the step designer when the template already has instances', async () => {
    vi.mocked(listTaskTemplateInstances).mockResolvedValue([mockTemplateInstance])

    const wrapper = mount(TaskTemplatesView, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()

    const editButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('编辑模板'))
    expect(editButton).toBeTruthy()
    await editButton?.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('该模板已有实例运行记录')

    const addStepButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('添加步骤'))
    expect(addStepButton?.attributes('disabled')).toBeDefined()
  })

  it('deletes a template after confirmation', async () => {
    vi.mocked(listTaskTemplates)
      .mockResolvedValueOnce([mockTemplate])
      .mockResolvedValueOnce([])

    const wrapper = mount(TaskTemplatesView, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()

    const deleteButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('删除模板'))
    expect(deleteButton).toBeTruthy()

    await deleteButton?.trigger('click')
    await flushPromises()

    expect(deleteTaskTemplate).toHaveBeenCalledWith('template-1')
  })
})
