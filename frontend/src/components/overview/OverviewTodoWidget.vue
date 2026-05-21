<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import type { OverviewTaskInboxEntry, ReportRecord, TaskPriority } from '@/types/api'
import { formatDateTime } from '@/utils/formatters'

const props = defineProps<{
  inboxTasks: OverviewTaskInboxEntry[]
  pendingReports: ReportRecord[]
  loading?: boolean
}>()

const router = useRouter()
const activePane = ref<'todo' | 'report'>('todo')

const inboxPreview = computed(() => props.inboxTasks.slice(0, 5))
const reportPreview = computed(() => props.pendingReports.slice(0, 5))

function priorityTagType(priority: TaskPriority): 'danger' | 'warning' | 'info' | 'success' {
  switch (priority) {
    case 'urgent':
      return 'danger'
    case 'high':
      return 'warning'
    case 'medium':
      return 'info'
    case 'low':
      return 'success'
  }
}

function priorityLabel(priority: TaskPriority): string {
  const labels: Record<TaskPriority, string> = {
    urgent: '紧急',
    high: '高',
    medium: '中',
    low: '低',
  }
  return labels[priority]
}

function openTask(taskId: string): void {
  void router.push({
    name: 'task-center',
    query: {
      filter: 'inbox',
      selected: taskId,
    },
  })
}

function openReport(reportId: string): void {
  void router.push({
    name: 'reports',
    query: {
      filter: 'pending',
      selected: reportId,
    },
  })
}
</script>

<template>
  <el-card
    shadow="never"
    class="overview-widget overview-todo-widget filum-panel-card"
    data-testid="overview-widget-todos"
    v-loading="loading"
  >
    <template #header>
      <div class="overview-todo-widget__header">
        <div class="overview-widget__heading">
          <span>待办 / 汇报</span>
          <small>点击条目跳转到任务中心或汇报中心处理</small>
        </div>
        <el-radio-group v-model="activePane" size="small" data-testid="overview-todo-pane-switch">
          <el-radio-button value="todo">待办</el-radio-button>
          <el-radio-button value="report">汇报</el-radio-button>
        </el-radio-group>
      </div>
    </template>

    <template v-if="activePane === 'todo'">
      <el-empty
        v-if="inboxPreview.length === 0"
        class="overview-widget__empty"
        description="当前没有待办任务"
      />
      <ul v-else class="overview-todo-list" data-testid="overview-todo-task-list">
        <li
          v-for="item in inboxPreview"
          :key="item.task_id"
          class="overview-todo-list__row"
        >
          <button type="button" class="overview-todo-list__button" @click="openTask(item.task_id)">
            <div class="overview-todo-list__main">
              <strong class="overview-todo-list__title">{{ item.title }}</strong>
              <el-tag :type="priorityTagType(item.priority)" effect="plain" size="small">
                {{ priorityLabel(item.priority) }}
              </el-tag>
            </div>
            <p class="overview-todo-list__meta">
              {{ item.current_stage_label }}
              <span v-if="item.current_handler_label"> · {{ item.current_handler_label }}</span>
            </p>
            <span class="overview-todo-list__footnote">
              {{ item.department_name ?? '未分配部门' }} · 到期：{{ formatDateTime(item.due_date) }}
            </span>
          </button>
        </li>
      </ul>
    </template>

    <template v-else>
      <el-empty
        v-if="reportPreview.length === 0"
        class="overview-widget__empty"
        description="当前没有待审汇报"
      />
      <ul v-else class="overview-todo-list" data-testid="overview-report-list">
        <li
          v-for="report in reportPreview"
          :key="report.id"
          class="overview-todo-list__row"
        >
          <button type="button" class="overview-todo-list__button" @click="openReport(report.id)">
            <div class="overview-todo-list__main">
              <strong class="overview-todo-list__title">{{ report.title }}</strong>
              <el-tag effect="plain" size="small">{{ report.direction === 'upward' ? '向上' : '向下' }}</el-tag>
            </div>
            <p class="overview-todo-list__meta">
              {{ report.initiator_label }} → {{ report.target_label }}
            </p>
            <span class="overview-todo-list__footnote">
              更新于 {{ formatDateTime(report.updated_at) }}
            </span>
          </button>
        </li>
      </ul>
    </template>
  </el-card>
</template>

<style scoped>
.overview-todo-widget__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.overview-widget__heading {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.overview-widget__heading small {
  color: var(--filum-text-secondary);
  font-size: 12px;
}

.overview-widget__empty {
  padding: 4px 0;
}

.overview-todo-list {
  margin: 0;
  padding: 0;
  list-style: none;
}

.overview-todo-list__row {
  border-bottom: 1px solid var(--filum-border-strong);
}

.overview-todo-list__row:last-child {
  border-bottom: none;
}

.overview-todo-list__button {
  display: block;
  width: 100%;
  padding: 12px 4px;
  border: none;
  background: transparent;
  text-align: left;
  cursor: pointer;
  transition: background-color 0.2s ease;
}

.overview-todo-list__button:hover {
  background: rgba(37, 99, 235, 0.04);
}

.overview-todo-list__main {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.overview-todo-list__title {
  color: var(--filum-text);
  font-size: 14px;
  font-weight: 600;
}

.overview-todo-list__meta {
  margin: 6px 0 0;
  color: var(--filum-text-secondary);
  font-size: 13px;
  line-height: 1.5;
}

.overview-todo-list__footnote {
  display: inline-block;
  margin-top: 6px;
  color: var(--filum-text-muted);
  font-size: 12px;
}
</style>
