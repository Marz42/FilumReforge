import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { describe, expect, it } from 'vitest'

import TaskDetailHeaderBar from '@/components/task-detail/TaskDetailHeaderBar.vue'
import { resolveTaskDetailProfile } from '@/domain/task-detail/profile'

const batchRootTask = {
  id: 'task-batch-root',
  title: '批次 Run',
  description: null,
  creator_id: 'user-admin',
  assignee_id: 'user-admin',
  department_id: 'dept-1',
  status: 'doing' as const,
  priority: 'high' as const,
  due_date: null,
  started_at: null,
  completed_at: null,
  parent_task_id: null,
  source_type: 'template' as const,
  extra_metadata: {
    workflow_graph_instance_id: 'graph-1',
    workflow_graph_root_task: true,
    run_kind: 'batch',
  },
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
}

describe('TaskDetailHeaderBar', () => {
  it('renders close capture button for batch root run', () => {
    const wrapper = mount(TaskDetailHeaderBar, {
      props: {
        showCloseCaptureButton: true,
        closeCaptureSubmitting: false,
        showDetailHeaderActions: false,
        canDecideApproval: false,
        approvalSubmitting: false,
        canReviewDeliverable: false,
        useVideoProductionReviewMoreMenu: false,
        deliverableReviewComment: '',
        selectedTask: batchRootTask,
        isGraphHandshakeTask: false,
        canAcceptTask: false,
        canRejectTask: false,
        canDelegateTask: false,
        handshakeSubmitting: false,
        nextStatusAction: null,
        canAdvanceSelectedTaskByStatus: false,
        statusSubmitting: false,
        canSubmitDeliverable: false,
        selectedTaskProfile: resolveTaskDetailProfile(batchRootTask),
        videoProductionPanelRef: null,
        deliverableSubmitting: false,
        usesVideoWorkflowLayout: true,
        graphInstance: null,
        canManageCaptureReject: true,
        canRejectProductionStep: false,
        canAdminArchive: false,
      },
      global: {
        plugins: [ElementPlus],
        stubs: {
          TaskDetailMoreMenu: true,
        },
      },
    })

    expect(wrapper.find('[data-testid="video-batch-close-capture"]').text()).toContain('结束采集')
  })
})
