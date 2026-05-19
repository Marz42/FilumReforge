import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { defineComponent } from 'vue'
import { beforeEach, describe, expect, it } from 'vitest'
import ElementPlus from 'element-plus'

import AppShell from '@/components/AppShell.vue'
import router from '@/router'
import { useAuthStore } from '@/stores/auth'

const RoutedViewStub = defineComponent({
  name: 'RoutedViewStub',
  template: '<div class="router-view-stub">Route Content</div>',
})

const RouterViewStub = defineComponent({
  name: 'RouterViewStub',
  setup(_, { slots }) {
    return () => slots.default?.({ Component: RoutedViewStub })
  },
})

const AppHeaderStub = defineComponent({
  name: 'AppHeaderStub',
  props: {
    isMobileViewport: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['openMobileNav', 'logout'],
  template: `
    <div class="app-header-stub">
      <button
        v-if="isMobileViewport"
        data-testid="mobile-nav-trigger"
        type="button"
        @click="$emit('openMobileNav')"
      >
        menu
      </button>
    </div>
  `,
})
const DrawerStub = defineComponent({
  name: 'ElDrawer',
  props: {
    modelValue: {
      type: Boolean,
      default: false,
    },
  },
  template: '<div v-if="modelValue" class="drawer-stub"><slot /></div>',
})

describe('App shell', () => {
  let pinia: ReturnType<typeof createPinia>

  beforeEach(() => {
    window.localStorage.clear()
    Object.defineProperty(window, 'innerWidth', {
      configurable: true,
      writable: true,
      value: 1280,
    })
    pinia = createPinia()
    setActivePinia(pinia)
  })

  async function seedUser(role: 'admin' | 'hr' | 'employee'): Promise<void> {
    const authStore = useAuthStore()
    authStore.initialized = true
    authStore.accessToken = 'test-access-token'
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
          AppHeader: AppHeaderStub,
          RouterView: RouterViewStub,
          ElDrawer: DrawerStub,
          teleport: true,
        },
      },
    })

    expect(wrapper.text()).toContain('Project Filum')
    expect(wrapper.text()).toContain('统一协同工作台')
    expect(wrapper.text()).toContain('通用模块')
    expect(wrapper.text()).toContain('特殊模块')
    expect(wrapper.text()).toContain('总览')
    expect(wrapper.text()).toContain('任务中心')
    expect(wrapper.text()).toContain('知识库')
    expect(wrapper.text()).toContain('汇报中心')
    expect(wrapper.text()).not.toContain('消息中心')
    expect(wrapper.text()).toContain('设置')
    expect(wrapper.text()).toContain('人员管理')
    expect(wrapper.text()).toContain('部门管理')
    expect(wrapper.findAll('.el-menu-item .el-icon').length).toBeGreaterThan(0)
    expect(wrapper.find('.router-view-stub').exists()).toBe(true)
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
          AppHeader: AppHeaderStub,
          RouterView: RouterViewStub,
          ElDrawer: DrawerStub,
          teleport: true,
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
          AppHeader: AppHeaderStub,
          RouterView: RouterViewStub,
          ElDrawer: DrawerStub,
          teleport: true,
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

  it('uses a drawer trigger for narrow screens', async () => {
    Object.defineProperty(window, 'innerWidth', {
      configurable: true,
      writable: true,
      value: 720,
    })
    window.dispatchEvent(new Event('resize'))

    await seedUser('admin')

    const wrapper = mount(AppShell, {
      attachTo: document.body,
      global: {
        plugins: [pinia, router, ElementPlus],
        stubs: {
          CommandBar: true,
          AppHeader: AppHeaderStub,
          RouterView: RouterViewStub,
          ElDrawer: DrawerStub,
          teleport: true,
        },
      },
    })

    await nextTick()

    expect(wrapper.find('[data-testid="mobile-nav-trigger"]').exists()).toBe(true)

    await wrapper.get('[data-testid="mobile-nav-trigger"]').trigger('click')
    await nextTick()

    expect(wrapper.find('.drawer-stub').exists()).toBe(true)
    expect(wrapper.text()).toContain('通用模块')
    expect(wrapper.text()).toContain('特殊模块')

    wrapper.unmount()
  })
})
