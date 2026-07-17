<script setup lang="ts">
import TaskDetailMoreMenu from '@/components/task-detail/TaskDetailMoreMenu.vue'
import type { TaskDetailProfile } from '@/domain/task-detail/profile'
import type { Task, TaskStatus, WorkflowGraphInstanceDetail } from '@/types/api'

type StatusAction = {
  label: string
  status: TaskStatus
  buttonType: 'primary' | 'warning' | 'success'
}

type VideoProductionPanelExpose = {
  submit: () => void
  submitting: boolean
}

defineProps<{
  showCloseCaptureButton: boolean
  closeCaptureSubmitting: boolean
  showDetailHeaderActions: boolean
  canDecideApproval: boolean
  approvalSubmitting: boolean
  canReviewDeliverable: boolean
  useVideoProductionReviewMoreMenu: boolean
  deliverableReviewComment: string
  selectedTask: Task | null
  isGraphHandshakeTask: boolean
  isStandaloneTask: boolean
  canAcceptTask: boolean
  canRejectTask: boolean
  canDelegateTask: boolean
  handshakeSubmitting: boolean
  nextStatusAction: StatusAction | null
  canAdvanceSelectedTaskByStatus: boolean
  statusSubmitting: boolean
  canSubmitDeliverable: boolean
  selectedTaskProfile: TaskDetailProfile
  videoProductionPanelRef: VideoProductionPanelExpose | null
  deliverableSubmitting: boolean
  usesVideoWorkflowLayout: boolean
  graphInstance: WorkflowGraphInstanceDetail | null
  canManageCaptureReject: boolean
  canRejectProductionStep: boolean
  canAdminArchive: boolean
}>()

const emit = defineEmits<{
  closeCapture: []
  approvalDecide: ['approved' | 'rejected']
  openRejectDialog: []
  deliverableReview: ['approve']
  openReworkDialog: []
  acceptAssignment: []
  openHandshakeRejectDialog: []
  openDelegateDialog: []
  statusTransition: []
  submitDeliverable: []
  actionDone: []
  taskArchived: []
}>()
</script>

<template>
  <div class="task-detail-header-bar">
    <span>任务协同详情</span>
    <div v-if="showCloseCaptureButton" class="task-detail-header-bar__actions">
      <el-button
        type="warning"
        :loading="closeCaptureSubmitting"
        data-testid="video-batch-close-capture"
        @click="emit('closeCapture')"
      >
        结束采集
      </el-button>
    </div>
    <div v-else-if="showDetailHeaderActions" class="task-detail-header-bar__actions">
      <el-button
        v-if="isStandaloneTask && canDelegateTask"
        type="warning"
        plain
        :loading="handshakeSubmitting"
        data-testid="standalone-delegate-button"
        @click="emit('openDelegateDialog')"
      >
        转办
      </el-button>
      <template v-if="canDecideApproval">
        <el-button
          type="success"
          :loading="approvalSubmitting"
          @click="emit('approvalDecide', 'approved')"
        >
          审核通过
        </el-button>
        <el-button
          type="danger"
          :loading="approvalSubmitting"
          @click="emit('openRejectDialog')"
        >
          驳回修改
        </el-button>
      </template>
      <template v-else-if="canReviewDeliverable">
        <el-button
          type="success"
          :loading="approvalSubmitting"
          @click="emit('deliverableReview', 'approve')"
        >
          验收通过
        </el-button>
        <el-button
          v-if="!useVideoProductionReviewMoreMenu"
          type="danger"
          :loading="approvalSubmitting"
          @click="emit('openReworkDialog')"
        >
          打回返工
        </el-button>
      </template>
      <template v-else-if="selectedTask && isGraphHandshakeTask && selectedTask.status === 'todo'">
        <el-button
          v-if="canAcceptTask"
          type="primary"
          :loading="handshakeSubmitting"
          @click="emit('acceptAssignment')"
        >
          接受任务
        </el-button>
        <el-button
          v-if="canRejectTask"
          type="danger"
          plain
          :loading="handshakeSubmitting"
          @click="emit('openHandshakeRejectDialog')"
        >
          退回协商
        </el-button>
        <el-button
          v-if="canDelegateTask"
          type="warning"
          plain
          :loading="handshakeSubmitting"
          @click="emit('openDelegateDialog')"
        >
          转办
        </el-button>
        <el-button
          v-if="nextStatusAction && canAdvanceSelectedTaskByStatus"
          :type="nextStatusAction.buttonType"
          :loading="statusSubmitting"
          @click="emit('statusTransition')"
        >
          {{ nextStatusAction.label }}
        </el-button>
      </template>
      <el-button
        v-else-if="canSubmitDeliverable && selectedTaskProfile.submitMode === 'file'"
        type="primary"
        :loading="videoProductionPanelRef?.submitting ?? false"
        data-testid="video-production-header-submit"
        @click="videoProductionPanelRef?.submit()"
      >
        上传并提交
      </el-button>
      <el-button
        v-else-if="canSubmitDeliverable"
        type="warning"
        :loading="deliverableSubmitting"
        @click="emit('submitDeliverable')"
      >
        提交交付物
      </el-button>
      <el-button
        v-else-if="selectedTask && nextStatusAction && canAdvanceSelectedTaskByStatus"
        :type="nextStatusAction.buttonType"
        :loading="statusSubmitting"
        @click="emit('statusTransition')"
      >
        {{ nextStatusAction.label }}
      </el-button>
    </div>
    <TaskDetailMoreMenu
      v-if="selectedTask && (usesVideoWorkflowLayout || canAdminArchive)"
      :profile="selectedTaskProfile"
      :task="selectedTask"
      :graph-instance="graphInstance"
      :can-manage-capture-reject="canManageCaptureReject"
      :can-reject-production="canRejectProductionStep"
      :can-admin-archive="canAdminArchive"
      @action-done="emit('actionDone')"
      @task-archived="emit('taskArchived')"
    />
  </div>
</template>

<style scoped>
.task-detail-header-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.task-detail-header-bar__actions {
  display: flex;
  gap: 8px;
  align-items: center;
}
</style>
