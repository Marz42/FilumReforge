import { createMemoryHistory, createRouter } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus, { ElMessageBox } from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type {
  Department,
  PeopleManagementDetail,
  PeopleManagementSnapshot,
  Position,
  User,
} from '@/types/api'

vi.mock('@/api/people-management', () => ({
  getPeopleManagement: vi.fn(),
  getPeopleManagementDetail: vi.fn(),
}))

vi.mock('@/api/departments', () => ({
  listDepartments: vi.fn(),
}))

vi.mock('@/api/auth', () => ({
  createInvitation: vi.fn(),
}))

vi.mock('@/api/profiles', () => ({
  createDelegation: vi.fn(),
  createPosition: vi.fn(),
  createProfile: vi.fn(),
  createProfileEvent: vi.fn(),
  createProfilePosition: vi.fn(),
  createProfileReportingLine: vi.fn(),
  listPositions: vi.fn(),
  updateDelegation: vi.fn(),
  updateProfile: vi.fn(),
}))

vi.mock('@/api/users', () => ({
  createUser: vi.fn(),
  deleteUser: vi.fn(),
  updateUser: vi.fn(),
}))

import { listDepartments } from '@/api/departments'
import { createInvitation } from '@/api/auth'
import { getPeopleManagement, getPeopleManagementDetail } from '@/api/people-management'
import {
  createProfile,
  listPositions,
  updateProfile,
} from '@/api/profiles'
import { createUser, deleteUser, updateUser } from '@/api/users'
import PeopleManagementView from '@/views/PeopleManagementView.vue'

type PeopleManagementViewSetupState = {
  accountForm: {
    email: string
    password: string
    role: User['role']
    status: User['status']
  }
  createProfileForm: {
    user_id: string
    employee_no: string
    real_name: string
    department_id: string
    job_title: string
    phone: string
    hire_date: string
    custom_fields_text: string
  }
  handleSaveAccount: () => Promise<void>
  handleDeleteUser: () => Promise<void>
  handleCreateProfile: () => Promise<void>
  handleCreateUser: () => Promise<void>
}

const mockDepartment: Department = {
  id: 'dept-1',
  name: '研发部',
  code: 'engineering',
  parent_id: null,
  manager_id: 'user-1',
  sort_order: 1,
  is_active: true,
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
}

const mockPosition: Position = {
  id: 'position-1',
  code: 'backend-engineer',
  name: '后端工程师',
  level: 'P5',
  extra_metadata: {},
  is_active: true,
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
}

const workspaceSnapshot: PeopleManagementSnapshot = {
  summary: {
    total_people: 2,
    profiled_people: 1,
    unprofiled_people: 1,
    inactive_people: 0,
  },
  people: [
    {
      user_id: 'user-1',
      email: 'engineer@example.com',
      role: 'employee',
      status: 'active',
      last_login_at: null,
      has_profile: true,
      profile_completion_state: 'complete',
      employee_no: 'EMP-001',
      real_name: '研发工程师',
      department_id: 'dept-1',
      department_name: '研发部',
      job_title: '后端工程师',
      hire_date: '2025-01-01',
      updated_at: '2025-01-01T00:00:00Z',
    },
    {
      user_id: 'user-2',
      email: 'pending@example.com',
      role: 'employee',
      status: 'active',
      last_login_at: null,
      has_profile: false,
      profile_completion_state: 'missing_profile',
      employee_no: null,
      real_name: null,
      department_id: null,
      department_name: null,
      job_title: null,
      hire_date: null,
      updated_at: '2025-01-02T00:00:00Z',
    },
  ],
}

const profiledDetail: PeopleManagementDetail = {
  summary: workspaceSnapshot.people[0]!,
  account: {
    id: 'user-1',
    email: 'engineer@example.com',
    role: 'employee',
    status: 'active',
    invitation_accepted_at: '2025-01-01T00:00:00Z',
    last_login_at: null,
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
  },
  profile: {
    user_id: 'user-1',
    user_email: 'engineer@example.com',
    user_status: 'active',
    employee_no: 'EMP-001',
    real_name: '研发工程师',
    department_id: 'dept-1',
    job_title: '后端工程师',
    phone: '13800000000',
    hire_date: '2025-01-01',
    custom_fields: { skills: ['python'] },
    visible_fields: [
      {
        field_key: 'employee_no',
        label: '员工编号',
        field_type: 'string',
        storage_target: 'core',
        is_sensitive: false,
        value: 'EMP-001',
        can_view: true,
        can_edit: true,
      },
    ],
    positions: [],
    reporting_lines: [],
    employment_events: [],
    delegations: [],
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
  },
  actions: {
    can_edit_user: true,
    can_delete_user: false,
    can_create_profile: false,
    can_edit_profile: true,
    can_manage_relations: true,
    can_manage_lifecycle: true,
    can_manage_delegations: true,
  },
  primary_manager_user_id: null,
  primary_manager_label: null,
  latest_employment_event: null,
}

const unprofiledDetail: PeopleManagementDetail = {
  summary: workspaceSnapshot.people[1]!,
  account: {
    id: 'user-2',
    email: 'pending@example.com',
    role: 'employee',
    status: 'active',
    last_login_at: null,
    created_at: '2025-01-02T00:00:00Z',
    updated_at: '2025-01-02T00:00:00Z',
  },
  profile: null,
  actions: {
    can_edit_user: true,
    can_delete_user: true,
    can_create_profile: true,
    can_edit_profile: false,
    can_manage_relations: false,
    can_manage_lifecycle: false,
    can_manage_delegations: false,
  },
  primary_manager_user_id: null,
  primary_manager_label: null,
  latest_employment_event: null,
}

describe('PeopleManagementView', () => {
  beforeEach(() => {
    window.localStorage.clear()
    setActivePinia(createPinia())
    vi.clearAllMocks()

    vi.mocked(getPeopleManagement).mockResolvedValue(workspaceSnapshot)
    vi.mocked(getPeopleManagementDetail).mockImplementation(async (userId: string) => {
      return userId === 'user-2' ? unprofiledDetail : profiledDetail
    })
    vi.mocked(listDepartments).mockResolvedValue([mockDepartment])
    vi.mocked(listPositions).mockResolvedValue([mockPosition])
    vi.mocked(updateUser).mockResolvedValue(profiledDetail.account)
    vi.mocked(deleteUser).mockResolvedValue(undefined)
    vi.mocked(createUser).mockResolvedValue({
      id: 'user-3',
      email: 'new@example.com',
      role: 'employee',
      status: 'active',
      last_login_at: null,
      created_at: '2025-01-03T00:00:00Z',
      updated_at: '2025-01-03T00:00:00Z',
    })
    vi.mocked(createInvitation).mockResolvedValue({
      user: {
        id: 'user-4',
        email: 'invite@example.com',
        role: 'employee',
        status: 'inactive',
        last_login_at: null,
        created_at: '2025-01-04T00:00:00Z',
        updated_at: '2025-01-04T00:00:00Z',
      },
      invite_url: 'https://app.example.com/login?invite=test-token',
      expires_at: '2025-01-06T00:00:00Z',
    })
    vi.mocked(updateProfile).mockResolvedValue(profiledDetail.profile!)
    vi.mocked(createProfile).mockResolvedValue({
      ...profiledDetail.profile!,
      user_id: 'user-2',
      user_email: 'pending@example.com',
      real_name: '待建档员工',
    })
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as never)
  })

  async function mountView(initialPath = '/people?selected=user-1&detailTab=account') {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        {
          path: '/people',
          name: 'people',
          component: PeopleManagementView,
        },
      ],
    })
    await router.push(initialPath)
    await router.isReady()

    const wrapper = mount(PeopleManagementView, {
      global: {
        plugins: [ElementPlus, router],
      },
    })

    await flushPromises()
    await flushPromises()
    return { wrapper, router }
  }

  it('renders unified workspace and updates route when switching tabs', async () => {
    const { wrapper, router } = await mountView()

    expect(wrapper.text()).toContain('档案管理 & 用户管理')
    expect(wrapper.text()).toContain('研发工程师')
    expect(wrapper.text()).toContain('后端工程师')
    expect(wrapper.text()).toContain('已完成注册（非撤销）')

    const permissionsTab = wrapper
      .findAll('.el-tabs__item')
      .find((item) => item.text().includes('权限视图'))
    expect(permissionsTab).toBeTruthy()
    await permissionsTab?.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.query.detailTab).toBe('permissions')

    const setupState = wrapper.vm.$.setupState as unknown as PeopleManagementViewSetupState
    setupState.accountForm.password = 'ResetPass123!'
    await setupState.handleSaveAccount()
    await flushPromises()

    expect(updateUser).toHaveBeenCalledWith('user-1', {
      email: 'engineer@example.com',
      password: 'ResetPass123!',
      role: 'employee',
      status: 'active',
    })
  })

  it('creates a profile for an unprofiled account from the unified workspace', async () => {
    const { wrapper } = await mountView('/people?selected=user-2&detailTab=profile')

    expect(wrapper.text()).toContain('当前账号尚未建立档案')
    const buildProfileButton = wrapper
      .findAll('button')
      .find((button) => button.text().includes('补建档案'))
    expect(buildProfileButton).toBeTruthy()
    await buildProfileButton?.trigger('click')
    await flushPromises()

    const setupState = wrapper.vm.$.setupState as unknown as PeopleManagementViewSetupState
    setupState.createProfileForm.user_id = 'user-2'
    setupState.createProfileForm.employee_no = 'EMP-002'
    setupState.createProfileForm.real_name = '待建档员工'
    setupState.createProfileForm.department_id = 'dept-1'
    setupState.createProfileForm.job_title = '测试工程师'
    setupState.createProfileForm.custom_fields_text = '{\n  "skills": ["qa"]\n}'

    await setupState.handleCreateProfile()
    await flushPromises()

    expect(createProfile).toHaveBeenCalledWith({
      user_id: 'user-2',
      employee_no: 'EMP-002',
      real_name: '待建档员工',
      department_id: 'dept-1',
      job_title: '测试工程师',
      phone: undefined,
      hire_date: undefined,
      custom_fields: {
        skills: ['qa'],
      },
    })
  })

  it('generates an invitation link from the account creation dialog', async () => {
    const { wrapper } = await mountView()

    const newUserButton = wrapper
      .findAll('button')
      .find((button) => button.text().includes('新建账号'))
    expect(newUserButton).toBeTruthy()
    await newUserButton?.trigger('click')
    await flushPromises()

    const setupState = wrapper.vm.$.setupState as unknown as PeopleManagementViewSetupState & {
      createUserMode: 'direct' | 'invite'
      createUserForm: {
        email: string
        password: string
        role: User['role']
        status: User['status']
      }
    }
    setupState.createUserMode = 'invite'
    setupState.createUserForm.email = 'invite@example.com'
    setupState.createUserForm.role = 'employee'

    await setupState.handleCreateUser()
    await flushPromises()

    expect(createInvitation).toHaveBeenCalledWith({
      email: 'invite@example.com',
      role: 'employee',
    })
    const inviteInput = wrapper.find('.people-management__invite-result input')
    expect(inviteInput.exists()).toBe(true)
    expect(inviteInput.element).toHaveProperty('value', 'https://app.example.com/login?invite=test-token')
  })

  it('allows deleting an unprofiled account from the account tab', async () => {
    const { wrapper } = await mountView('/people?selected=user-2&detailTab=account')

    expect(wrapper.text()).toContain('删除未建档账号')

    const setupState = wrapper.vm.$.setupState as unknown as PeopleManagementViewSetupState
    await setupState.handleDeleteUser()
    await flushPromises()

    expect(ElMessageBox.confirm).toHaveBeenCalled()
    expect(deleteUser).toHaveBeenCalledWith('user-2')
  })
})
