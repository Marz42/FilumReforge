import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type {
  Department,
  Position,
  Profile,
  ProfileFieldDefinition,
  User,
} from '@/types/api'

vi.mock('@/api/profiles', () => ({
  createDelegation: vi.fn(),
  createPosition: vi.fn(),
  createProfile: vi.fn(),
  createProfileEvent: vi.fn(),
  createProfilePosition: vi.fn(),
  createProfileReportingLine: vi.fn(),
  getProfile: vi.fn(),
  listPositions: vi.fn(),
  listProfileFieldDefinitions: vi.fn(),
  listProfiles: vi.fn(),
  updateDelegation: vi.fn(),
  updateProfile: vi.fn(),
}))

vi.mock('@/api/departments', () => ({
  listDepartments: vi.fn(),
}))

vi.mock('@/api/users', () => ({
  listUsers: vi.fn(),
}))

import { listDepartments } from '@/api/departments'
import {
  createDelegation,
  createPosition,
  createProfile,
  createProfileEvent,
  createProfilePosition,
  createProfileReportingLine,
  getProfile,
  listPositions,
  listProfileFieldDefinitions,
  listProfiles,
  updateDelegation,
  updateProfile,
} from '@/api/profiles'
import { listUsers } from '@/api/users'
import { useAuthStore } from '@/stores/auth'
import ProfilesView from '@/views/ProfilesView.vue'

const mockDepartment: Department = {
  id: 'dept-1',
  name: '运营部',
  code: 'operations',
  parent_id: null,
  manager_id: 'user-3',
  sort_order: 1,
  is_active: true,
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
}

const mockUsers: User[] = [
  {
    id: 'user-1',
    email: 'admin@example.com',
    role: 'admin',
    status: 'active',
    last_login_at: null,
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
  },
  {
    id: 'user-2',
    email: 'employee@example.com',
    role: 'employee',
    status: 'active',
    last_login_at: null,
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
  },
  {
    id: 'user-3',
    email: 'manager@example.com',
    role: 'employee',
    status: 'active',
    last_login_at: null,
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
  },
]

const mockPosition: Position = {
  id: 'position-1',
  code: 'ops-specialist',
  name: '运营专员',
  level: 'P4',
  extra_metadata: { track: 'ops' },
  is_active: true,
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
}

const mockFieldDefinition: ProfileFieldDefinition = {
  id: 'field-1',
  field_key: 'salary',
  label: '薪资',
  field_type: 'number',
  storage_target: 'custom',
  is_sensitive: true,
  config: {},
  is_active: true,
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
}

const mockProfileSummary: Profile = {
  user_id: 'user-2',
  user_email: 'employee@example.com',
  user_status: 'active',
  employee_no: 'EMP-001',
  real_name: '普通员工',
  department_id: 'dept-1',
  job_title: '运营专员',
  phone: '13800000000',
  hire_date: '2025-01-01',
  custom_fields: { hobby: '摄影' },
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
}

const mockProfileDetail: Profile = {
  ...mockProfileSummary,
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
    {
      field_key: 'performance',
      label: '绩效评估',
      field_type: 'text',
      storage_target: 'custom',
      is_sensitive: true,
      value: 'A',
      can_view: true,
      can_edit: true,
    },
  ],
  custom_fields: {
    hobby: '摄影',
    performance: 'A',
  },
  positions: [
    {
      id: 'assignment-1',
      user_id: 'user-2',
      position_id: 'position-1',
      department_id: 'dept-1',
      assignment_type: 'primary',
      is_primary: true,
      starts_at: '2025-01-01',
      ends_at: null,
      created_at: '2025-01-01T00:00:00Z',
      updated_at: '2025-01-01T00:00:00Z',
    },
  ],
  reporting_lines: [
    {
      id: 'line-1',
      user_id: 'user-2',
      manager_user_id: 'user-3',
      department_id: 'dept-1',
      line_type: 'solid',
      is_primary: true,
      starts_at: '2025-01-01',
      ends_at: null,
      created_at: '2025-01-01T00:00:00Z',
      updated_at: '2025-01-01T00:00:00Z',
    },
  ],
  employment_events: [
    {
      id: 'event-1',
      user_id: 'user-2',
      event_type: 'promotion',
      effective_date: '2025-02-01',
      title: '晋升为运营专员',
      summary: '升级主岗位',
      payload: {},
      created_by: 'user-1',
      created_at: '2025-02-01T00:00:00Z',
    },
  ],
  delegations: [
    {
      id: 'delegation-1',
      delegator_user_id: 'user-2',
      delegate_user_id: 'user-3',
      scope_type: 'data_access',
      scope_department_id: 'dept-1',
      scope_filters: {},
      status: 'active',
      starts_at: '2025-02-01T00:00:00Z',
      ends_at: '2025-02-08T00:00:00Z',
      created_by: 'user-2',
      created_at: '2025-02-01T00:00:00Z',
      updated_at: '2025-02-01T00:00:00Z',
    },
  ],
}

describe('Profiles view', () => {
  beforeEach(() => {
    window.localStorage.clear()
    setActivePinia(createPinia())
    vi.clearAllMocks()

    const authStore = useAuthStore()
    authStore.initialized = true
    authStore.accessToken = 'test-access-token'
    authStore.refreshToken = 'test-refresh-token'
    authStore.user = mockUsers[0] ?? null

    vi.mocked(listProfiles).mockResolvedValue([mockProfileSummary])
    vi.mocked(getProfile).mockResolvedValue(mockProfileDetail)
    vi.mocked(listDepartments).mockResolvedValue([mockDepartment])
    vi.mocked(listUsers).mockResolvedValue(mockUsers)
    vi.mocked(listPositions).mockResolvedValue([mockPosition])
    vi.mocked(listProfileFieldDefinitions).mockResolvedValue([mockFieldDefinition])
    vi.mocked(createProfile).mockResolvedValue(mockProfileDetail)
    vi.mocked(updateProfile).mockResolvedValue(mockProfileDetail)
    vi.mocked(createPosition).mockResolvedValue(mockPosition)
    vi.mocked(createProfilePosition).mockResolvedValue(mockProfileDetail.positions[0]!)
    vi.mocked(createProfileReportingLine).mockResolvedValue(mockProfileDetail.reporting_lines[0]!)
    vi.mocked(createProfileEvent).mockResolvedValue(mockProfileDetail.employment_events[0]!)
    vi.mocked(createDelegation).mockResolvedValue(mockProfileDetail.delegations[0]!)
    vi.mocked(updateDelegation).mockResolvedValue({
      ...mockProfileDetail.delegations[0]!,
      status: 'revoked',
    })
  })

  it('renders phase3 profile governance tabs and detail sections', async () => {
    const wrapper = mount(ProfilesView, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()
    await flushPromises()

    expect(wrapper.text()).toContain('Phase 3 / HR Governance & Org Modeling')
    expect(wrapper.text()).toContain('任职关系')
    expect(wrapper.text()).toContain('生命周期事件')
    expect(wrapper.text()).toContain('敏感字段')
    expect(wrapper.text()).toContain('代理授权')
    expect(getProfile).toHaveBeenCalledWith('user-2')
  })

  it('revokes delegation from delegation tab', async () => {
    const wrapper = mount(ProfilesView, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()
    await flushPromises()

    const delegationTab = wrapper
      .findAll('.el-tabs__item')
      .find((item) => item.text().includes('代理授权'))
    expect(delegationTab).toBeTruthy()
    await delegationTab?.trigger('click')
    await flushPromises()

    const revokeButton = wrapper
      .findAll('button')
      .find((button) => button.text().includes('撤销'))
    expect(revokeButton).toBeTruthy()
    await revokeButton?.trigger('click')
    await flushPromises()

    expect(updateDelegation).toHaveBeenCalledWith('delegation-1', {
      status: 'revoked',
    })
  })
})
