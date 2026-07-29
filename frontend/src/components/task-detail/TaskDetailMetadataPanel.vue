<script setup lang="ts">
import {
  normalizeTagType,
  PRIORITY_TAG_TYPES,
  resolvePriorityLabel,
  resolveStatusLabel,
  STATUS_TAG_TYPES,
  type TagTypeInput,
} from '@/components/task-detail/task-detail-labels'
import type { TaskDetailProfile } from '@/domain/task-detail/profile'
import type { Task, TaskPriority, TaskStatus } from '@/types/api'
import { formatDateTime } from '@/utils/formatters'

defineProps<{
  task: Task
  profile: TaskDetailProfile
  userFacingStateLabel: string
  userFacingTagType: TagTypeInput
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
      <span>执行人 {{ resolveUserLabel(task.assignee_id, task.assignee_label) }}</span>
    </el-space>
  </div>

  <el-descriptions
    v-else
    :column="2"
    border
    class="task-detail-metadata__summary"
    data-testid="task-detail-summary-grid"
  >
    <el-descriptions-item label="任务标题">
      {{ task.title }}
    </el-descriptions-item>
    <el-descriptions-item label="任务描述">
      <span class="task-detail-metadata__description">{{ task.description || '—' }}</span>
    </el-descriptions-item>
    <el-descriptions-item label="状态">
      <el-tag :type="normalizeTagType(STATUS_TAG_TYPES[task.status as TaskStatus])" effect="plain">
        {{ resolveStatusLabel(task.status as TaskStatus) }}
      </el-tag>
    </el-descriptions-item>
    <el-descriptions-item label="优先级">
      <el-tag
        :type="normalizeTagType(PRIORITY_TAG_TYPES[task.priority as TaskPriority])"
        effect="plain"
      >
        {{ resolvePriorityLabel(task.priority as TaskPriority) }}
      </el-tag>
    </el-descriptions-item>
    <el-descriptions-item label="发布时间">
      {{ formatDateTime(task.created_at) }}
    </el-descriptions-item>
    <el-descriptions-item label="截止时间">
      {{ formatDateTime(task.due_date) }}
    </el-descriptions-item>
  </el-descriptions>
</template>

<style scoped>
.task-detail-metadata__compact {
  margin-bottom: 16px;
}

.task-detail-metadata__summary {
  margin-bottom: 16px;
}

.task-detail-metadata__description {
  display: -webkit-box;
  overflow: hidden;
  line-height: 1.55;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
}
</style>
