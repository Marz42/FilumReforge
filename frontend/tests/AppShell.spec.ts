import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it } from 'vitest'
import ElementPlus from 'element-plus'

import AppShell from '@/components/AppShell.vue'
import router from '@/router'
import { useAuthStore } from '@/stores/auth'

describe('App shell', () => {
  let pinia: ReturnType<typeof createPinia>

  beforeEach(async () => {
    window.localStorage.clear()
    pinia = createPinia()
    setActivePinia(pinia)

    const authStore = useAuthStore()
    authStore.initialized = true
    authStore.accessToken = 'test-access-token'
    authStore.refreshToken = 'test-refresh-token'
    authStore.user = {
      id: 'user-1',
      email: 'admin@example.com',
      role: 'admin',
      status: 'active',
      last_login_at: null,
      created_at: '2025-01-01T00:00:00Z',
      updated_at: '2025-01-01T00:00:00Z',
    }

    router.push('/dashboard')
    await router.isReady()
  })

  it('renders the phase 4 shell navigation', () => {
    const wrapper = mount(AppShell, {
      global: {
        plugins: [pinia, router, ElementPlus],
        stubs: {
          RouterView: true,
        },
      },
    })

    expect(wrapper.text()).toContain('Project Filum')
    expect(wrapper.text()).toContain('Phase 4')
    expect(wrapper.text()).toContain('部门管理')
    expect(wrapper.text()).toContain('任务中心')
    expect(wrapper.text()).toContain('模板中心')
    expect(wrapper.text()).toContain('审批中心')
    expect(wrapper.text()).toContain('消息中心')
  })
})
