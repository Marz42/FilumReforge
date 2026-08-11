import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { describe, expect, it, vi } from 'vitest'

import TaskDetailActivityTimeline from '@/components/task-detail/TaskDetailActivityTimeline.vue'
import type { Attachment, TaskActivityEntry, TaskLog } from '@/types/api'

function attachmentFixture(): Attachment {
  return {
    id: 'attachment-1',
    original_filename: '评审说明.pdf',
    mime_type: 'application/pdf',
    size_bytes: 128,
    checksum_sha256: 'checksum',
    uploader_id: 'user-1',
    visibility: 'private',
    status: 'uploaded',
    deleted_at: null,
    created_at: '2026-08-12T00:00:00Z',
    download_url: null,
  }
}

function logEntry(
  actionType: TaskLog['action_type'],
  detail: Record<string, unknown> = {},
  overrides: Partial<TaskLog> = {},
): TaskActivityEntry {
  return {
    entry_type: 'log',
    created_at: overrides.created_at ?? '2026-08-12T00:00:00Z',
    comment: null,
    log: {
      id: overrides.id ?? `log-${actionType}`,
      task_id: 'task-1',
      operator_id: 'user-1',
      operator_label: null,
      action_type: actionType,
      from_status: null,
      to_status: null,
      detail,
      created_at: overrides.created_at ?? '2026-08-12T00:00:00Z',
      ...overrides,
    },
  }
}

function mountTimeline(entries: TaskActivityEntry[], resolveUserLabel = vi.fn(() => '测试用户')) {
  const wrapper = mount(TaskDetailActivityTimeline, {
    props: {
      entries,
      resolveUserLabel,
    },
    global: {
      plugins: [ElementPlus],
      stubs: {
        AttachmentActions: {
          props: ['attachment'],
          template: '<span data-testid="attachment-actions-stub">附件操作</span>',
        },
      },
    },
  })
  return { resolveUserLabel, wrapper }
}

describe('TaskDetailActivityTimeline', () => {
  it('renders the existing empty state when there are no activities', () => {
    const { wrapper } = mountTimeline([])

    expect(wrapper.text()).toContain('暂无活动记录')
    expect(wrapper.find('[data-testid="task-detail-activity-timeline"]').exists()).toBe(true)
  })

  it('keeps comment order, internal marker and attachment actions', () => {
    const entries: TaskActivityEntry[] = [
      {
        entry_type: 'comment',
        created_at: '2026-08-12T01:00:00Z',
        comment: {
          id: 'comment-1',
          task_id: 'task-1',
          user_id: 'user-1',
          author_label: '负责人 A',
          content: '第一条内部说明',
          content_format: 'markdown',
          is_internal: true,
          created_at: '2026-08-12T01:00:00Z',
          updated_at: '2026-08-12T01:00:00Z',
          attachments: [attachmentFixture()],
        },
        log: null,
      },
      {
        entry_type: 'comment',
        created_at: '2026-08-12T00:30:00Z',
        comment: {
          id: 'comment-2',
          task_id: 'task-1',
          user_id: 'user-2',
          author_label: null,
          content: '第二条普通说明',
          content_format: 'markdown',
          is_internal: false,
          created_at: '2026-08-12T00:30:00Z',
          updated_at: '2026-08-12T00:30:00Z',
          attachments: [],
        },
        log: null,
      },
    ]
    const resolveUserLabel = vi.fn((userId: string, preferred?: string | null) => (
      preferred ?? `用户 ${userId}`
    ))
    const { wrapper } = mountTimeline(entries, resolveUserLabel)
    const text = wrapper.text()

    expect(text.indexOf('第一条内部说明')).toBeLessThan(text.indexOf('第二条普通说明'))
    expect(text).toContain('负责人 A')
    expect(text).toContain('内部备注')
    expect(text).toContain('评审说明.pdf')
    expect(wrapper.find('[data-testid="attachment-actions-stub"]').exists()).toBe(true)
    expect(resolveUserLabel).toHaveBeenCalledWith('user-1', '负责人 A')
    expect(resolveUserLabel).toHaveBeenCalledWith('user-2', null)
  })

  it('preserves status and workflow action summaries', () => {
    const entries = [
      logEntry('status_changed', {}, { from_status: 'todo', to_status: 'doing' }),
      logEntry('commented', { action: 'submit_deliverable' }),
      logEntry('commented', { action: 'rejected', reason: '目标需要再明确' }),
      logEntry('commented', { action: 'approve_completion', quality_score: 4 }),
      logEntry('commented', { action: 'return_for_rework', comment: '附件命名不规范' }),
      logEntry('attachment_added', { filename: '交付物.docx' }),
    ]
    const { wrapper } = mountTimeline(entries)

    expect(wrapper.text()).toContain('状态从 待办 变更为 进行中')
    expect(wrapper.text()).toContain('提交了交付物，等待验收')
    expect(wrapper.text()).toContain('退回协商：目标需要再明确')
    expect(wrapper.text()).toContain('完成交付已通过验收，质量 4/5')
    expect(wrapper.text()).toContain('打回返工：附件命名不规范')
    expect(wrapper.text()).toContain('添加了附件：交付物.docx')
  })
})
