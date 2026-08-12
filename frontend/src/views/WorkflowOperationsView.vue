<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import {
  getWorkflowOperationsDashboard,
  operateWorkflowNode,
  replayWorkflowOutbox,
  searchWorkflowTraces,
  updateWorkflowIncident,
} from '@/api/workflow-operations'
import type {
  WorkflowIncidentOperation,
  WorkflowOperationsDashboard,
  WorkflowOutboxOperation,
  WorkflowTrace,
  WorkflowTraceFilters,
} from '@/types/workflowOperations'
import { getErrorMessage } from '@/utils/errors'

const loading = ref(false)
const actionLoading = ref(false)
const dashboard = ref<WorkflowOperationsDashboard | null>(null)
const traces = ref<WorkflowTrace[]>([])
const traceLoading = ref(false)
const traceType = ref<keyof WorkflowTraceFilters>('request_id')
const traceQuery = ref('')
const stalledMinutes = ref(30)
const nodeAction = reactive({
  nodeInstanceId: '',
  action: 'retry' as 'retry' | 'suspend' | 'resume',
  reason: '',
})

const metrics = computed(() => dashboard.value?.metrics)
const runActive = computed(() => metrics.value?.runs.active ?? 0)
const runFailed = computed(() => metrics.value?.runs.failed ?? 0)

function formatAge(seconds: number | null | undefined): string {
  if (!seconds) return '刚刚'
  if (seconds < 60) return `${seconds} 秒`
  if (seconds < 3600) return `${Math.floor(seconds / 60)} 分钟`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} 小时`
  return `${Math.floor(seconds / 86400)} 天`
}

function statusTag(status: string): 'success' | 'warning' | 'danger' | 'info' | 'primary' {
  if (['idle', 'dispatched', 'resolved'].includes(status)) return 'success'
  if (['failed', 'open', 'critical', 'error'].includes(status)) return 'danger'
  if (['running', 'retrying', 'warning'].includes(status)) return 'warning'
  return 'info'
}

async function loadDashboard(): Promise<void> {
  loading.value = true
  try {
    dashboard.value = await getWorkflowOperationsDashboard(stalledMinutes.value)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

async function handleReplay(item: WorkflowOutboxOperation): Promise<void> {
  try {
    const { value } = await ElMessageBox.prompt(
      '请输入人工重放原因。事件会回到重试队列，业务 payload 不会显示在此页面。',
      '重放 FAILED Outbox',
      {
        inputPattern: /^.{3,500}$/s,
        inputErrorMessage: '请输入 3–500 个字符',
        confirmButtonText: '确认重放',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
    actionLoading.value = true
    await replayWorkflowOutbox(item.id, value.trim())
    ElMessage.success('Outbox 事件已进入重试队列')
    await loadDashboard()
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(getErrorMessage(error))
  } finally {
    actionLoading.value = false
  }
}

async function handleIncident(
  item: WorkflowIncidentOperation,
  status: 'resolved' | 'ignored',
): Promise<void> {
  try {
    const label = status === 'resolved' ? '解决' : '忽略'
    const { value } = await ElMessageBox.prompt(`请输入${label}原因。`, `${label} Incident`, {
      inputPattern: /^.{3,500}$/s,
      inputErrorMessage: '请输入 3–500 个字符',
      confirmButtonText: `确认${label}`,
      cancelButtonText: '取消',
      type: 'warning',
    })
    actionLoading.value = true
    await updateWorkflowIncident(item.id, status, value.trim())
    ElMessage.success(`Incident 已${label}`)
    await loadDashboard()
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(getErrorMessage(error))
  } finally {
    actionLoading.value = false
  }
}

async function submitNodeAction(): Promise<void> {
  const nodeId = nodeAction.nodeInstanceId.trim()
  const reason = nodeAction.reason.trim()
  if (!nodeId || reason.length < 3) {
    ElMessage.warning('请填写节点实例 ID 和至少 3 个字符的原因')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确认对节点 ${nodeId} 执行 ${nodeAction.action}？该动作只调整运行时技术状态，不代办业务审批。`,
      '确认节点运维动作',
      { type: 'warning', confirmButtonText: '确认执行', cancelButtonText: '取消' },
    )
    actionLoading.value = true
    await operateWorkflowNode(nodeId, nodeAction.action, reason)
    ElMessage.success('节点运维动作已执行')
    nodeAction.reason = ''
    await loadDashboard()
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(getErrorMessage(error))
  } finally {
    actionLoading.value = false
  }
}

async function handleTraceSearch(): Promise<void> {
  const value = traceQuery.value.trim()
  traceLoading.value = true
  try {
    const filters: WorkflowTraceFilters = value ? { [traceType.value]: value } : {}
    traces.value = (await searchWorkflowTraces(filters)).items
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    traceLoading.value = false
  }
}

onMounted(() => {
  void loadDashboard()
  void handleTraceSearch()
})
</script>

<template>
  <div class="workflow-operations filum-page" data-testid="workflow-operations-view">
    <div class="filum-page-header workflow-operations__header">
      <div class="filum-page-header__copy">
        <span class="filum-page-header__eyebrow">Operations</span>
        <h1 class="filum-page-header__title">工作流运维</h1>
        <p>定位运行时异常、执行受控恢复并查看投影健康；这里不提供任何业务审批或交付权限。</p>
      </div>
      <div class="workflow-operations__refresh">
        <el-input-number v-model="stalledMinutes" :min="5" :max="1440" controls-position="right" />
        <span>分钟卡死阈值</span>
        <el-button :loading="loading" @click="loadDashboard">刷新</el-button>
      </div>
    </div>

    <div class="workflow-operations__metrics" v-loading="loading">
      <el-card shadow="never" class="filum-metric-card"><span>活跃 Run</span><strong>{{ runActive }}</strong></el-card>
      <el-card shadow="never" class="filum-metric-card"><span>失败 Run</span><strong>{{ runFailed }}</strong></el-card>
      <el-card shadow="never" class="filum-metric-card"><span>卡死 Run</span><strong>{{ metrics?.stalled_run_count ?? 0 }}</strong></el-card>
      <el-card shadow="never" class="filum-metric-card"><span>挂起节点</span><strong>{{ metrics?.suspended_node_count ?? 0 }}</strong></el-card>
      <el-card shadow="never" class="filum-metric-card"><span>Outbox 积压</span><strong>{{ metrics?.outbox_backlog_count ?? 0 }}</strong></el-card>
      <el-card shadow="never" class="filum-metric-card"><span>投影失败流</span><strong>{{ metrics?.projection_failed_stream_count ?? 0 }}</strong></el-card>
    </div>

    <el-card shadow="never" class="filum-panel-card" v-loading="loading">
      <template #header><strong>异常工作台</strong></template>
      <el-table :data="dashboard?.issues ?? []" empty-text="当前没有运行时异常">
        <el-table-column label="级别" width="90">
          <template #default="{ row }"><el-tag :type="statusTag(row.severity)">{{ row.severity }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="category" label="类型" width="150" />
        <el-table-column prop="title" label="对象" min-width="180" />
        <el-table-column prop="message" label="诊断" min-width="260" show-overflow-tooltip />
        <el-table-column label="持续" width="110">
          <template #default="{ row }">{{ formatAge(row.age_seconds) }}</template>
        </el-table-column>
        <el-table-column prop="instance_id" label="Run ID" min-width="220" show-overflow-tooltip />
        <el-table-column prop="node_instance_id" label="Node ID" min-width="220" show-overflow-tooltip />
      </el-table>
    </el-card>

    <div class="workflow-operations__two-column">
      <el-card shadow="never" class="filum-panel-card" v-loading="loading || actionLoading">
        <template #header><strong>FAILED Outbox</strong></template>
        <el-table :data="dashboard?.failed_outbox ?? []" empty-text="没有失败事件">
          <el-table-column prop="event_type" label="事件" min-width="150" />
          <el-table-column prop="attempt_count" label="次数" width="70" />
          <el-table-column prop="last_error" label="最后错误" min-width="180" show-overflow-tooltip />
          <el-table-column label="操作" width="90">
            <template #default="{ row }"><el-button link type="primary" @click="handleReplay(row)">重放</el-button></template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card shadow="never" class="filum-panel-card" v-loading="loading || actionLoading">
        <template #header><strong>Incident 处置</strong></template>
        <el-table :data="dashboard?.incidents ?? []" empty-text="没有 Incident">
          <el-table-column prop="category" label="类型" min-width="150" />
          <el-table-column label="状态" width="90">
            <template #default="{ row }"><el-tag :type="statusTag(row.status)">{{ row.status }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="occurrence_count" label="次数" width="70" />
          <el-table-column label="操作" width="130">
            <template #default="{ row }">
              <template v-if="row.status === 'open'">
                <el-button link type="success" @click="handleIncident(row, 'resolved')">解决</el-button>
                <el-button link @click="handleIncident(row, 'ignored')">忽略</el-button>
              </template>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>

    <el-card shadow="never" class="filum-panel-card" v-loading="loading">
      <template #header><strong>投影健康</strong></template>
      <el-table :data="dashboard?.projection_streams ?? []">
        <el-table-column prop="stream_name" label="数据流" min-width="190" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }"><el-tag :type="statusTag(row.status)">{{ row.status }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="processed_count" label="已处理" width="100" />
        <el-table-column prop="backlog_count" label="积压" width="90" />
        <el-table-column label="Lag" width="100">
          <template #default="{ row }">{{ formatAge(row.lag_seconds) }}</template>
        </el-table-column>
        <el-table-column prop="last_error" label="最后错误" min-width="220" show-overflow-tooltip />
      </el-table>
    </el-card>

    <el-card shadow="never" class="filum-panel-card">
      <template #header><strong>节点受控动作</strong></template>
      <el-form inline class="workflow-operations__node-form">
        <el-form-item label="Node ID"><el-input v-model="nodeAction.nodeInstanceId" placeholder="节点实例 UUID" /></el-form-item>
        <el-form-item label="动作">
          <el-select v-model="nodeAction.action" style="width: 130px">
            <el-option label="重试失败节点" value="retry" />
            <el-option label="人工挂起" value="suspend" />
            <el-option label="恢复人工挂起" value="resume" />
          </el-select>
        </el-form-item>
        <el-form-item label="原因"><el-input v-model="nodeAction.reason" placeholder="必填，写入审计" /></el-form-item>
        <el-button type="primary" :loading="actionLoading" @click="submitNodeAction">执行</el-button>
      </el-form>
    </el-card>

    <el-card shadow="never" class="filum-panel-card">
      <template #header><strong>统一 Trace</strong></template>
      <div class="workflow-operations__trace-search">
        <el-select v-model="traceType" style="width: 180px">
          <el-option label="Request ID" value="request_id" />
          <el-option label="Command ID" value="command_id" />
          <el-option label="Correlation ID" value="correlation_id" />
          <el-option label="Run ID" value="instance_id" />
          <el-option label="Node ID" value="node_instance_id" />
          <el-option label="Task ID" value="task_id" />
        </el-select>
        <el-input v-model="traceQuery" data-testid="workflow-trace-query" clearable placeholder="精确标识；留空显示最近事件" @keyup.enter="handleTraceSearch" />
        <el-button data-testid="workflow-trace-search" :loading="traceLoading" @click="handleTraceSearch">检索</el-button>
      </div>
      <el-table :data="traces" v-loading="traceLoading" empty-text="没有匹配事件">
        <el-table-column prop="occurred_at" label="时间" min-width="180" />
        <el-table-column prop="event_type" label="事件" min-width="180" />
        <el-table-column prop="request_id" label="Request" min-width="180" show-overflow-tooltip />
        <el-table-column prop="command_id" label="Command" min-width="180" show-overflow-tooltip />
        <el-table-column prop="correlation_id" label="Correlation" min-width="220" show-overflow-tooltip />
        <el-table-column prop="instance_id" label="Run" min-width="220" show-overflow-tooltip />
        <el-table-column label="Payload 字段" min-width="180">
          <template #default="{ row }">{{ row.payload_keys.join(', ') || '—' }}</template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.workflow-operations {
  display: grid;
  gap: 16px;
}

.workflow-operations__header,
.workflow-operations__refresh,
.workflow-operations__trace-search {
  display: flex;
  align-items: center;
  gap: 12px;
}

.workflow-operations__header {
  justify-content: space-between;
}

.workflow-operations__header p {
  margin: 6px 0 0;
  color: var(--el-text-color-secondary);
}

.workflow-operations__metrics {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 12px;
}

.workflow-operations__metrics :deep(.el-card__body) {
  display: grid;
  gap: 8px;
}

.workflow-operations__metrics strong {
  font-size: 26px;
}

.workflow-operations__two-column {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.workflow-operations__node-form :deep(.el-input) {
  width: 280px;
}

.workflow-operations__trace-search .el-input {
  flex: 1;
}

@media (max-width: 1100px) {
  .workflow-operations__metrics { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .workflow-operations__two-column { grid-template-columns: 1fr; }
}

@media (max-width: 720px) {
  .workflow-operations__header,
  .workflow-operations__refresh,
  .workflow-operations__trace-search { align-items: stretch; flex-direction: column; }
  .workflow-operations__metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
