import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it } from 'vitest'
import ElementPlus from 'element-plus'

import AppShell from '@/components/AppShell.vue'
import router from '@/router'
import { useAuthStore } from '@/stores/auth'

describe('App shell', () => {
  let pinia: ReturnType<typeof createPinia>

  beforeEach(() => {
    window.localStorage.clear()
    pinia = createPinia()
    setActivePinia(pinia)
  })

  async function seedUser(role: 'admin' | 'hr' | 'employee'): Promise<void> {
    const authStore = useAuthStore()
    authStore.initialized = true
    authStore.accessToken = 'test-access-token'
    authStore.refreshToken = 'test-refresh-token'
    authStore.user = {
      id: 'user-1',
      email: 'admin@example.com',
      role,
      status: 'active',
      last_login_at: null,
      created_at: '2025-01-01T00:00:00Z',
      updated_at: '2025-01-01T00:00:00Z',
    }

    router.push('/overview')
    await router.isReady()
  }

  it('renders the grouped navigation for admin users', async () => {
    await seedUser('admin')

    const wrapper = mount(AppShell, {
      global: {
        plugins: [pinia, router, ElementPlus],
        stubs: {
          CommandBar: true,
          RouterView: true,
        },
      },
    })

    expect(wrapper.text()).toContain('Project Filum')
    expect(wrapper.text()).toContain('统一协同工作台')
    expect(wrapper.text()).toContain('人事、任务、汇报、消息与知识库统一入口')
    expect(wrapper.text()).toContain('通用模块')
    expect(wrapper.text()).toContain('特殊模块')
    expect(wrapper.text()).toContain('总览')
    expect(wrapper.text()).toContain('任务中心')
    expect(wrapper.text()).toContain('知识库')
    expect(wrapper.text()).toContain('汇报中心')
    expect(wrapper.text()).toContain('消息中心')
    expect(wrapper.text()).toContain('设置')
    expect(wrapper.text()).toContain('人员管理')
    expect(wrapper.text()).toContain('部门管理')
    expect(wrapper.text()).not.toContain('仪表盘')
    expect(wrapper.text()).not.toContain('模板中心')
    expect(wrapper.text()).not.toContain('审批中心')
    expect(wrapper.text()).not.toContain('Step 7')
    expect(wrapper.text()).not.toContain('当前重构收口')
  })

  it('hides admin-only modules from hr users', async () => {
    await seedUser('hr')

    const wrapper = mount(AppShell, {
      global: {
        plugins: [pinia, router, ElementPlus],
        stubs: {
          CommandBar: true,
          RouterView: true,
        },
      },
    })

    expect(wrapper.text()).toContain('人员管理')
    expect(wrapper.text()).not.toContain('部门管理')
  })

  it('shows only general modules for employees', async () => {
    await seedUser('employee')

    const wrapper = mount(AppShell, {
      global: {
        plugins: [pinia, router, ElementPlus],
        stubs: {
          CommandBar: true,
          RouterView: true,
        },
      },
    })

    expect(wrapper.text()).toContain('总览')
    expect(wrapper.text()).toContain('任务中心')
    expect(wrapper.text()).toContain('汇报中心')
    expect(wrapper.text()).toContain('设置')
    expect(wrapper.text()).not.toContain('特殊模块')
    expect(wrapper.text()).not.toContain('人员管理')
    expect(wrapper.text()).not.toContain('部门管理')
  })
})
