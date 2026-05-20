import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import PeopleAnchorNav, { type PeopleAnchorItem } from '@/components/people/PeopleAnchorNav.vue'

const items: PeopleAnchorItem[] = [
  { id: 'account', label: '账号信息', testId: 'people-anchor-account' },
  { id: 'profile', label: '档案信息', testId: 'people-anchor-profile' },
]

describe('PeopleAnchorNav', () => {
  it('emits navigate events when an anchor is clicked', async () => {
    const wrapper = mount(PeopleAnchorNav, {
      props: {
        modelValue: 'account',
        items,
      },
    })

    await wrapper.find('[data-testid="people-anchor-profile"]').trigger('click')

    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['profile'])
    expect(wrapper.emitted('navigate')?.[0]).toEqual(['profile'])
  })

  it('highlights the active anchor', () => {
    const wrapper = mount(PeopleAnchorNav, {
      props: {
        modelValue: 'profile',
        items,
      },
    })

    expect(
      wrapper.find('[data-testid="people-anchor-profile"]').classes(),
    ).toContain('people-anchor-nav__item--active')
    expect(
      wrapper.find('[data-testid="people-anchor-account"]').classes(),
    ).not.toContain('people-anchor-nav__item--active')
  })
})
