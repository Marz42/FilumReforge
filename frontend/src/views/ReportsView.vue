<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'

import ReportComposeDrawer from '@/components/reports/ReportComposeDrawer.vue'
import ReportDetailPanel from '@/components/reports/ReportDetailPanel.vue'
import { actReport, getReportCenterSnapshot } from '@/api/report-center'
import type {
  ReportActionOption,
  ReportCenterSnapshot,
  ReportDirection,
  ReportRecord,
  ReportStatus,
} from '@/types/api'
import { getErrorMessage } from '@/utils/errors'
import { formatDateTime } from '@/utils/formatters'

type ReportCenterFilter = 'pending' | 'initiated' | 'history'

const STATUS_LABELS: Record<ReportStatus, string> = {
  in_progress: '流转中',
  completed: '已完成',
  returned: '已退回',
  archived: '已归档',
}

const STATUS_DOT_CLASS: Record<ReportStatus, string> = {
  in_progress: 'reports-page__status-dot--in-progress',
  completed: 'reports-page__status-dot--completed',
  returned: 'reports-page__status-dot--returned',
  archived: 'reports-page__status-dot--archived',
}

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const actionKey = ref('')
const snapshot = ref<ReportCenterSnapshot | null>(null)
const showComposeDrawer = ref(false)
const composeInitialDirection = ref<ReportDirection | null>(null)

const activeFilter = computed<ReportCenterFilter>(() => normalizeFilter(route.query.filter ?? route.query.tab))
const selectedReportId = computed(() => (typeof route.query.selected === 'string' ? route.query.selected : ''))

const pendingReports = computed(() => snapshot.value?.pending_reports ?? [])
const initiatedReports = computed(() => snapshot.value?.initiated_reports ?? [])
const historyReports = computed(() => snapshot.value?.history_reports ?? [])
const upwardTargetOptions = computed(() => snapshot.value?.upward_target_options ?? [])
const downwardTargetOptions = computed(() => snapshot.value?.downward_target_options ?? [])
const workflowDefinitionOptions = computed(() => snapshot.value?.workflow_definition_options ?? [])

const permissions = computed(() => {
  return (
    snapshot.value?.permissions ?? {
      can_create_upward: false,
      can_create_downward: false,
    }
  )
})

const canComposeReport = computed(
  () => permissions.value.can_create_upward || permissions.value.can_create_downward,
)

const filteredReports = computed(() => {
  if (activeFilter.value === 'initiated') {
    return initiatedReports.value
  }
  if (activeFilter.value === 'history') {
    return historyReports.value
  }
  return pendingReports.value
})

const selectedReport = computed(() => {
  if (!selectedReportId.value) {
    return null
  }
  return filteredReports.value.find((report) => report.id === selectedReportId.value) ?? null
})

function normalizeFilter(rawFilter: unknown): ReportCenterFilter {
  if (rawFilter === 'pending' || rawFilter === 'initiated' || rawFilter === 'history') {
    return rawFilter
  }
  return 'pending'
}

function buildRouteQuery(options: {
  filter?: ReportCenterFilter
  selected?: string
}): Record<string, string> | undefined {
  const filter = options.filter ?? activeFilter.value
  const selected = options.selected ?? selectedReportId.value
  const query: Record<string, string> = {}

  if (filter !== 'pending') {
    query.filter = filter
  }
  if (selected) {
    query.selected = selected
  }

  return Object.keys(query).length > 0 ? query : undefined
}

function resolveStatusLabel(status: ReportStatus): string {
  return STATUS_LABELS[status]
}

function resolveCounterpartyLabel(report: ReportRecord): string {
  if (activeFilter.value === 'initiated') {
    return report.current_recipient_label ?? report.target_label
  }
  if (activeFilter.value === 'history') {
    return report.target_label
  }
  return report.initiator_label
}

function resolveListTimestamp(report: ReportRecord): string {
  if (report.completed_at) {
    return formatDateTime(report.completed_at)
  }
  if (report.returned_at) {
    return formatDateTime(report.returned_at)
  }
  if (report.archived_at) {
    return formatDateTime(report.archived_at)
  }
  return formatDateTime(report.updated_at)
}

async function loadSnapshot(): Promise<void> {
  loading.value = true
  try {
    snapshot.value = await getReportCenterSnapshot()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

function handleFilterChange(value: ReportCenterFilter): void {
  const nextList =
    value === 'initiated' ? initiatedReports.value : value === 'history' ? historyReports.value : pendingReports.value
  const keepSelected = nextList.some((report) => report.id === selectedReportId.value)
  void router.replace({
    name: 'reports',
    query: buildRouteQuery({
      filter: value,
      selected: keepSelected ? selectedReportId.value : '',
    }),
  })
}

function handleSelectReport(reportId: string): void {
  void router.replace({
    name: 'reports',
    query: buildRouteQuery({ selected: reportId }),
  })
}

function openComposeDrawer(direction: ReportDirection | null = null): void {
  if (!canComposeReport.value) {
    return
  }
  composeInitialDirection.value = direction
  showComposeDrawer.value = true
}

async function handleReportCreated(): Promise<void> {
  await loadSnapshot()
  handleFilterChange('initiated')
}

async function handleAction(reportId: string, action: ReportActionOption): Promise<void> {
  actionKey.value = `${reportId}:${action.action}`
  try {
    await actReport(reportId, {
      action: action.action,
    })
    ElMessage.success(`${action.label}已提交`)
    await loadSnapshot()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    actionKey.value = ''
  }
}

function migrateLegacyQuery(): void {
  const rawTab = route.query.tab
  if (typeof rawTab !== 'string') {
    return
  }

  if (rawTab === 'upward' || rawTab === 'downward') {
    const direction = rawTab as ReportDirection
    const allowed =
      direction === 'upward' ? permissions.value.can_create_upward : permissions.value.can_create_downward
    if (allowed) {
      openComposeDrawer(direction)
    }
    void router.replace({ name: 'reports', query: buildRouteQuery({ filter: 'pending', selected: '' }) })
    return
  }

  if (rawTab === 'pending' || rawTab === 'initiated' || rawTab === 'history') {
    const nextSelected = typeof route.query.selected === 'string' ? route.query.selected : ''
    void router.replace({
      name: 'reports',
      query: buildRouteQuery({ filter: rawTab as ReportCenterFilter, selected: nextSelected }),
    })
  }
}

watch(
  () => route.query.tab,
  () => {
    if (snapshot.value) {
      migrateLegacyQuery()
    }
  },
)

onMounted(async () => {
  await loadSnapshot()
  migrateLegacyQuery()
})
</script>

<template>
  <div class="reports-page filum-page" data-testid="reports-view" v-loading="loading">
    <el-card shadow="never" class="filum-panel-card">
      <template #header>
        <div class="reports-page__header filum-page-header">
          <div class="filum-page-header__copy">
            <span class="filum-page-header__eyebrow">Collaboration</span>
            <strong class="filum-page-header__title">汇报中心</strong>
            <p class="reports-page__subtitle">
              待处理 {{ pendingReports.length }} · 我发起 {{ initiatedReports.length }} · 历史归档
              {{ historyReports.length }}
            </p>
          </div>
          <el-space wrap>
            <el-tag :type="canComposeReport ? 'success' : 'info'" effect="plain">
              {{ canComposeReport ? '可撰写汇报' : '暂无可发起链路' }}
            </el-tag>
            <el-button
              type="primary"
              :disabled="!canComposeReport"
              data-testid="reports-compose-button"
              @click="openComposeDrawer()"
            >
              撰写汇报
            </el-button>
          </el-space>
        </div>
      </template>

      <div class="reports-page__filters" data-testid="reports-filter-chips">
        <el-check-tag
          :checked="activeFilter === 'pending'"
          data-testid="reports-filter-pending"
          @click="handleFilterChange('pending')"
        >
          待处理
        </el-check-tag>
        <el-check-tag
          :checked="activeFilter === 'initiated'"
          data-testid="reports-filter-initiated"
          @click="handleFilterChange('initiated')"
        >
          我发起
        </el-check-tag>
        <el-check-tag
          :checked="activeFilter === 'history'"
          data-testid="reports-filter-history"
          @click="handleFilterChange('history')"
        >
          历史归档
        </el-check-tag>
      </div>
    </el-card>

    <div class="reports-page__master-detail">
      <el-card shadow="never" class="filum-panel-card reports-page__list-panel" data-testid="reports-list-panel">
        <template #header>
          <span v-if="activeFilter === 'pending'">待处理</span>
          <span v-else-if="activeFilter === 'initiated'">我发起</span>
          <span v-else>历史归档</span>
        </template>

        <el-empty v-if="filteredReports.length === 0" description="暂无汇报" />

        <div v-else class="reports-page__list">
          <button
            v-for="report in filteredReports"
            :key="report.id"
            type="button"
            class="reports-page__list-item"
            :class="{ 'reports-page__list-item--selected': report.id === selectedReportId }"
            data-testid="reports-list-item"
            @click="handleSelectReport(report.id)"
          >
            <span class="reports-page__status-dot" :class="STATUS_DOT_CLASS[report.status]" />
            <div class="reports-page__list-item-body">
              <div class="reports-page__list-item-title">{{ report.title }}</div>
              <div class="reports-page__list-item-meta">
                <span>{{ resolveCounterpartyLabel(report) }}</span>
                <span>{{ resolveStatusLabel(report.status) }}</span>
                <span>{{ resolveListTimestamp(report) }}</span>
              </div>
            </div>
          </button>
        </div>
      </el-card>

      <ReportDetailPanel
        class="reports-page__detail"
        :report="selectedReport"
        :action-key="actionKey"
        @action="handleAction"
      />
    </div>

    <ReportComposeDrawer
      v-model="showComposeDrawer"
      :can-create-upward="permissions.can_create_upward"
      :can-create-downward="permissions.can_create_downward"
      :upward-target-options="upwardTargetOptions"
      :downward-target-options="downwardTargetOptions"
      :workflow-definition-options="workflowDefinitionOptions"
      :initial-direction="composeInitialDirection"
      @created="handleReportCreated"
    />
  </div>
</template>

<style scoped>
.reports-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.reports-page__header {
  align-items: flex-start;
}

.reports-page__subtitle {
  margin: 6px 0 0;
  color: var(--filum-text-secondary);
  font-size: 13px;
}

.reports-page__filters {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.reports-page__master-detail {
  display: grid;
  grid-template-columns: minmax(280px, 36%) minmax(0, 1fr);
  gap: 20px;
  align-items: start;
}

.reports-page__list-panel {
  min-width: 0;
}

.reports-page__detail {
  min-width: 0;
}

.reports-page__list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.reports-page__list-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  width: 100%;
  padding: 12px 14px;
  border: 1px solid var(--filum-border-strong);
  border-radius: 12px;
  background: #fff;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
}

.reports-page__list-item:hover {
  border-color: rgba(37, 99, 235, 0.35);
  background: #f8faff;
}

.reports-page__list-item--selected {
  border-color: var(--el-color-primary);
  background: rgba(37, 99, 235, 0.06);
}

.reports-page__status-dot {
  width: 10px;
  height: 10px;
  margin-top: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.reports-page__status-dot--in-progress {
  background: var(--el-color-warning);
}

.reports-page__status-dot--completed {
  background: var(--el-color-success);
}

.reports-page__status-dot--returned {
  background: var(--el-color-danger);
}

.reports-page__status-dot--archived {
  background: var(--el-color-info);
}

.reports-page__list-item-body {
  min-width: 0;
  flex: 1;
}

.reports-page__list-item-title {
  font-size: 15px;
  font-weight: 600;
  line-height: 1.4;
}

.reports-page__list-item-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 6px;
  color: var(--filum-text-secondary);
  font-size: 12px;
}

@media (max-width: 1080px) {
  .reports-page__master-detail {
    grid-template-columns: 1fr;
  }
}
</style>
