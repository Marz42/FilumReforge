<script setup lang="ts">
import type { TaskCenterFilter } from '@/constants/task-center'
import type { TaskCenterWorkspaceRow } from '@/composables/useTaskUserFacingProjection'
import { formatDateTime } from '@/utils/formatters'

const props = defineProps<{
  filter: TaskCenterFilter
  rows: TaskCenterWorkspaceRow[]
  selectedTaskId: string
  loading?: boolean
  canManageDueDate?: boolean
}>()

const emit = defineEmits<{
  select: [taskId: string]
  nudge: [taskId: string]
  extendDueDate: [taskId: string]
}>()

function normalizeTagType(
  value: '' | 'info' | 'warning' | 'success' | 'danger',
): 'info' | 'warning' | 'success' | 'danger' | undefined {
  return value || undefined
}

function rowClassName(row: TaskCenterWorkspaceRow): string {
  return row.taskId === props.selectedTaskId ? 'task-center-list-view__row--selected' : ''
}
</script>

<template>
  <div v-loading="loading" class="task-center-list-view" data-testid="task-center-list-view">
    <div
      v-for="row in rows"
      :key="row.taskId"
      class="task-center-list-view__row"
      :class="rowClassName(row)"
      :data-testid="`task-center-${filter}-row`"
    >
      <button
        type="button"
        class="task-center-list-view__content"
        @click="emit('select', row.taskId)"
      >
        <div class="task-center-list-view__title-row">
          <strong class="task-center-list-view__title">{{ row.title }}</strong>
          <el-tag v-if="row.isOverdue" type="danger" size="small" effect="plain">已逾期</el-tag>
          <el-tag
            v-else-if="filter === 'inbox'"
            :type="normalizeTagType(row.userStateTagType)"
            size="small"
            effect="plain"
          >
            {{ row.userStateLabel }}
          </el-tag>
        </div>

        <div class="task-center-list-view__meta">
          <template v-if="filter === 'history'">
            <span>执行人 {{ row.assigneeLabel || '—' }}</span>
            <span>完成于 {{ formatDateTime(row.completedAt) }}</span>
          </template>
          <template v-else-if="filter === 'tracking'">
            <span>当前执行人 {{ row.assigneeLabel || '—' }}</span>
            <span v-if="row.stageLabel">{{ row.stageLabel }}</span>
          </template>
          <template v-else>
            <span>执行人 {{ row.assigneeLabel || '—' }}</span>
            <span>截止 {{ formatDateTime(row.dueDate) }}</span>
          </template>
        </div>
      </button>

      <div v-if="filter === 'tracking'" class="task-center-list-view__actions">
        <el-button size="small" type="primary" plain @click.stop="emit('nudge', row.taskId)">
          催办
        </el-button>
        <el-button
          v-if="canManageDueDate && row.isOverdue"
          size="small"
          type="warning"
          plain
          data-testid="task-center-extend-due-date"
          @click.stop="emit('extendDueDate', row.taskId)"
        >
          延期
        </el-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.task-center-list-view {
  display: flex;
  flex-direction: column;
  min-height: 120px;
}

.task-center-list-view__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  width: 100%;
  padding: 14px 4px;
  border-bottom: 1px solid var(--filum-border);
  transition: background-color 0.15s ease;
}

.task-center-list-view__row:last-child {
  border-bottom: 0;
}

.task-center-list-view__row:hover {
  background: var(--el-fill-color-light);
}

.task-center-list-view__row--selected {
  background: var(--el-color-primary-light-9);
  box-shadow: inset 3px 0 0 var(--el-color-primary);
}

.task-center-list-view__content {
  flex: 1 1 auto;
  min-width: 0;
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.task-center-list-view__title-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.task-center-list-view__title {
  min-width: 0;
  overflow: hidden;
  color: var(--filum-text);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-center-list-view__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 14px;
  margin-top: 7px;
  color: var(--filum-text-secondary);
  font-size: 12px;
}

.task-center-list-view__actions {
  display: flex;
  flex: 0 0 auto;
  gap: 8px;
}

@media (max-width: 560px) {
  .task-center-list-view__row {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
