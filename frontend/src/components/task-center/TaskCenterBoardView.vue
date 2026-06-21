<script setup lang="ts">
import { computed } from 'vue'

import { groupRowsByUserState, type TaskCenterWorkspaceRow } from '@/composables/useTaskUserFacingProjection'
import { resolveRunColor } from '@/constants/task-center-run-colors'
import {
  TASK_USER_FACING_STATE_ORDER,
} from '@/constants/task-center'
import { TASK_USER_FACING_STATE_LABELS } from '@/domain/task-detail/user-state'
import { formatDateTime } from '@/utils/formatters'

const props = defineProps<{
  rows: TaskCenterWorkspaceRow[]
  selectedTaskId: string
  loading?: boolean
}>()

const emit = defineEmits<{
  select: [taskId: string]
}>()

const grouped = computed(() => groupRowsByUserState(props.rows))

function resolveAssigneeLabel(row: TaskCenterWorkspaceRow): string {
  return row.assigneeLabel ?? '—'
}
</script>

<template>
  <div v-loading="loading" class="task-center-board-view" data-testid="task-center-board-view">
    <div class="task-center-board-view__columns">
      <el-card
        v-for="state in TASK_USER_FACING_STATE_ORDER"
        :key="state"
        shadow="never"
        class="task-center-board-view__column"
        :data-testid="`board-column-${state}`"
      >
        <template #header>
          <div class="task-center-board-view__column-header">
            <span>{{ TASK_USER_FACING_STATE_LABELS[state] }}</span>
            <el-tag effect="plain">{{ grouped[state].length }}</el-tag>
          </div>
        </template>

        <el-empty v-if="grouped[state].length === 0" description="暂无任务" />
        <div v-else class="task-center-board-view__cards">
          <button
            v-for="row in grouped[state]"
            :key="row.taskId"
            type="button"
            class="task-center-board-view__card"
            :class="{ 'task-center-board-view__card--selected': row.taskId === selectedTaskId }"
            @click="emit('select', row.taskId)"
          >
            <strong>{{ row.title }}</strong>
            <span
              class="task-center-board-view__run-chip"
              :style="{ backgroundColor: resolveRunColor(row.runLabel) }"
            >
              {{ row.runLabel }}
            </span>
            <span class="task-center-board-view__meta">{{ resolveAssigneeLabel(row) }}</span>
            <span class="task-center-board-view__meta">{{ formatDateTime(row.dueDate) }}</span>
          </button>
        </div>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.task-center-board-view__columns {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
}

.task-center-board-view__column-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.task-center-board-view__cards {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.task-center-board-view__card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--filum-border-strong);
  border-radius: 10px;
  background: #fff;
  text-align: left;
  cursor: pointer;
}

.task-center-board-view__card:hover,
.task-center-board-view__card--selected {
  border-color: var(--el-color-primary);
}

.task-center-board-view__run-chip {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  color: #fff;
  font-size: 11px;
}

.task-center-board-view__meta {
  color: var(--filum-text-secondary);
  font-size: 12px;
}

@media (max-width: 1200px) {
  .task-center-board-view__columns {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
