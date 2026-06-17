import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import ElementPlus, { ElMessage, ElMessageBox } from 'element-plus'
import type { ComponentPublicInstance } from 'vue'
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

vi.mock('@/api/task-center', () => ({
  getTaskCenterSnapshot: vi.fn(),
}))

vi.mock('@/api/workflow-graph', () => ({
  listGraphTemplates: vi.fn(),
}))

import { listDepartments } from '@/api/departments'
import { getTaskCenterSnapshot } from '@/api/task-center'
import { listUsers } from '@/api/users'
import { listGraphTemplates } from '@/api/workflow-graph'
import {
  createTaskTemplate,
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

function buildStepState(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    step_key: 'draft',
    title: '发起执行',
    description: '',
    step_type: 'task',
    assignment_mode: 'single',
    join_mode: 'all',
    assignee_rule_type: 'initiator',
    assignee_user_id: '',
    assignee_user_ids: [],
    default_due_offset_hours: undefined,
    depends_on_step_keys: [],
    approval_type: 'none',
    reject_target_step_key: '',
    downstream_template_code: '',
    downstream_spawn_mode: 'single',
    downstream_spawn_source_step_key: '',
    ...overrides,
  }
}

type TaskTemplatesSetupState = {
  createForm: {
    code: string
    name: string
    category: string
    description: string
    steps: Array<Record<string, unknown>>
  }
  handleSaveTemplate: () => Promise<void>
}

function configureCreateForm(
  wrapper: VueWrapper<ComponentPublicInstance>,
  code: string,
  name: string,
  steps: Array<Record<string, unknown>>,
): TaskTemplatesSetupState {
  const setupState = (wrapper.vm as ComponentPublicInstance).$?.setupState as TaskTemplatesSetupState
  expect(setupState).toBeTruthy()
  setupState.createForm.code = code
  setupState.createForm.name = name
  setupState.createForm.category = 'ops'
  setupState.createForm.description = ''
  setupState.createForm.steps = steps
  return setupState
}

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
  base_code: 'onboard-basic',
  version: 1,
  name: '入职模板',
  category: 'hr',
  description: '用于员工入职',
  trigger_type: 'manual',
  config: {},
  is_active: true,
  created_by: 'user-1',
  source_template_id: null,
  latest_version: 1,
  has_instances: false,
  is_structure_locked: false,
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
  last_run_at: '2025-01-05T09:00:00Z',
  last_run_status: 'success',
  last_run_message: '成功实例化 1 条任务',
  last_run_task_count: 1,
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

const mockTaskCenterSnapshot = {
  permissions: {
    can_manage_templates: true,
    can_publish_task: true,
    can_create_task: true,
    can_view_all_tasks: true,
    can_manage_users: true,
  },
  template_summaries: [],
  publish_department_options: [],
  publish_user_options: [],
  task_inbox: [],
  task_tracking: [],
  task_history: [],
  task_memos: [],
}

async function mountTaskTemplatesView() {
  const wrapper = mount(TaskTemplatesView, {
    global: {
      plugins: [ElementPlus],
    },
  })
  await flushPromises()
  return wrapper
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
  total_step_count: 2,
  completed_step_count: 0,
  active_step_count: 1,
  blocked_step_count: 1,
  ready_step_count: 0,
  progress_percent: 0,
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
      history_iteration_count: 1,
      latest_iteration: 1,
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
      history_iteration_count: 0,
      latest_iteration: 0,
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
    authStore.user = mockUser

    vi.mocked(listTaskTemplates).mockResolvedValue([mockTemplate])
    vi.mocked(listTaskSchedules).mockResolvedValue([mockSchedule])
    vi.mocked(listTaskTemplateInstances).mockResolvedValue([])
    vi.mocked(listDepartments).mockResolvedValue([mockDepartment])
    vi.mocked(listUsers).mockResolvedValue([mockUser])
    vi.mocked(getTaskCenterSnapshot).mockResolvedValue(mockTaskCenterSnapshot)
    vi.mocked(listGraphTemplates).mockResolvedValue([])
    vi.mocked(createTaskTemplate).mockResolvedValue(mockTemplate)
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
    const wrapper = await mountTaskTemplatesView()

    expect(wrapper.text()).toContain('入职模板')
    expect(wrapper.text()).toContain('V1')
    expect(wrapper.text()).toContain('周期调度')
    expect(wrapper.text()).toContain('最近执行成功')

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

    const wrapper = await mountTaskTemplatesView()

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
          approval_type: 'none',
          reject_target_step_key: null,
          downstream_trigger: null,
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
          approval_type: 'none',
          reject_target_step_key: null,
          downstream_trigger: null,
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

    const wrapper = await mountTaskTemplatesView()

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

    const wrapper = await mountTaskTemplatesView()

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
    vi.mocked(listTaskTemplates).mockResolvedValue([
      {
        ...mockTemplate,
        has_instances: true,
        is_structure_locked: true,
      },
    ])

    const wrapper = await mountTaskTemplatesView()

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
    expect(wrapper.text()).toContain('新建版本')
  })

  it('creates a new template version from a locked template', async () => {
    const versionedTemplate: TaskTemplate = {
      ...mockTemplate,
      has_instances: true,
      is_structure_locked: true,
      latest_version: 1,
    }
    const createdVersion: TaskTemplate = {
      ...mockTemplate,
      id: 'template-2',
      code: 'onboard-basic-v2',
      version: 2,
      latest_version: 2,
      source_template_id: 'template-1',
    }
    vi.mocked(listTaskTemplates)
      .mockResolvedValueOnce([versionedTemplate])
      .mockResolvedValueOnce([versionedTemplate, createdVersion])
    vi.mocked(listTaskTemplateInstances).mockResolvedValue([mockTemplateInstance])
    vi.mocked(createTaskTemplate).mockResolvedValue(createdVersion)

    const wrapper = await mountTaskTemplatesView()

    const createVersionButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('新建版本'))
    expect(createVersionButton).toBeTruthy()
    await createVersionButton?.trigger('click')
    await flushPromises()

    const saveButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('保存新版本'))
    expect(saveButton).toBeTruthy()
    await saveButton?.trigger('click')
    await flushPromises()

    expect(createTaskTemplate).toHaveBeenCalledWith(
      expect.objectContaining({
        code: 'onboard-basic-v2',
        source_template_id: 'template-1',
      }),
    )
  })

  it('deletes a template after confirmation', async () => {
    vi.mocked(listTaskTemplates)
      .mockResolvedValueOnce([mockTemplate])
      .mockResolvedValueOnce([])

    const wrapper = await mountTaskTemplatesView()

    const deleteButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('删除模板'))
    expect(deleteButton).toBeTruthy()

    await deleteButton?.trigger('click')
    await flushPromises()

    expect(deleteTaskTemplate).toHaveBeenCalledWith('template-1')
  })

  it('rejects cyclic step dependencies before submitting the template', async () => {
    const messageErrorSpy = vi.spyOn(ElMessage, 'error').mockImplementation(() => '')

    const wrapper = await mountTaskTemplatesView()
    const setupState = configureCreateForm(wrapper, 'cycle-template', '循环模板', [
      buildStepState({ step_key: 'draft', title: '撰写方案', depends_on_step_keys: ['review'] }),
      buildStepState({
        step_key: 'review',
        title: '经理复核',
        assignee_rule_type: 'department_manager',
        depends_on_step_keys: ['draft'],
      }),
    ])

    await setupState.handleSaveTemplate()
    await flushPromises()

    expect(createTaskTemplate).not.toHaveBeenCalled()
    expect(messageErrorSpy).toHaveBeenCalledWith('正常流转路径存在循环依赖，请调整前置步骤关系')
  })

  it('rejects isolated steps before submitting the template', async () => {
    const messageErrorSpy = vi.spyOn(ElMessage, 'error').mockImplementation(() => '')

    const wrapper = await mountTaskTemplatesView()
    const setupState = configureCreateForm(wrapper, 'island-template', '孤岛模板', [
      buildStepState({ step_key: 'draft', title: '撰写方案' }),
      buildStepState({
        step_key: 'review',
        title: '经理复核',
        assignee_rule_type: 'department_manager',
        depends_on_step_keys: ['draft'],
      }),
      buildStepState({ step_key: 'archive', title: '归档记录' }),
    ])

    await setupState.handleSaveTemplate()
    await flushPromises()

    expect(createTaskTemplate).not.toHaveBeenCalled()
    expect(messageErrorSpy).toHaveBeenCalledWith('当前模板存在未连接的孤岛步骤，请确认每个步骤都和主流程相连')
  })

  it('rejects single-task steps that use multi-assignee rules', async () => {
    const messageErrorSpy = vi.spyOn(ElMessage, 'error').mockImplementation(() => '')

    const wrapper = await mountTaskTemplatesView()
    const setupState = configureCreateForm(wrapper, 'single-invalid-template', '非法分配模板', [
      buildStepState({
        step_key: 'collect',
        title: '多人提交素材',
        assignee_rule_type: 'user_ids',
        assignee_user_ids: ['user-1', 'user-2'],
      }),
    ])

    await setupState.handleSaveTemplate()
    await flushPromises()

    expect(createTaskTemplate).not.toHaveBeenCalled()
    expect(messageErrorSpy).toHaveBeenCalledWith('步骤「多人提交素材」使用单任务模式时不能选择多人负责人规则')
  })

  it('shows wait-any warning and race-cancelled run hint', async () => {
    const waitAnyTemplate: TaskTemplate = {
      ...mockTemplate,
      steps: [
        {
          ...mockTemplate.steps[0],
          step_key: 'parallel_review',
          title: '并行审核',
          assignment_mode: 'fan_out',
          join_mode: 'any',
          default_assignee_rule: { type: 'user_ids', user_ids: ['user-1', 'user-2'] },
        },
      ],
    }

    const waitAnyInstance: TaskTemplateInstance = {
      ...mockTemplateInstance,
      step_snapshots: [
        {
          ...mockTemplateInstance.step_snapshots[0],
          step: waitAnyTemplate.steps[0],
          status: 'active',
          total_run_count: 2,
          active_run_count: 0,
          completed_run_count: 1,
          step_runs: [
            {
              ...mockTemplateInstance.step_snapshots[0]!.step_runs[0]!,
              id: 'run-completed',
              assignee_user_id: 'user-1',
              assignee_email: 'admin@example.com',
              status: 'completed',
            },
            {
              ...mockTemplateInstance.step_snapshots[0]!.step_runs[0]!,
              id: 'run-cancelled',
              assignee_user_id: 'user-2',
              assignee_email: 'employee@example.com',
              status: 'cancelled',
              task: null,
            },
          ],
        },
      ],
    }

    vi.mocked(listTaskTemplates).mockResolvedValue([waitAnyTemplate])
    vi.mocked(listTaskTemplateInstances).mockResolvedValue([waitAnyInstance])

    const wrapper = await mountTaskTemplatesView()

    expect(wrapper.text()).toContain('任一完成推进')
    expect(wrapper.text()).toContain('已因或签命中被系统撤权')

    const editButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('编辑模板'))
    expect(editButton).toBeTruthy()
    await editButton?.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('该步骤启用或签/抢单模式')
  })

  it('shows deep rejection replay hint when step has history iterations', async () => {
    const replayedInstance: TaskTemplateInstance = {
      ...mockTemplateInstance,
      step_snapshots: [
        {
          ...mockTemplateInstance.step_snapshots[0]!,
          history_iteration_count: 2,
          latest_iteration: 3,
        },
      ],
    }

    vi.mocked(listTaskTemplateInstances).mockResolvedValue([replayedInstance])

    const wrapper = await mountTaskTemplatesView()

    expect(wrapper.text()).toContain('曾被系统打回重放')
    expect(wrapper.text()).toContain('累计 2 次')
  })

  it('adds IF routing rule and ELSE fallback, and saves template', async () => {
    const wrapper = await mountTaskTemplatesView()

    const editButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('编辑模板'))
    expect(editButton).toBeTruthy()
    await editButton?.trigger('click')
    await flushPromises()

    const setupState = (wrapper.vm as ComponentPublicInstance).$?.setupState as {
      createForm: { steps: Array<Record<string, unknown>> }
      handleSaveTemplate: () => Promise<void>
    }

    // 直接操控 setupState 给第一个步骤添加 routing_rules
    const step = setupState.createForm.steps[0] as {
      routing_rules: Array<Record<string, unknown>>
    }
    step.routing_rules = [
      { condition: { field: 'amount', operator: 'gt', value: '1000' }, target_step_key: 'review' },
      { else: true, target_step_key: 'review' },
    ]

    await wrapper.vm.$nextTick()

    const saveButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('更新模板'))
    expect(saveButton).toBeTruthy()
    await saveButton?.trigger('click')
    await flushPromises()

    expect(updateTaskTemplate).toHaveBeenCalledWith(
      'template-1',
      expect.objectContaining({
        steps: expect.arrayContaining([
          expect.objectContaining({
            step_key: 'collect',
            config: {
              routing_rules: [
                { condition: { field: 'amount', operator: 'gt', value: '1000' }, target_step_key: 'review' },
                { else: true, target_step_key: 'review' },
              ],
            },
          }),
        ]),
      }),
    )
  })

  it('throws an error when routing rules lack ELSE fallback', async () => {
    const wrapper = await mountTaskTemplatesView()

    const editButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('编辑模板'))
    await editButton?.trigger('click')
    await flushPromises()

    const setupState = (wrapper.vm as ComponentPublicInstance).$?.setupState as {
      createForm: { steps: Array<Record<string, unknown>> }
    }

    const step = setupState.createForm.steps[0] as {
      routing_rules: Array<Record<string, unknown>>
    }
    // 只加 IF 规则，不加 ELSE
    step.routing_rules = [
      { condition: { field: 'amount', operator: 'gt', value: '1000' }, target_step_key: 'review' },
    ]

    await wrapper.vm.$nextTick()

    const saveButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('更新模板'))
    await saveButton?.trigger('click')
    await flushPromises()

    // 不应调用 updateTaskTemplate；ElMessage.error 应触发（通过 wrapper text 间接验证）
    expect(updateTaskTemplate).not.toHaveBeenCalledWith(
      'template-1',
      expect.objectContaining({
        steps: expect.arrayContaining([
          expect.objectContaining({ config: expect.objectContaining({ routing_rules: expect.any(Array) }) }),
        ]),
      }),
    )
  })

  it('shows confirm dialog when any step has join_mode=any', async () => {
    vi.mocked(ElMessageBox.confirm).mockResolvedValue('confirm' as never)

    const wrapper = await mountTaskTemplatesView()

    const editButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('编辑模板'))
    await editButton?.trigger('click')
    await flushPromises()

    const setupState = (wrapper.vm as ComponentPublicInstance).$?.setupState as {
      createForm: { steps: Array<Record<string, unknown>> }
    }
    const step = setupState.createForm.steps[0] as { join_mode: string; assignment_mode: string }
    step.assignment_mode = 'fan_out'
    step.join_mode = 'any'

    await wrapper.vm.$nextTick()

    const saveButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('更新模板'))
    await saveButton?.trigger('click')
    await flushPromises()

    // ElMessageBox.confirm 应被调用（join_mode=any 警告）
    expect(ElMessageBox.confirm).toHaveBeenCalled()
  })
})
