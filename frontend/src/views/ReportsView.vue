<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'

import { actReport, createReport, getReportCenterSnapshot } from '@/api/report-center'
import type {
  ReportActionOption,
  ReportCenterSnapshot,
  ReportDirection,
  ReportRouteStatus,
  ReportStatus,
} from '@/types/api'
import { getErrorMessage } from '@/utils/errors'
import { formatDateTime } from '@/utils/formatters'

type ReportCenterTab = 'pending' | 'initiated' | 'history'

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

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const submittingDirection = ref<ReportDirection | null>(null)
const actionKey = ref('')
const snapshot = ref<ReportCenterSnapshot | null>(null)
const showCreateReportDialog = ref(false)
const createReportStep = ref<'pick' | 'form'>('pick')
const createReportMode = ref<ReportDirection | null>(null)

const upwardForm = reactive({
  target_user_id: '',
  title: '',
  content_md: '',
  workflow_definition_id: '',
})

const downwardForm = reactive({
  target_user_id: '',
  title: '',
  content_md: '',
  workflow_definition_id: '',
})

const activeTab = computed<ReportCenterTab>(() => normalizeTab(route.query.tab))
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

const canOpenCreateReportDialog = computed(
  () => permissions.value.can_create_upward || permissions.value.can_create_downward,
)

function normalizeTab(rawTab: unknown): ReportCenterTab {
  if (rawTab === 'pending' || rawTab === 'initiated' || rawTab === 'history') {
    return rawTab
  }
  return 'pending'
}

function handleTabChange(value: string): void {
  const nextTab = normalizeTab(value)
  void router.replace({
    name: 'reports',
    query: nextTab === 'pending' ? {} : { tab: nextTab },
  })
}

function resetForm(direction: ReportDirection): void {
  const form = direction === 'upward' ? upwardForm : downwardForm
  form.target_user_id =
    (direction === 'upward' ? upwardTargetOptions.value[0]?.user_id : downwardTargetOptions.value[0]?.user_id) ??
    ''
  form.title = ''
  form.content_md = ''
  form.workflow_definition_id = ''
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

async function loadSnapshot(): Promise<void> {
  loading.value = true
  try {
    snapshot.value = await getReportCenterSnapshot()
    if (!upwardForm.target_user_id && upwardTargetOptions.value.length > 0) {
      upwardForm.target_user_id = upwardTargetOptions.value[0]!.user_id
    }
    if (!downwardForm.target_user_id && downwardTargetOptions.value.length > 0) {
      downwardForm.target_user_id = downwardTargetOptions.value[0]!.user_id
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

function resetCreateReportDialogUi(): void {
  createReportStep.value = 'pick'
  createReportMode.value = null
}

function openCreateReportDialog(): void {
  resetCreateReportDialogUi()
  showCreateReportDialog.value = true
}

function selectCreateReportDirection(direction: ReportDirection): void {
  const allowed =
    direction === 'upward' ? permissions.value.can_create_upward : permissions.value.can_create_downward
  if (!allowed) {
    return
  }
  createReportMode.value = direction
  createReportStep.value = 'form'
}

function goCreateReportPickStep(): void {
  createReportStep.value = 'pick'
  createReportMode.value = null
}

function onCreateReportDialogClosed(): void {
  resetCreateReportDialogUi()
}

async function maybeOpenCreateReportFromRouteQuery(): Promise<void> {
  const raw = route.query.tab
  if (raw !== 'upward' && raw !== 'downward') {
    return
  }
  if (!snapshot.value) {
    await loadSnapshot()
  }
  const direction = raw as ReportDirection
  const allowed =
    direction === 'upward' ? permissions.value.can_create_upward : permissions.value.can_create_downward
  if (!allowed) {
    await router.replace({ name: 'reports', query: {} })
    return
  }
  createReportMode.value = direction
  createReportStep.value = 'form'
  showCreateReportDialog.value = true
  await router.replace({ name: 'reports', query: {} })
}

async function handleCreate(direction: ReportDirection): Promise<void> {
  const form = direction === 'upward' ? upwardForm : downwardForm
  if (!form.target_user_id) {
    ElMessage.warning('请选择目标对象')
    return
  }
  if (!form.title.trim()) {
    ElMessage.warning('请输入主题')
    return
  }
  if (!form.content_md.trim()) {
    ElMessage.warning('请输入内容')
    return
  }

  submittingDirection.value = direction
  try {
    await createReport({
      direction,
      target_user_id: form.target_user_id,
      title: form.title.trim(),
      content_md: form.content_md.trim(),
      workflow_definition_id: form.workflow_definition_id || null,
    })
    ElMessage.success(direction === 'upward' ? '汇报已发起' : '传达已发起')
    resetForm(direction)
    await loadSnapshot()
    handleTabChange('initiated')
    showCreateReportDialog.value = false
    resetCreateReportDialogUi()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    submittingDirection.value = null
  }
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

function isActionLoading(reportId: string, action: string): boolean {
  return actionKey.value === `${reportId}:${action}`
}

watch(
  () => route.query.tab,
  () => {
    void maybeOpenCreateReportFromRouteQuery()
  },
)

onMounted(async () => {
  await loadSnapshot()
  await maybeOpenCreateReportFromRouteQuery()
})
</script>

<template>
  <div class="page reports-page filum-page" v-loading="loading">
    <el-row :gutter="16" class="reports-page__summary">
      <el-col :xs="24" :md="8">
        <el-card shadow="never" class="filum-metric-card">
          <div class="reports-page__metric-label">待处理</div>
          <div class="reports-page__metric-value">{{ pendingReports.length }}</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="8">
        <el-card shadow="never" class="filum-metric-card">
          <div class="reports-page__metric-label">我发起的</div>
          <div class="reports-page__metric-value">{{ initiatedReports.length }}</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="8">
        <el-card shadow="never" class="filum-metric-card">
          <div class="reports-page__metric-label">历史归档</div>
          <div class="reports-page__metric-value">{{ historyReports.length }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="filum-panel-card">
      <template #header>
        <div class="reports-page__header filum-page-header">
          <div class="filum-page-header__copy">
            <span class="filum-page-header__eyebrow">Collaboration</span>
            <strong class="filum-page-header__title">汇报中心</strong>
            <p class="reports-page__subtitle">
              查看待处理与我发起的汇报；通过「发起汇报」统一入口选择向上汇报或向下传达。
            </p>
          </div>
          <el-space wrap>
            <el-tag :type="canOpenCreateReportDialog ? 'success' : 'info'" effect="plain">
              {{ canOpenCreateReportDialog ? '可发起汇报' : '暂无可发起链路' }}
            </el-tag>
            <el-button type="primary" data-testid="reports-open-create" @click="openCreateReportDialog">
              发起汇报
            </el-button>
          </el-space>
        </div>
      </template>
      <el-tabs :model-value="activeTab" @tab-change="handleTabChange">
        <el-tab-pane label="待处理" name="pending">
          <el-empty v-if="pendingReports.length === 0" description="暂无待处理汇报" />
          <div v-else class="reports-page__list">
            <el-card
              v-for="report in pendingReports"
              :key="report.id"
              shadow="hover"
              :class="{ 'reports-page__card--selected': report.id === selectedReportId }"
            >
              <template #header>
                <div class="reports-page__card-header">
                  <div>
                    <div class="reports-page__title">{{ report.title }}</div>
                    <div class="reports-page__subtitle">
                      {{ resolveDirectionLabel(report.direction) }} · 发起人 {{ report.initiator_label }}
                    </div>
                  </div>
                  <el-space>
                    <el-tag :type="STATUS_TAG_TYPES[report.status]">{{ resolveStatusLabel(report.status) }}</el-tag>
                    <el-tag type="info">{{ report.current_recipient_label ?? '已结束' }}</el-tag>
                  </el-space>
                </div>
              </template>

              <div class="reports-page__content">{{ report.content_md }}</div>
              <div class="reports-page__meta">
                <span>目标：{{ report.target_label }}</span>
                <span>创建时间：{{ formatDateTime(report.created_at) }}</span>
                <span v-if="report.workflow_definition_name">挂接审批：{{ report.workflow_definition_name }}</span>
              </div>

              <el-timeline>
                <el-timeline-item
                  v-for="routeItem in report.routes"
                  :key="routeItem.id"
                  :timestamp="routeItem.acted_at ? formatDateTime(routeItem.acted_at) : routeItem.activated_at ? formatDateTime(routeItem.activated_at) : ''"
                >
                  <div class="reports-page__route-line">
                    {{ routeItem.sequence_no }}. {{ routeItem.sender_label }} -> {{ routeItem.recipient_label }}
                    <span v-if="routeItem.assigned_label && routeItem.assigned_label !== routeItem.recipient_label">
                      （代理：{{ routeItem.assigned_label }}）
                    </span>
                    · {{ resolveRouteStatusLabel(routeItem.status) }}
                  </div>
                  <div v-if="routeItem.note" class="reports-page__route-note">{{ routeItem.note }}</div>
                </el-timeline-item>
              </el-timeline>

              <el-space>
                <el-button
                  v-for="action in report.available_actions"
                  :key="action.action"
                  size="small"
                  :type="action.button_type"
                  :loading="isActionLoading(report.id, action.action)"
                  @click="handleAction(report.id, action)"
                >
                  {{ action.label }}
                </el-button>
              </el-space>
            </el-card>
          </div>
        </el-tab-pane>

        <el-tab-pane label="我发起" name="initiated">
          <el-empty v-if="initiatedReports.length === 0" description="暂无流转中的汇报" />
          <div v-else class="reports-page__list">
            <el-card
              v-for="report in initiatedReports"
              :key="report.id"
              shadow="hover"
              :class="{ 'reports-page__card--selected': report.id === selectedReportId }"
            >
              <template #header>
                <div class="reports-page__card-header">
                  <div>
                    <div class="reports-page__title">{{ report.title }}</div>
                    <div class="reports-page__subtitle">
                      {{ resolveDirectionLabel(report.direction) }} · 当前处理人 {{ report.current_recipient_label ?? '已结束' }}
                    </div>
                  </div>
                  <el-tag :type="STATUS_TAG_TYPES[report.status]">{{ resolveStatusLabel(report.status) }}</el-tag>
                </div>
              </template>

              <div class="reports-page__content">{{ report.content_md }}</div>
              <div class="reports-page__meta">
                <span>目标：{{ report.target_label }}</span>
                <span>创建时间：{{ formatDateTime(report.created_at) }}</span>
              </div>

              <el-timeline>
                <el-timeline-item v-for="routeItem in report.routes" :key="routeItem.id">
                  <div class="reports-page__route-line">
                    {{ routeItem.sequence_no }}. {{ routeItem.sender_label }} -> {{ routeItem.recipient_label }}
                    <span v-if="routeItem.assigned_label && routeItem.assigned_label !== routeItem.recipient_label">
                      （代理：{{ routeItem.assigned_label }}）
                    </span>
                    · {{ resolveRouteStatusLabel(routeItem.status) }}
                  </div>
                </el-timeline-item>
              </el-timeline>
            </el-card>
          </div>
        </el-tab-pane>

        <el-tab-pane label="历史归档" name="history">
          <el-empty v-if="historyReports.length === 0" description="暂无历史汇报" />
          <div v-else class="reports-page__list">
            <el-card
              v-for="report in historyReports"
              :key="report.id"
              shadow="hover"
              :class="{ 'reports-page__card--selected': report.id === selectedReportId }"
            >
              <template #header>
                <div class="reports-page__card-header">
                  <div>
                    <div class="reports-page__title">{{ report.title }}</div>
                    <div class="reports-page__subtitle">
                      {{ resolveDirectionLabel(report.direction) }} · 发起人 {{ report.initiator_label }}
                    </div>
                  </div>
                  <el-space>
                    <el-tag :type="STATUS_TAG_TYPES[report.status]">{{ resolveStatusLabel(report.status) }}</el-tag>
                    <el-button
                      v-for="action in report.available_actions"
                      :key="action.action"
                      size="small"
                      :type="action.button_type"
                      :loading="isActionLoading(report.id, action.action)"
                      @click="handleAction(report.id, action)"
                    >
                      {{ action.label }}
                    </el-button>
                  </el-space>
                </div>
              </template>

              <div class="reports-page__content">{{ report.content_md }}</div>
              <div class="reports-page__meta">
                <span>目标：{{ report.target_label }}</span>
                <span v-if="report.completed_at">完成时间：{{ formatDateTime(report.completed_at) }}</span>
                <span v-else-if="report.returned_at">退回时间：{{ formatDateTime(report.returned_at) }}</span>
                <span v-else-if="report.archived_at">归档时间：{{ formatDateTime(report.archived_at) }}</span>
              </div>
            </el-card>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <el-dialog
      v-model="showCreateReportDialog"
      title="发起汇报"
      width="560px"
      class="reports-page__create-dialog"
      data-testid="reports-create-dialog"
      :close-on-click-modal="false"
      append-to-body
      @closed="onCreateReportDialogClosed"
    >
      <div v-if="createReportStep === 'pick'" class="reports-page__pick">
        <p class="reports-page__pick-intro">请选择要发起的类型</p>
        <div class="reports-page__pick-actions">
          <el-button
            v-if="permissions.can_create_upward"
            type="primary"
            size="large"
            data-testid="reports-create-pick-upward"
            @click="selectCreateReportDirection('upward')"
          >
            发起向上汇报
          </el-button>
          <el-button
            v-if="permissions.can_create_downward"
            type="primary"
            size="large"
            plain
            data-testid="reports-create-pick-downward"
            @click="selectCreateReportDirection('downward')"
          >
            发起向下传达
          </el-button>
        </div>
        <el-empty
          v-if="!canOpenCreateReportDialog"
          description="当前账号暂无可用的逐级上报或逐级传达链路"
        />
      </div>

      <template v-else-if="createReportMode === 'upward'">
        <el-button text type="primary" class="reports-page__form-back" @click="goCreateReportPickStep">
          返回
        </el-button>
        <el-empty
          v-if="!permissions.can_create_upward"
          description="当前账号没有可用的逐级上报链路"
        />
        <el-form v-else label-position="top" data-testid="reports-create-form-upward">
          <el-form-item label="汇报对象">
            <el-select
              v-model="upwardForm.target_user_id"
              placeholder="请选择上级"
              class="reports-page__form-select"
              teleported
              :popper-options="{ strategy: 'fixed' }"
              popper-class="reports-page-select-popper"
            >
              <el-option
                v-for="option in upwardTargetOptions"
                :key="option.user_id"
                :label="`${option.label}（${option.path_labels.join(' -> ')}）`"
                :value="option.user_id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="主题">
            <el-input v-model="upwardForm.title" maxlength="255" show-word-limit />
          </el-form-item>
          <el-form-item label="内容">
            <el-input v-model="upwardForm.content_md" type="textarea" :rows="8" maxlength="4000" show-word-limit />
          </el-form-item>
          <el-form-item label="挂接审批流程（可选）">
            <el-select
              v-model="upwardForm.workflow_definition_id"
              clearable
              placeholder="不挂接审批"
              class="reports-page__form-select"
              teleported
              :popper-options="{ strategy: 'fixed' }"
              popper-class="reports-page-select-popper"
            >
              <el-option
                v-for="definition in workflowDefinitionOptions"
                :key="definition.id"
                :label="definition.name"
                :value="definition.id"
              />
            </el-select>
          </el-form-item>
          <el-button
            type="primary"
            :loading="submittingDirection === 'upward'"
            data-testid="reports-create-submit-upward"
            @click="handleCreate('upward')"
          >
            发起向上汇报
          </el-button>
        </el-form>
      </template>

      <template v-else-if="createReportMode === 'downward'">
        <el-button text type="primary" class="reports-page__form-back" @click="goCreateReportPickStep">
          返回
        </el-button>
        <el-empty
          v-if="!permissions.can_create_downward"
          description="当前账号没有可用的逐级传达链路"
        />
        <el-form v-else label-position="top" data-testid="reports-create-form-downward">
          <el-form-item label="传达对象">
            <el-select
              v-model="downwardForm.target_user_id"
              placeholder="请选择下级"
              class="reports-page__form-select"
              teleported
              :popper-options="{ strategy: 'fixed' }"
              popper-class="reports-page-select-popper"
            >
              <el-option
                v-for="option in downwardTargetOptions"
                :key="option.user_id"
                :label="`${option.label}（${option.path_labels.join(' -> ')}）`"
                :value="option.user_id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="主题">
            <el-input v-model="downwardForm.title" maxlength="255" show-word-limit />
          </el-form-item>
          <el-form-item label="内容">
            <el-input v-model="downwardForm.content_md" type="textarea" :rows="8" maxlength="4000" show-word-limit />
          </el-form-item>
          <el-form-item label="挂接审批流程（可选）">
            <el-select
              v-model="downwardForm.workflow_definition_id"
              clearable
              placeholder="不挂接审批"
              class="reports-page__form-select"
              teleported
              :popper-options="{ strategy: 'fixed' }"
              popper-class="reports-page-select-popper"
            >
              <el-option
                v-for="definition in workflowDefinitionOptions"
                :key="definition.id"
                :label="definition.name"
                :value="definition.id"
              />
            </el-select>
          </el-form-item>
          <el-button
            type="primary"
            :loading="submittingDirection === 'downward'"
            data-testid="reports-create-submit-downward"
            @click="handleCreate('downward')"
          >
            发起向下传达
          </el-button>
        </el-form>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.reports-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.reports-page__summary {
  margin-bottom: 0;
}

.reports-page__metric-label {
  color: var(--filum-text-secondary);
  font-size: 12px;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.reports-page__metric-value {
  font-size: 28px;
  font-weight: 600;
  margin-top: 8px;
  color: var(--filum-text);
}

.reports-page__list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.reports-page__card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.reports-page__title {
  font-size: 16px;
  font-weight: 600;
}

.reports-page__subtitle {
  margin-top: 4px;
  color: var(--filum-text-secondary);
  font-size: 13px;
}

.reports-page__content {
  white-space: pre-wrap;
  line-height: 1.6;
  margin-bottom: 12px;
}

.reports-page__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 12px;
  color: var(--filum-text-secondary);
  font-size: 13px;
}

.reports-page__route-line {
  line-height: 1.5;
}

.reports-page__card--selected {
  border-color: var(--el-color-primary);
}

.reports-page__route-note {
  margin-top: 4px;
  color: var(--filum-text-secondary);
  font-size: 13px;
}

.reports-page__header {
  align-items: flex-start;
}

.reports-page__subtitle {
  margin: 6px 0 0;
  color: var(--filum-text-secondary);
  font-size: 13px;
  line-height: 1.5;
}

.reports-page__pick {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 4px 0 8px;
}

.reports-page__pick-intro {
  margin: 0;
  color: var(--filum-text-secondary);
  font-size: 14px;
  text-align: center;
}

.reports-page__pick-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  justify-content: center;
}

.reports-page__form-back {
  padding: 0 0 8px;
}

.reports-page__form-select {
  width: 100%;
}
</style>

<style>
/* 弹窗 / 抽屉内下拉：fixed 策略 + 高层级，避免被遮挡或裁切 */
.reports-page-select-popper,
.task-center-view-select-popper {
  z-index: 6000 !important;
}
</style>
