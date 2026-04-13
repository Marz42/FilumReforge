import { createPinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it } from 'vitest'
import ElementPlus from 'element-plus'

import App from '@/App.vue'
import router from '@/router'

describe('App shell', () => {
  beforeEach(async () => {
    router.push('/')
    await router.isReady()
  })

  it('renders the phase A dashboard shell', () => {
    const wrapper = mount(App, {
      global: {
        plugins: [createPinia(), router, ElementPlus],
      },
    })

    expect(wrapper.text()).toContain('Project Filum')
    expect(wrapper.text()).toContain('Phase A')
    expect(wrapper.text()).toContain('工程骨架初始化中')
  })
})
