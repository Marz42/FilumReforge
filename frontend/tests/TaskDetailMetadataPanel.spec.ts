import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { describe, expect, it } from 'vitest'

import TaskDetailContextPanel from '@/components/task-detail/TaskDetailContextPanel.vue'
import TaskDetailMetadataPanel from '@/components/task-detail/TaskDetailMetadataPanel.vue'
import type { TaskDetailProfile } from '@/domain/task-detail/profile'
import type { Task } from '@/types/api'

const task = {
  id: 'task-1',
  title: '整理部门交付材料',
  description: '收集并验收三位成员提交的文件。',
  creator_id: 'manager-1',
  assignee_id: 'employee-1',
  assignee_label: '成员 A',
  department_id: 'dept-1',
  status: 'doing',
  priority: 'high',
  due_date: '2026-07-31T10:00:00Z',
  created_at: '2026-07-29T08:00:00Z',
} as Task

const profile = {
  compactMetadata: false,
  hideHandshakeFields: false,
} as TaskDetailProfile

describe('task detail information hierarchy', () => {
  it('keeps only the six primary fields in the top two-column summary', () => {
    const wrapper = mount(TaskDetailMetadataPanel, {
      props: {
        task,
        profile,
        userFacingStateLabel: '处理中',
        userFacingTagType: 'warning',
        resolveDepartmentName: () => '内容部',
        resolveUserLabel: () => '成员 A',
        resolveRunLabel: () => 'Run 1',
      },
      global: { plugins: [ElementPlus] },
    })

    const summary = wrapper.find('[data-testid="task-detail-summary-grid"]')
    expect(summary.text()).toContain('任务标题')
    expect(summary.text()).toContain('任务描述')
    expect(summary.text()).toContain('状态')
    expect(summary.text()).toContain('优先级')
    expect(summary.text()).toContain('发布时间')
    expect(summary.text()).toContain('截止时间')
    expect(summary.text()).not.toContain('执行人')
    expect(summary.text()).not.toContain('最近返工原因')
  })

  it('moves collaboration and rework fields into the secondary panel', () => {
    const wrapper = mount(TaskDetailContextPanel, {
      props: {
        task,
        profile,
        handshakeStateLabel: '已接受',
        isGraphHandshakeTask: true,
        workflowNodeIteration: 2,
        workflowDeepRejectionReason: '材料不完整',
        latestRejectReason: '需补充说明',
        latestDelegateReason: '转由成员 A',
        latestDeliverableSummary: '已提交三份文件',
        latestDeliverableSubmittedAt: '2026-07-29T09:00:00Z',
        latestReviewQualityScore: 4,
        reworkCount: 1,
        latestReworkReason: '附件命名不规范',
        graphParentInstanceId: 'instance-12345678',
        graphRunKind: 'batch',
        resolveDepartmentName: () => '内容部',
        resolveUserLabel: () => '成员 A',
      },
      global: { plugins: [ElementPlus] },
    })

    const context = wrapper.find('[data-testid="task-detail-context-panel"]')
    expect(context.text()).toContain('执行人')
    expect(context.text()).toContain('最新交付说明')
    expect(context.text()).toContain('返工次数')
    expect(context.text()).toContain('最近返工原因')
    expect(context.text()).toContain('附件命名不规范')
  })
})
