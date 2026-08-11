<script setup lang="ts">
import { computed, ref } from 'vue'

import BatchRunDashboard from '@/components/workflow/BatchRunDashboard.vue'
import CapturePanel from '@/components/workflow/CapturePanel.vue'
import TemplateAggregatePanel from '@/components/workflow/TemplateAggregatePanel.vue'
import WorkflowCaptureProgressPanel from '@/components/workflow/VideoCaptureProgressPanel.vue'
import WorkflowDeliverablePanel from '@/components/workflow/VideoProductionPanel.vue'
import WorkflowTrackingPanel from '@/components/workflow/VideoTrackingPanel.vue'
import { resolveActiveStepTaskId } from '@/domain/workflow-graph/activeStepTask'
import {
  usesWorkflowCapabilityLayout,
  type TaskDetailProfile,
} from '@/domain/task-detail/profile'
import type { Task, User, WorkflowGraphInstanceDetail } from '@/types/api'
import type { WorkflowRunEventItem } from '@/types/workflowVideo'
import { formatDateTime } from '@/utils/formatters'
import { resolveAggregateMode } from '@/utils/workflowVideoSchema'

type WorkflowDeliverablePanelExpose = {
  submit: () => void
  submitting: boolean
}

const props = defineProps<{
  task: Task
  graphInstance: WorkflowGraphInstanceDetail | null
  profile: TaskDetailProfile
  users: User[]
  canManageReject: boolean
  currentUserId?: string | null
  runEvents: WorkflowRunEventItem[]
  compactTelemetry: boolean
}>()

const emit = defineEmits<{
  reload: []
  selectTask: [taskId: string]
}>()

const deliverablePanelRef = ref<WorkflowDeliverablePanelExpose | null>(null)
const batchAggregateMode = computed(() => resolveAggregateMode(props.graphInstance?.context))
const usesWorkflowLayout = computed(() => usesWorkflowCapabilityLayout(props.profile))
const showCaptureProgressPanel = computed(
  () =>
    props.profile.surface === 'collection'
    && props.profile.features.capture_progress === true
    && props.graphInstance !== null
    && batchAggregateMode.value === 'batch',
)
const showWorkflowTrackingPanel = computed(
  () => props.profile.features.tracking === true && props.graphInstance !== null,
)
const showBatchRunDashboard = computed(
  () => props.profile.features.run_dashboard === true && props.graphInstance !== null,
)
const showCapturePanel = computed(() => props.profile.surface === 'structured_form')
const showWorkflowAggregatePanel = computed(
  () =>
    props.profile.surface === 'collection'
    && props.profile.features.aggregate === true
    && batchAggregateMode.value === 'batch',
)
const deliverablePanelMode = computed((): 'single' | 'multi' | 'platform' => {
  if (props.profile.variant === 'multi') return 'multi'
  if (props.profile.variant === 'platform') return 'platform'
  return 'single'
})
const showWorkflowDeliverablePanel = computed(
  () => props.profile.surface === 'deliverable' && props.profile.submitMode === 'file',
)
const activeStepTaskId = computed(() =>
  resolveActiveStepTaskId(props.graphInstance, {
    preferAssigneeUserId: props.currentUserId ?? null,
  }),
)
const showProductionRootStepRouter = computed(() => {
  const metadata = (props.task.extra_metadata as Record<string, unknown> | undefined) ?? {}
  return (
    props.task.source_type === 'template'
    && metadata.workflow_graph_root_task === true
    && props.profile.rootVisibility === 'hidden_for_non_management'
    && props.graphInstance !== null
    && activeStepTaskId.value !== null
    && activeStepTaskId.value !== props.task.id
  )
})
const usesCompactRunEventCards = computed(
  () => props.compactTelemetry || usesWorkflowLayout.value,
)
const visibleRunEvents = computed(() =>
  usesCompactRunEventCards.value ? props.runEvents.slice(0, 3) : props.runEvents,
)
const submitting = computed(() => deliverablePanelRef.value?.submitting ?? false)

const EVENT_TYPE_LABELS: Record<string, string> = {
  run_instantiated: '运行已创建',
  capture_submitted: '采集已提交',
  aggregate_confirmed: '汇总已确认',
  production_run_forked: '已 fork 制作子流',
  capture_rejected: '采集已打回',
  production_deep_reject: '制作节点打回',
  node_completed: '节点已完成',
}

function resolveRunEventLabel(eventType: string): string {
  return EVENT_TYPE_LABELS[eventType] ?? eventType
}

function submit(): void {
  deliverablePanelRef.value?.submit()
}

defineExpose({ submit, submitting })
</script>

<template>
  <WorkflowTrackingPanel
    v-if="showWorkflowTrackingPanel && graphInstance"
    :graph-instance="graphInstance"
    :users="users"
    :can-manage-reject="canManageReject"
    @dispatched="emit('reload')"
    @rejected="emit('reload')"
  />

  <el-alert
    v-if="showProductionRootStepRouter"
    type="info"
    :closable="false"
    show-icon
    class="workflow-panel"
    data-testid="production-root-step-router"
  >
    <template #title>这是制作 Run 跟踪壳层</template>
    请打开当前步骤任务提交脚本、配音等交付物。
    <div style="margin-top: 8px">
      <el-button type="primary" size="small" @click="emit('selectTask', activeStepTaskId!)">
        打开当前步骤任务
      </el-button>
    </div>
  </el-alert>

  <BatchRunDashboard
    v-if="showBatchRunDashboard && graphInstance"
    :graph-instance="graphInstance"
    @open-task="(taskId: string) => emit('selectTask', taskId)"
  />

  <WorkflowCaptureProgressPanel
    v-if="showCaptureProgressPanel && graphInstance"
    :graph-instance="graphInstance"
  />

  <CapturePanel
    v-if="showCapturePanel"
    :task="task"
    :graph-instance="graphInstance"
    @submitted="emit('reload')"
  />

  <WorkflowDeliverablePanel
    v-if="showWorkflowDeliverablePanel"
    ref="deliverablePanelRef"
    :task="task"
    :mode="deliverablePanelMode"
    @submitted="emit('reload')"
  />

  <TemplateAggregatePanel
    v-if="showWorkflowAggregatePanel"
    :task="task"
    :graph-instance="graphInstance"
    :users="users"
    :can-manage-reject="canManageReject"
    @finalized="emit('reload')"
    @rejected="emit('reload')"
  />

  <el-card
    v-if="runEvents.length > 0"
    shadow="never"
    class="run-events"
    :data-testid="usesCompactRunEventCards ? 'workflow-run-events-compact' : 'workflow-run-events'"
  >
    <template #header>
      <div class="run-events__header">
        <strong>{{ usesCompactRunEventCards ? '最近事件' : '运行事件' }}</strong>
        <router-link
          v-if="compactTelemetry"
          :to="{ name: 'task-center', query: { filter: 'stats', selected: task.id } }"
        >
          在任务统计中查看
        </router-link>
      </div>
    </template>
    <el-timeline>
      <el-timeline-item
        v-for="event in visibleRunEvents"
        :key="event.id"
        :timestamp="formatDateTime(event.created_at)"
      >
        {{ resolveRunEventLabel(event.event_type) }}
        <span v-if="!usesCompactRunEventCards && typeof event.payload.reason === 'string'">
          — {{ event.payload.reason }}
        </span>
      </el-timeline-item>
    </el-timeline>
  </el-card>
</template>

<style scoped>
.run-events {
  margin-top: 16px;
}

.run-events__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
</style>
