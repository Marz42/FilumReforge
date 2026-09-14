import ElementPlus from 'element-plus'
import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import RecordFieldsEditor from '@/components/common/RecordFieldsEditor.vue'

describe('RecordFieldsEditor', () => {
  it('keeps unknown keys and applies advanced JSON without dropping them', async () => {
    const wrapper = mount(RecordFieldsEditor, {
      props: {
        modelValue: { skills: ['python'], salary: 12 },
        definitions: [
          {
            field_key: 'salary',
            label: '薪资',
            field_type: 'number',
            storage_target: 'custom',
            is_active: true,
          },
        ],
        storageTarget: 'custom',
      },
      global: {
        plugins: [ElementPlus],
      },
    })

    expect(wrapper.text()).toContain('薪资')
    expect(wrapper.find('input[disabled]').element).toHaveProperty('value', 'skills')

    await wrapper.find('[data-testid="record-fields-advanced-toggle"]').trigger('click')
    await wrapper.find('[data-testid="record-fields-advanced-json"]').setValue('{"skills":["qa"],"salary":20}')
    await wrapper.find('[data-testid="record-fields-advanced-apply"]').trigger('click')
    await flushPromises()

    expect(wrapper.emitted('update:modelValue')?.at(-1)?.[0]).toEqual({
      skills: ['qa'],
      salary: 20,
    })
  })
})
