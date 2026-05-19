<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'

import type { OverviewTaskInboxEntry, ReportRecord, TaskPriority } from '@/types/api'
import { formatDateTime } from '@/utils/formatters'

const props = defineProps<{
  inboxTasks: OverviewTaskInboxEntry[]
  pendingReports: ReportRecord[]
  loading?: boolean
}>()

const router = useRouter()

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
      <div class="overview-widget__heading">
        <span>待办与汇报</span>
        <small>点击条目跳转到任务中心或汇报中心处理</small>
      </div>
    </template>

    <section class="overview-todo-widget__section">
      <div class="overview-todo-widget__section-title">待办任务</div>
      <el-empty v-if="inboxPreview.length === 0" description="当前没有待办任务" />
      <div v-else class="overview-widget__list">
        <button
          v-for="item in inboxPreview"
          :key="item.task_id"
          type="button"
          class="overview-widget__item"
          @click="openTask(item.task_id)"
        >
          <div class="overview-widget__item-meta">
            <strong>{{ item.title }}</strong>
            <el-tag :type="priorityTagType(item.priority)" effect="plain" size="small">
              {{ priorityLabel(item.priority) }}
            </el-tag>
          </div>
          <p class="overview-widget__item-content">
            {{ item.current_stage_label }}
            <span v-if="item.current_handler_label"> · {{ item.current_handler_label }}</span>
          </p>
          <span class="overview-widget__footnote">
            {{ item.department_name ?? '未分配部门' }} · 到期：{{ formatDateTime(item.due_date) }}
          </span>
        </button>
      </div>
    </section>

    <section class="overview-todo-widget__section">
      <div class="overview-todo-widget__section-title">待审汇报</div>
      <el-empty v-if="reportPreview.length === 0" description="当前没有待审汇报" />
      <div v-else class="overview-widget__list">
        <button
          v-for="report in reportPreview"
          :key="report.id"
          type="button"
          class="overview-widget__item"
          @click="openReport(report.id)"
        >
          <div class="overview-widget__item-meta">
            <strong>{{ report.title }}</strong>
            <el-tag effect="plain" size="small">{{ report.direction === 'upward' ? '向上' : '向下' }}</el-tag>
          </div>
          <p class="overview-widget__item-content">
            {{ report.initiator_label }} → {{ report.target_label }}
          </p>
          <span class="overview-widget__footnote">更新：{{ formatDateTime(report.updated_at) }}</span>
        </button>
      </div>
    </section>
  </el-card>
</template>

<style scoped>
.overview-widget__heading {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.overview-widget__heading small {
  color: var(--filum-text-secondary);
  font-size: 12px;
}

.overview-todo-widget__section + .overview-todo-widget__section {
  margin-top: 18px;
  padding-top: 18px;
  border-top: 1px solid var(--filum-border);
}

.overview-todo-widget__section-title {
  margin-bottom: 10px;
  font-size: 13px;
  font-weight: 600;
  color: var(--filum-text-secondary);
}

.overview-widget__list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.overview-widget__item {
  width: 100%;
  padding: 12px 14px;
  border: 1px solid var(--filum-border-strong);
  border-radius: 12px;
  background: linear-gradient(180deg, #ffffff 0%, #f8faff 100%);
  text-align: left;
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease;
}

.overview-widget__item:hover {
  border-color: var(--el-color-primary-light-5);
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.06);
}

.overview-widget__item-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.overview-widget__item-meta strong {
  color: var(--filum-text);
  font-size: 14px;
}

.overview-widget__item-content {
  margin: 8px 0 0;
  color: var(--filum-text-secondary);
  line-height: 1.5;
}

.overview-widget__footnote {
  display: inline-block;
  margin-top: 8px;
  color: var(--filum-text-muted);
  font-size: 12px;
}
</style>
