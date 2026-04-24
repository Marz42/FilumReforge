import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { describe, expect, it } from 'vitest'

import SettingsView from '@/views/SettingsView.vue'

describe('Settings view', () => {
  it('renders the push settings entry', () => {
    const wrapper = mount(SettingsView, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          PushSubscriptionCard: true,
        },
      },
    })

    expect(wrapper.text()).toContain('设置')
    expect(wrapper.text()).toContain('浏览器推送')
    expect(wrapper.text()).toContain('多个浏览器或设备可分别订阅')
  })
})