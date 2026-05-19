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

  it('shows bootstrap wizard when backend still requires admin initialization', async () => {
    vi.mocked(getBootstrapStatus).mockResolvedValue({ bootstrap_required: true })

    const wrapper = mount(LoginView, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()

    expect(wrapper.find('[data-testid="login-page"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="bootstrap-wizard"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="login-form"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('系统初始化')
    expect(wrapper.text()).toContain('管理员邮箱')
  })

  it('shows normal login when backend reports initialization completed', async () => {
    vi.mocked(getBootstrapStatus).mockResolvedValue({ bootstrap_required: false })

    const wrapper = mount(LoginView, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()

    expect(wrapper.find('[data-testid="login-form"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="bootstrap-wizard"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('登录系统')
    expect(wrapper.text()).toContain('本系统采用邀请制，请联系 HR 获取账号')
  })

  it('shows invite activation when invite token is present', async () => {
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

    expect(wrapper.find('[data-testid="login-invite-activate"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="login-form"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('欢迎加入，请设置密码')
    expect(wrapper.text()).toContain('invitee@example.com')
    expect(wrapper.text()).toContain('完成注册')
  })
})
