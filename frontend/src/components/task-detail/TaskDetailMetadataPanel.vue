<script setup lang="ts">
import {
  normalizeTagType,
  PRIORITY_TAG_TYPES,
  resolvePriorityLabel,
  resolveStatusLabel,
  STATUS_TAG_TYPES,
} from '@/components/task-detail/task-detail-labels'
import type { TaskDetailProfile } from '@/domain/task-detail/profile'
import type { Task, TaskPriority, TaskStatus } from '@/types/api'
import { formatDateTime } from '@/utils/formatters'

defineProps<{
  task: Task
  profile: TaskDetailProfile
  userFacingStateLabel: string
  userFacingTagType: 'info' | 'warning' | 'success' | 'danger' | 'primary'
  handshakeStateLabel: string
  isGraphHandshakeTask: boolean
  workflowNodeIteration: number
  workflowDeepRejectionReason: string | null
  latestRejectReason: string
  latestDelegateReason: string
  latestDeliverableSummary: string
  latestDeliverableSubmittedAt: string | null
  latestReviewQualityScore: number | null
  reworkCount: number
  latestReworkReason: string
  graphParentInstanceId: string | null
  graphRunKind: string
  resolveDepartmentName: (departmentId: string | null) => string
  resolveUserLabel: (userId: string, preferredLabel?: string | null) => string
  resolveRunLabel: (task: Task) => string
}>()
</script>

<template>
  <div
    v-if="profile.compactMetadata"
    class="task-detail-metadata__compact"
    data-testid="task-detail-compact-meta"
  >
    <el-space wrap>
      <span>
        用户态
        <el-tag :type="normalizeTagType(userFacingTagType)" effect="plain">
          {{ userFacingStateLabel }}
        </el-tag>
      </span>
      <span>截止时间 {{ formatDateTime(task.due_date) }}</span>
      <span>所属部门 {{ resolveDepartmentName(task.department_id) }}</span>
      <span>Run {{ resolveRunLabel(task) }}</span>
      <span>执行人 {{ resolveUserLabel(task.assignee_id) }}</span>
    </el-space>
  </div>

  <el-descriptions v-else :column="1" border>
    <el-descriptions-item label="任务标题">
      {{ task.title }}
    </el-descriptions-item>
    <el-descriptions-item label="执行人">
      {{ resolveUserLabel(task.assignee_id) }}
    </el-descriptions-item>
    <el-descriptions-item label="状态">
      <el-tag :type="normalizeTagType(STATUS_TAG_TYPES[task.status as TaskStatus])" effect="plain">
        {{ resolveStatusLabel(task.status as TaskStatus) }}
      </el-tag>
    </el-descriptions-item>
    <el-descriptions-item label="优先级">
      <el-tag :type="normalizeTagType(PRIORITY_TAG_TYPES[task.priority as TaskPriority])" effect="plain">
        {{ resolvePriorityLabel(task.priority as TaskPriority) }}
      </el-tag>
    </el-descriptions-item>
    <el-descriptions-item label="所属部门">
      {{ resolveDepartmentName(task.department_id) }}
    </el-descriptions-item>
    <el-descriptions-item label="截止时间">
      {{ formatDateTime(task.due_date) }}
    </el-descriptions-item>
    <el-descriptions-item label="任务描述">
      {{ task.description || '—' }}
    </el-descriptions-item>
    <el-descriptions-item v-if="!profile.hideHandshakeFields" label="握手状态">
      {{ handshakeStateLabel }}
    </el-descriptions-item>
    <el-descriptions-item
      v-if="!profile.hideHandshakeFields && isGraphHandshakeTask && workflowNodeIteration > 1"
      label="迭代版本"
    >
      V{{ workflowNodeIteration }}（系统深度打回重放）
    </el-descriptions-item>
    <el-descriptions-item v-if="isGraphHandshakeTask && workflowDeepRejectionReason" label="打回原因">
      {{ workflowDeepRejectionReason }}
    </el-descriptions-item>
    <el-descriptions-item label="最近协商原因">
      {{ latestRejectReason }}
    </el-descriptions-item>
    <el-descriptions-item label="最近转办原因">
      {{ latestDelegateReason }}
    </el-descriptions-item>
    <el-descriptions-item label="最新交付说明">
      {{ latestDeliverableSummary }}
    </el-descriptions-item>
    <el-descriptions-item label="最近提交时间">
      {{ formatDateTime(latestDeliverableSubmittedAt) }}
    </el-descriptions-item>
    <el-descriptions-item label="完成质量评分">
      {{ latestReviewQualityScore ? `${latestReviewQualityScore}/5` : '—' }}
    </el-descriptions-item>
    <el-descriptions-item label="返工次数">
      {{ reworkCount }}
    </el-descriptions-item>
    <el-descriptions-item label="最近返工原因">
      {{ latestReworkReason }}
    </el-descriptions-item>
    <el-descriptions-item v-if="graphParentInstanceId" label="所属批次">
      实例 {{ graphParentInstanceId.slice(0, 8) }}…
    </el-descriptions-item>
    <el-descriptions-item v-if="graphRunKind" label="运行类型">
      {{ graphRunKind === 'batch' ? '批次 Run' : graphRunKind === 'production' ? '制作 Run' : graphRunKind }}
    </el-descriptions-item>
  </el-descriptions>
</template>

<style scoped>
.task-detail-metadata__compact {
  margin-bottom: 16px;
}
</style>
