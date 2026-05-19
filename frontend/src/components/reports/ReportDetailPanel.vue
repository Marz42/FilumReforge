<script setup lang="ts">
import { attachmentMimeIsInlineViewable } from '@/constants/attachments'
import type { ReportActionOption, ReportDirection, ReportRecord, ReportRouteStatus, ReportStatus } from '@/types/api'
import { formatDateTime } from '@/utils/formatters'

interface Props {
  report: ReportRecord | null
  actionKey?: string
}

const props = withDefaults(defineProps<Props>(), {
  actionKey: '',
})

const emit = defineEmits<{
  action: [reportId: string, action: ReportActionOption]
}>()

const STATUS_LABELS: Record<ReportStatus, string> = {
  in_progress: '流转中',
  completed: '已完成',
  returned: '已退回',
  archived: '已归档',
}

const STATUS_TAG_TYPES: Record<ReportStatus, '' | 'warning' | 'success' | 'info'> = {
  in_progress: 'warning',
  completed: 'success',
  returned: '',
  archived: 'info',
}

const DIRECTION_LABELS: Record<ReportDirection, string> = {
  upward: '向上汇报',
  downward: '向下传达',
}

const ROUTE_STATUS_LABELS: Record<ReportRouteStatus, string> = {
  queued: '待激活',
  pending: '待处理',
  forwarded: '已转交',
  completed: '已完成',
  returned: '已退回',
}

function resolveStatusLabel(status: ReportStatus): string {
  return STATUS_LABELS[status]
}

function resolveDirectionLabel(direction: ReportDirection): string {
  return DIRECTION_LABELS[direction]
}

function resolveRouteStatusLabel(status: ReportRouteStatus): string {
  return ROUTE_STATUS_LABELS[status]
}

function isActionLoading(reportId: string, action: string): boolean {
  return props.actionKey === `${reportId}:${action}`
}
</script>

<template>
  <el-card shadow="never" class="report-detail-panel" data-testid="reports-detail-panel">
    <template v-if="report" #header>
      <div class="report-detail-panel__header">
        <div>
          <div class="report-detail-panel__title">{{ report.title }}</div>
          <div class="report-detail-panel__subtitle">
            {{ resolveDirectionLabel(report.direction) }} · 发起人 {{ report.initiator_label }}
          </div>
        </div>
        <el-space wrap>
          <el-tag :type="STATUS_TAG_TYPES[report.status]">{{ resolveStatusLabel(report.status) }}</el-tag>
          <el-tag v-if="report.current_recipient_label" type="info">{{ report.current_recipient_label }}</el-tag>
        </el-space>
      </div>
    </template>

    <template v-if="report">
      <div class="report-detail-panel__content">{{ report.content_md }}</div>

      <div v-if="report.attachments?.length" class="report-detail-panel__attachments">
        <el-divider content-position="left">附件</el-divider>
        <el-space wrap>
          <el-card v-for="attachment in report.attachments" :key="attachment.id" shadow="never" class="report-detail-panel__att-card">
            <div>
              <strong>{{ attachment.original_filename }}</strong>
            </div>
            <div class="report-detail-panel__att-meta">{{ attachment.mime_type }}</div>
            <el-space v-if="attachment.download_url">
              <el-link
                v-if="attachmentMimeIsInlineViewable(attachment.mime_type)"
                :href="attachment.download_url"
                target="_blank"
                type="primary"
                data-testid="report-attachment-view"
              >
                查看
              </el-link>
              <el-link
                :href="attachment.download_url"
                target="_blank"
                type="primary"
                data-testid="report-attachment-open"
              >
                {{ attachmentMimeIsInlineViewable(attachment.mime_type) ? '下载' : '打开/下载' }}
              </el-link>
            </el-space>
          </el-card>
        </el-space>
      </div>

      <div class="report-detail-panel__meta">
        <span>目标：{{ report.target_label }}</span>
        <span>创建时间：{{ formatDateTime(report.created_at) }}</span>
        <span v-if="report.workflow_definition_name">挂接审批：{{ report.workflow_definition_name }}</span>
        <span v-if="report.completed_at">完成时间：{{ formatDateTime(report.completed_at) }}</span>
        <span v-else-if="report.returned_at">退回时间：{{ formatDateTime(report.returned_at) }}</span>
        <span v-else-if="report.archived_at">归档时间：{{ formatDateTime(report.archived_at) }}</span>
      </div>

      <el-timeline>
        <el-timeline-item
          v-for="routeItem in report.routes"
          :key="routeItem.id"
          :timestamp="routeItem.acted_at ? formatDateTime(routeItem.acted_at) : routeItem.activated_at ? formatDateTime(routeItem.activated_at) : ''"
        >
          <div class="report-detail-panel__route-line">
            {{ routeItem.sequence_no }}. {{ routeItem.sender_label }} -> {{ routeItem.recipient_label }}
            <span v-if="routeItem.assigned_label && routeItem.assigned_label !== routeItem.recipient_label">
              （代理：{{ routeItem.assigned_label }}）
            </span>
            · {{ resolveRouteStatusLabel(routeItem.status) }}
          </div>
          <div v-if="routeItem.note" class="report-detail-panel__route-note">{{ routeItem.note }}</div>
        </el-timeline-item>
      </el-timeline>

      <el-space v-if="report.available_actions.length > 0" wrap>
        <el-button
          v-for="action in report.available_actions"
          :key="action.action"
          size="small"
          :type="action.button_type"
          :loading="isActionLoading(report.id, action.action)"
          @click="emit('action', report.id, action)"
        >
          {{ action.label }}
        </el-button>
      </el-space>
    </template>

    <el-empty v-else description="请选择左侧汇报查看详情" />
  </el-card>
</template>

<style scoped>
.report-detail-panel {
  min-height: 420px;
}

.report-detail-panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.report-detail-panel__title {
  font-size: 18px;
  font-weight: 600;
}

.report-detail-panel__subtitle {
  margin-top: 4px;
  color: var(--filum-text-secondary);
  font-size: 13px;
}

.report-detail-panel__content {
  white-space: pre-wrap;
  line-height: 1.7;
  margin-bottom: 16px;
}

.report-detail-panel__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
  color: var(--filum-text-secondary);
  font-size: 13px;
}

.report-detail-panel__route-line {
  line-height: 1.5;
}

.report-detail-panel__route-note {
  margin-top: 4px;
  color: var(--filum-text-secondary);
  font-size: 13px;
}

.report-detail-panel__att-card {
  min-width: 180px;
}

.report-detail-panel__att-meta {
  color: var(--filum-text-muted);
  font-size: 12px;
  margin: 4px 0 8px;
}
</style>
