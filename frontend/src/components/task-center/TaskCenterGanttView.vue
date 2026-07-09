<script setup lang="ts">
import { computed } from 'vue'

import type { TaskCenterWorkspaceRow } from '@/composables/useTaskUserFacingProjection'
import { resolveRunColor } from '@/constants/task-center-run-colors'
import { formatDateTime } from '@/utils/formatters'

const props = defineProps<{
  rows: TaskCenterWorkspaceRow[]
  selectedTaskId: string
  loading?: boolean
}>()

const emit = defineEmits<{
  select: [taskId: string]
}>()

const MS_DAY = 86_400_000

const rowsWithDue = computed(() => props.rows.filter((row) => row.dueDate != null))

const windowRange = computed(() => {
  const timestamps: number[] = []
  for (const row of rowsWithDue.value) {
    const start = resolveStartMs(row)
    const end = new Date(row.dueDate!).getTime()
    timestamps.push(start, end)
  }
  if (timestamps.length === 0) {
    const now = Date.now()
    return { start: now, end: now + MS_DAY * 14 }
  }
  const min = Math.min(...timestamps)
  const max = Math.max(...timestamps)
  const padding = MS_DAY
  return { start: min - padding, end: max + padding }
})

function resolveStartMs(row: TaskCenterWorkspaceRow): number {
  const started = row.task.started_at ?? row.task.created_at
  return new Date(started).getTime()
}

function resolveBarStyle(row: TaskCenterWorkspaceRow): { left: string; width: string; backgroundColor: string } {
  const { start, end } = windowRange.value
  const span = Math.max(end - start, MS_DAY)
  const barStart = resolveStartMs(row)
  const barEnd = new Date(row.dueDate!).getTime()
  const left = ((barStart - start) / span) * 100
  const width = Math.max(((barEnd - barStart) / span) * 100, 2)
  return {
    left: `${Math.min(Math.max(left, 0), 98)}%`,
    width: `${Math.min(width, 100 - left)}%`,
    backgroundColor: resolveRunColor(row.runLabel),
  }
}
</script>

<template>
  <div v-loading="loading" class="task-center-gantt-view" data-testid="task-center-gantt-view">
    <el-empty v-if="rows.length === 0" description="暂无任务" />
    <el-empty v-else-if="rowsWithDue.length === 0" description="无截止时间的任务不在甘特中显示" />
    <div v-else class="task-center-gantt-view__rows">
      <button
        v-for="row in rowsWithDue"
        :key="row.taskId"
        type="button"
        class="task-center-gantt-view__row"
        :class="{ 'task-center-gantt-view__row--selected': row.taskId === selectedTaskId }"
        @click="emit('select', row.taskId)"
      >
        <div class="task-center-gantt-view__label">
          <strong>{{ row.title }}</strong>
          <span>{{ formatDateTime(row.dueDate) }}</span>
        </div>
        <div class="task-center-gantt-view__track">
          <div class="task-center-gantt-view__bar" :style="resolveBarStyle(row)" />
        </div>
      </button>
    </div>
  </div>
</template>

<style scoped>
.task-center-gantt-view__rows {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.task-center-gantt-view__row {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 8px 0;
  border: none;
  background: transparent;
  text-align: left;
  cursor: pointer;
}

.task-center-gantt-view__row--selected .task-center-gantt-view__track {
  outline: 2px solid var(--el-color-primary);
  outline-offset: 2px;
}

.task-center-gantt-view__label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  width: 180px;
  flex-shrink: 0;
  font-size: 12px;
}

.task-center-gantt-view__label span {
  color: var(--filum-text-secondary);
}

.task-center-gantt-view__track {
  position: relative;
  flex: 1;
  height: 24px;
  border-radius: 6px;
  background: #f2f4f7;
}

.task-center-gantt-view__bar {
  position: absolute;
  top: 3px;
  bottom: 3px;
  border-radius: 4px;
  min-width: 8px;
}
</style>
