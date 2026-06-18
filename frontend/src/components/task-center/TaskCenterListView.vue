<script setup lang="ts">
import type { TaskCenterFilter } from '@/constants/task-center'
import type { TaskCenterWorkspaceRow } from '@/composables/useTaskUserFacingProjection'
import { formatDateTime } from '@/utils/formatters'

const props = defineProps<{
  filter: TaskCenterFilter
  rows: TaskCenterWorkspaceRow[]
  selectedTaskId: string
  loading?: boolean
}>()

const emit = defineEmits<{
  select: [taskId: string]
  nudge: [taskId: string]
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
  <el-table
    v-loading="loading"
    :data="rows"
    :row-key="(row: TaskCenterWorkspaceRow) => row.taskId"
    :row-class-name="({ row }: { row: TaskCenterWorkspaceRow }) => rowClassName(row)"
    stripe
    highlight-current-row
    data-testid="task-center-list-view"
    @row-click="(row: TaskCenterWorkspaceRow) => emit('select', row.taskId)"
  >
    <el-table-column label="任务标题" min-width="200">
      <template #default="{ row }: { row: TaskCenterWorkspaceRow }">
        <el-space wrap>
          <span>{{ row.title }}</span>
          <el-tag v-if="row.isOverdue" type="danger" size="small" effect="plain">已逾期</el-tag>
        </el-space>
      </template>
    </el-table-column>
    <el-table-column label="Run" min-width="140">
      <template #default="{ row }: { row: TaskCenterWorkspaceRow }">
        {{ row.runLabel }}
      </template>
    </el-table-column>
    <el-table-column label="用户态" width="120">
      <template #default="{ row }: { row: TaskCenterWorkspaceRow }">
        <el-tag :type="normalizeTagType(row.userStateTagType)" effect="plain">
          {{ row.userStateLabel }}
        </el-tag>
      </template>
    </el-table-column>
    <el-table-column v-if="filter === 'tracking'" label="关联方式" min-width="140">
      <template #default="{ row }: { row: TaskCenterWorkspaceRow }">
        {{ row.relationTypes.length > 0 ? row.relationTypes.join('、') : '—' }}
      </template>
    </el-table-column>
    <el-table-column v-if="filter === 'history'" label="完成时间" min-width="180">
      <template #default="{ row }: { row: TaskCenterWorkspaceRow }">
        {{ formatDateTime(row.completedAt) }}
      </template>
    </el-table-column>
    <el-table-column v-else label="截止时间" min-width="180">
      <template #default="{ row }: { row: TaskCenterWorkspaceRow }">
        {{ formatDateTime(row.dueDate) }}
      </template>
    </el-table-column>
    <el-table-column v-if="filter === 'tracking'" label="操作" width="100" fixed="right">
      <template #default="{ row }: { row: TaskCenterWorkspaceRow }">
        <el-button size="small" @click.stop="emit('nudge', row.taskId)">催办</el-button>
      </template>
    </el-table-column>
  </el-table>
</template>

<style scoped>
:deep(.task-center-list-view__row--selected > td) {
  background: var(--el-color-primary-light-9) !important;
}
</style>
