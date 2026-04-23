import { flushPromises, mount } from '@vue/test-utils'
import { ElMessageBox } from 'element-plus'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { Department, DepartmentTreeNode, User } from '@/types/api'

vi.mock('@/api/departments', () => ({
  createDepartment: vi.fn(),
  deleteDepartment: vi.fn(),
  listDepartments: vi.fn(),
  listDepartmentTree: vi.fn(),
  updateDepartment: vi.fn(),
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
  handleDelete: (department: Department) => Promise<void>
  openCreateDialog: () => void
  openEditDialog: (department: Department) => void
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

describe('Departments view', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(listDepartments).mockResolvedValue(mockDepartments)
    vi.mocked(listDepartmentTree).mockResolvedValue(mockTree)
    vi.mocked(listUsers).mockResolvedValue(mockUsers)
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as never)
  })

  it('updates an existing department and hides delete for the root node', async () => {
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

    expect(wrapper.text()).toContain('公司')
    expect(wrapper.text()).toContain('市场部')
    expect(wrapper.findAll('button').filter((node) => node.text().includes('删除'))).toHaveLength(1)

    const setupState = wrapper.vm.$.setupState as unknown as DepartmentsViewSetupState
    setupState.openEditDialog(mockDepartments[1]!)
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

  it('creates and deletes a non-root department', async () => {
    vi.mocked(createDepartment).mockResolvedValue(mockDepartments[1]!)

    const wrapper = mount(DepartmentsView, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()

    const setupState = wrapper.vm.$.setupState as unknown as DepartmentsViewSetupState
    setupState.openCreateDialog()
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

    await setupState.handleDelete(mockDepartments[1]!)
    await flushPromises()

    expect(deleteDepartment).toHaveBeenCalledWith('dept-marketing')
  })
})