import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createRouter, createWebHistory } from 'vue-router'
import { describe, expect, it } from 'vitest'

import NotificationsSection from '@/components/settings/NotificationsSection.vue'
import ProfileSection from '@/components/settings/ProfileSection.vue'
import SecuritySection from '@/components/settings/SecuritySection.vue'
import SettingsLayout from '@/components/settings/SettingsLayout.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/settings',
      component: SettingsLayout,
      children: [
        { path: 'profile', name: 'settings-profile', component: ProfileSection },
        { path: 'security', name: 'settings-security', component: SecuritySection },
        { path: 'notifications', name: 'settings-notifications', component: NotificationsSection },
      ],
    },
  ],
})

describe('Settings layout', () => {
  it('renders navigation and notifications section content', async () => {
    await router.push('/settings/notifications')

    const wrapper = mount(SettingsLayout, {
      global: {
        plugins: [ElementPlus, router],
        stubs: {
          PushSubscriptionCard: true,
        },
      },
    })

    expect(wrapper.find('[data-testid="settings-layout"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('个人资料')
    expect(wrapper.text()).toContain('安全与密码')
    expect(wrapper.text()).toContain('通知偏好')
    expect(wrapper.text()).toContain('浏览器推送')
  })
})
