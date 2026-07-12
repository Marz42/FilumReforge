import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { createTask } from '@/api/tasks'
import PublishTaskDialog from '@/components/task-center/PublishTaskDialog.vue'

vi.mock('@/api/attachments', () => ({ uploadAttachment: vi.fn() }))
vi.mock('@/api/tasks', () => ({ createTask: vi.fn() }))

const departments = [
  { id: 'dept-1', label: '内容部' },
  { id: 'dept-2', label: '市场部' },
]
const users = [
  { user_id: 'user-1', email: 'one@example.com', department_id: 'dept-1', label: '成员一' },
  { user_id: 'user-2', email: 'two@example.com', department_id: 'dept-2', label: '成员二' },
]

describe('PublishTaskDialog', () => {
  beforeEach(() => vi.clearAllMocks())

  function mountDialog() {
    return mount(PublishTaskDialog, {
      props: {
        modelValue: true,
        departmentOptions: departments,
        userOptions: users,
        'onUpdate:modelValue': vi.fn(),
      },
      global: { plugins: [ElementPlus] },
    })
  }

  it('filters assignees when the department changes', async () => {
    const wrapper = mountDialog()
    const state = wrapper.vm.$.setupState as {
      publishForm: { department_id: string; assignee_user_id: string }
      filteredPublishUserOptions: { user_id: string }[]
    }
    state.publishForm.assignee_user_id = 'user-2'
    state.publishForm.department_id = 'dept-1'
    await flushPromises()

    expect(state.filteredPublishUserOptions.map((user) => user.user_id)).toEqual(['user-1'])
    expect(state.publishForm.assignee_user_id).toBe('')
  })

  it('submits attachment and watcher ids with the task payload', async () => {
    vi.mocked(createTask).mockResolvedValue({} as never)
    const wrapper = mountDialog()
    const state = wrapper.vm.$.setupState as {
      publishForm: {
        title: string
        assignee_user_id: string
        department_id: string
        watcher_user_ids: string[]
      }
      publishDraftAttachments: { id: string; original_filename: string }[]
      handlePublishTask: () => Promise<void>
    }
    state.publishForm.title = '新任务'
    state.publishForm.assignee_user_id = 'user-1'
    state.publishForm.department_id = 'dept-1'
    state.publishForm.watcher_user_ids = ['user-2']
    state.publishDraftAttachments = [{ id: 'att-1', original_filename: 'brief.pdf' }]

    await state.handlePublishTask()

    expect(createTask).toHaveBeenCalledWith(
      expect.objectContaining({
        title: '新任务',
        assignee_id: 'user-1',
        department_id: 'dept-1',
        attachment_ids: ['att-1'],
        watcher_user_ids: ['user-2'],
      }),
    )
    expect(wrapper.emitted('created')).toHaveLength(1)
  })
})
