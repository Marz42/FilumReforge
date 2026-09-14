import { describe, expect, it } from 'vitest'
import { defineComponent, h } from 'vue'

import { mountApp } from './helpers/mountApp'

describe('mountApp helper', () => {
  it('mounts with pinia, router, and element-plus', async () => {
    const Stub = defineComponent({
      name: 'MountStub',
      setup() {
        return () => h('div', { 'data-testid': 'mount-stub' }, 'ok')
      },
    })
    const { wrapper } = await mountApp(Stub)
    expect(wrapper.get('[data-testid="mount-stub"]').text()).toBe('ok')
  })
})
