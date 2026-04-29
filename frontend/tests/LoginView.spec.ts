import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const route = { query: {} as Record<string, string> }

vi.mock('vue-router', () => ({
  useRoute: () => route,
  useRouter: () => ({ replace: vi.fn() }),
}))

vi.mock('@/api/auth', () => ({
  acceptInvitation: vi.fn(),
  bootstrapAdmin: vi.fn(),
  getBootstrapStatus: vi.fn(),
  getInvitationPreview: vi.fn(),
  getCurrentUser: vi.fn(),
  login: vi.fn(),
}))

import { getBootstrapStatus, getInvitationPreview } from '@/api/auth'
import LoginView from '@/views/LoginView.vue'

describe('Login view', () => {
  beforeEach(() => {
    window.localStorage.clear()
    route.query = {}
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('shows bootstrap entry when backend still requires admin initialization', async () => {
    vi.mocked(getBootstrapStatus).mockResolvedValue({ bootstrap_required: true })

    const wrapper = mount(LoginView, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('第一次进入系统时，请先初始化管理员账号')
    expect(wrapper.text()).toContain('初始化管理员')

    const inputs = wrapper.findAll('input')
    expect(inputs[0]?.element).toHaveProperty('value', '')
    expect(inputs[1]?.element).toHaveProperty('value', '')
  })

  it('hides bootstrap entry after backend reports initialization completed', async () => {
    vi.mocked(getBootstrapStatus).mockResolvedValue({ bootstrap_required: false })

    const wrapper = mount(LoginView, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()

    expect(wrapper.text()).not.toContain('第一次进入系统时，请先初始化管理员账号')
    expect(wrapper.text()).not.toContain('初始化管理员')
    expect(wrapper.text()).toContain('登录系统')
    expect(wrapper.text()).toContain('统一协同与人事工作台')
  })

  it('shows invitation registration when invite token is present', async () => {
    route.query = { invite: 'invite-token' }
    vi.mocked(getBootstrapStatus).mockResolvedValue({ bootstrap_required: false })
    vi.mocked(getInvitationPreview).mockResolvedValue({
      user_id: 'user-2',
      email: 'invitee@example.com',
      role: 'employee',
      expires_at: '2025-01-02T00:00:00Z',
    })

    const wrapper = mount(LoginView, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('邀请注册链接')
    expect(wrapper.text()).toContain('invitee@example.com')
    expect(wrapper.text()).toContain('完成注册')
  })
})