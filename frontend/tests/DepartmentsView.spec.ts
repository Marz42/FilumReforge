import { flushPromises, mount } from '@vue/test-utils'
import { ElMessageBox } from 'element-plus'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { Department, DepartmentTreeNode, PeopleManagementSnapshot, User } from '@/types/api'

vi.mock('@/api/departments', () => ({
  createDepartment: vi.fn(),
  deleteDepartment: vi.fn(),
  listDepartments: vi.fn(),
  listDepartmentTree: vi.fn(),
  updateDepartment: vi.fn(),
}))

vi.mock('@/api/people-management', () => ({
  getPeopleManagement: vi.fn(),
}))

vi.mock('@/api/users', () => ({
  listUsers: vi.fn(),
}))

import {
  createDepartment,
  deleteDepartment,
  listDepartments,
  listDepartmentTree,
  updateDepartment,
} from '@/api/departments'
import { getPeopleManagement } from '@/api/people-management'
import { listUsers } from '@/api/users'
import DepartmentsView from '@/views/DepartmentsView.vue'

type DepartmentsViewSetupState = {
  form: {
    name: string
    code: string
    parent_id: string
    manager_id: string
    sort_order: number
    is_active: boolean
  }
  handleSubmit: () => Promise<void>
  handleDelete: () => Promise<void>
  selectDepartment: (departmentId: string) => void
  openCreateRootDialog: () => void
}

const mockDepartments: Department[] = [
  {
    id: 'dept-root',
    name: '总部',
    code: 'root',
    parent_id: null,
    manager_id: null,
    sort_order: 0,
    is_active: true,
    created_at: '2026-04-01T00:00:00Z',
    updated_at: '2026-04-01T00:00:00Z',
  },
  {
    id: 'dept-marketing',
    name: '市场部',
    code: 'marketing',
    parent_id: 'dept-root',
    manager_id: 'user-1',
    sort_order: 10,
    is_active: true,
    created_at: '2026-04-02T00:00:00Z',
    updated_at: '2026-04-02T00:00:00Z',
  },
]

const mockTree: DepartmentTreeNode[] = [
  {
    ...mockDepartments[0],
    children: [
      {
        id: 'dept-marketing',
        name: '市场部',
        code: 'marketing',
        parent_id: 'dept-root',
        manager_id: 'user-1',
        sort_order: 10,
        is_active: true,
        children: [],
      },
    ],
  },
]

const mockUsers: User[] = [
  {
    id: 'user-1',
    email: 'manager@example.com',
    role: 'employee',
    status: 'active',
    last_login_at: null,
    created_at: '2026-04-01T00:00:00Z',
    updated_at: '2026-04-01T00:00:00Z',
  },
]

const mockPeopleSnapshot: PeopleManagementSnapshot = {
  summary: {
    total_people: 1,
    profiled_people: 1,
    unprofiled_people: 0,
    inactive_people: 0,
  },
  people: [
    {
      user_id: 'user-1',
      email: 'manager@example.com',
      role: 'employee',
      status: 'active',
      last_login_at: null,
      has_profile: true,
      profile_completion_state: 'complete',
      employee_no: 'EMP-001',
      real_name: '部门负责人',
      department_id: 'dept-marketing',
      department_name: '市场部',
      job_title: '经理',
      hire_date: '2025-01-01',
      updated_at: '2025-01-01T00:00:00Z',
    },
  ],
}

describe('Departments view', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(listDepartments).mockResolvedValue(mockDepartments)
    vi.mocked(listDepartmentTree).mockResolvedValue(mockTree)
    vi.mocked(listUsers).mockResolvedValue(mockUsers)
    vi.mocked(getPeopleManagement).mockResolvedValue(mockPeopleSnapshot)
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as never)
  })

  it('renders tree and detail panels and updates an existing department', async () => {
    vi.mocked(updateDepartment).mockResolvedValue({
      ...mockDepartments[1]!,
      name: '品牌市场部',
      manager_id: null,
    })

    const wrapper = mount(DepartmentsView, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()

    expect(wrapper.find('[data-testid="departments-tree"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="departments-detail-panel"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('市场部')

    const setupState = wrapper.vm.$.setupState as unknown as DepartmentsViewSetupState
    setupState.selectDepartment('dept-marketing')
    setupState.form.name = '品牌市场部'
    setupState.form.manager_id = ''

    await setupState.handleSubmit()
    await flushPromises()

    expect(updateDepartment).toHaveBeenCalledWith('dept-marketing', {
      name: '品牌市场部',
      code: 'marketing',
      parent_id: 'dept-root',
      manager_id: null,
      sort_order: 10,
      is_active: true,
    })
  })

  it('shows create form when clicking 新建根部门', async () => {
    const wrapper = mount(DepartmentsView, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()

    expect(wrapper.find('[data-testid="departments-form-submit"]').text()).toContain('保存部门')

    await wrapper.find('[data-testid="departments-create-root"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="departments-form-submit"]').text()).toContain('创建部门')
    expect(wrapper.text()).toContain('新建根部门')
  })

  it('creates and deletes a non-root department', async () => {
    vi.mocked(createDepartment).mockResolvedValue(mockDepartments[1]!)

    const wrapper = mount(DepartmentsView, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()

    const setupState = wrapper.vm.$.setupState as unknown as DepartmentsViewSetupState
    setupState.openCreateRootDialog()
    setupState.form.name = '运营部'
    setupState.form.code = 'operations'
    setupState.form.parent_id = 'dept-root'
    setupState.form.manager_id = 'user-1'
    setupState.form.sort_order = 20

    await setupState.handleSubmit()
    await flushPromises()

    expect(createDepartment).toHaveBeenCalledWith({
      name: '运营部',
      code: 'operations',
      parent_id: 'dept-root',
      manager_id: 'user-1',
      sort_order: 20,
    })

    setupState.selectDepartment('dept-marketing')
    await setupState.handleDelete()
    await flushPromises()

    expect(deleteDepartment).toHaveBeenCalledWith('dept-marketing')
  })
})
