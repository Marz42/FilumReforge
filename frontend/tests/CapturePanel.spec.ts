import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { submitTaskTopicCapture } from '@/api/workflow-graph'
import CapturePanel from '@/components/workflow/CapturePanel.vue'
import type { Task, WorkflowGraphInstanceDetail } from '@/types/api'

vi.mock('@/api/workflow-graph', () => ({
  listDepartmentPoolMemberOptions: vi.fn().mockResolvedValue([]),
  listManagedDepartmentMemberOptions: vi.fn().mockResolvedValue([]),
  submitTaskTopicCapture: vi.fn(),
}))

const task = {
  id: 'task-1',
  title: '采集任务',
  extra_metadata: { template_node_key: 'N1_PROPOSE' },
} as Task

function graphInstance(captureClosed: boolean): WorkflowGraphInstanceDetail {
  return {
    id: 'instance-1',
    template_id: 'template-1',
    context: {
      capture_closed: captureClosed,
      schema_snapshot: {
        nodes: {
          N1_PROPOSE: {
            capture_schema: {
              min_rows: 1,
              max_rows: 2,
              columns: [{ key: 'title', label: '标题', type: 'text', required: true }],
            },
          },
        },
      },
    },
  } as WorkflowGraphInstanceDetail
}

describe('CapturePanel', () => {
  beforeEach(() => vi.clearAllMocks())

  it('disables submission when capture has been closed', async () => {
    const wrapper = mount(CapturePanel, {
      props: { task, graphInstance: graphInstance(true) },
      global: { plugins: [ElementPlus] },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('采集已结束，由管理员提前关闭')
    expect(wrapper.get('[data-testid="capture-submit"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-testid="capture-submit"]').text()).toContain('采集已结束')
  })

  it('submits normalized capture rows and emits submitted', async () => {
    vi.mocked(submitTaskTopicCapture).mockResolvedValue({} as never)
    const wrapper = mount(CapturePanel, {
      props: { task, graphInstance: graphInstance(false) },
      global: { plugins: [ElementPlus] },
    })
    await flushPromises()
    const state = wrapper.vm.$.setupState as {
      rows: Array<Record<string, string>>
      handleSubmit: () => Promise<void>
    }
    state.rows[0].title = '  选题 A  '

    await state.handleSubmit()

    expect(submitTaskTopicCapture).toHaveBeenCalledWith('task-1', [{ title: '选题 A' }])
    expect(wrapper.emitted('submitted')).toHaveLength(1)
  })
})
