<script setup lang="ts">
import type { WorkflowGraphInstanceDetail, WorkflowNodeInstanceSummary } from '@/types/api'

defineProps<{
  graphInstance: WorkflowGraphInstanceDetail
  compact: boolean
}>()

function resolveNodeEngineStateLabel(state: WorkflowNodeInstanceSummary['engine_state']): string {
  const labels: Record<string, string> = {
    pending: '待激活',
    activated: '进行中',
    acknowledged: '已确认',
    completed: '已完成',
    terminated: '已终止',
    skipped: '已跳过',
    failed: '失败',
    suspended: '已挂起',
  }
  return labels[state] ?? state
}

function resolveNodeEngineStateTagType(
  state: WorkflowNodeInstanceSummary['engine_state'],
): 'info' | 'primary' | 'success' | 'danger' | 'warning' {
  if (state === 'completed') return 'success'
  if (state === 'activated' || state === 'acknowledged') return 'primary'
  if (state === 'terminated' || state === 'failed') return 'danger'
  if (state === 'suspended') return 'warning'
  return 'info'
}

function formatNodeDuration(node: WorkflowNodeInstanceSummary): string {
  if (!node.activated_at) return '—'
  const end = node.completed_at ?? node.terminated_at
  if (!end) return '进行中'
  const ms = new Date(end).getTime() - new Date(node.activated_at).getTime()
  const minutes = Math.floor(ms / 60000)
  if (minutes < 60) return `${minutes} 分钟`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} 小时`
  return `${Math.floor(hours / 24)} 天`
}
</script>

<template>
  <el-collapse v-if="compact" data-testid="task-detail-graph-collapse">
    <el-collapse-item title="工作流节点追踪（完整日志见任务统计）" name="graph-nodes">
      <el-space direction="vertical" fill class="telemetry__nodes" data-testid="tasks-graph-panel">
        <el-card
          v-for="node in graphInstance.node_instances"
          :key="node.id"
          shadow="never"
          class="telemetry__node-card"
        >
          <div class="telemetry__node-header">
            <div class="telemetry__node-title">
              <strong>{{ node.title }}</strong>
              <el-tag v-if="node.iteration > 1" size="small" type="warning" effect="dark">
                V{{ node.iteration }}
              </el-tag>
            </div>
            <el-tag
              :type="resolveNodeEngineStateTagType(node.engine_state)"
              effect="plain"
              size="small"
            >
              {{ resolveNodeEngineStateLabel(node.engine_state) }}
            </el-tag>
          </div>
          <p class="telemetry__node-meta">耗时：{{ formatNodeDuration(node) }}</p>
          <p
            v-if="node.engine_state === 'terminated'"
            class="telemetry__node-meta telemetry__node-meta--terminated"
          >
            已被系统终止（or-join 撤权或深度打回）
          </p>
        </el-card>
      </el-space>
    </el-collapse-item>
  </el-collapse>

  <template v-else>
    <el-divider>工作流节点追踪</el-divider>
    <el-space direction="vertical" fill class="telemetry__nodes" data-testid="tasks-graph-panel">
      <el-card
        v-for="node in graphInstance.node_instances"
        :key="node.id"
        shadow="never"
        class="telemetry__node-card"
      >
        <div class="telemetry__node-header">
          <div class="telemetry__node-title">
            <strong>{{ node.title }}</strong>
            <el-tag v-if="node.iteration > 1" size="small" type="warning" effect="dark">
              V{{ node.iteration }}
            </el-tag>
          </div>
          <el-tag
            :type="resolveNodeEngineStateTagType(node.engine_state)"
            effect="plain"
            size="small"
          >
            {{ resolveNodeEngineStateLabel(node.engine_state) }}
          </el-tag>
        </div>
        <p class="telemetry__node-meta">耗时：{{ formatNodeDuration(node) }}</p>
        <p
          v-if="node.engine_state === 'terminated'"
          class="telemetry__node-meta telemetry__node-meta--terminated"
        >
          已被系统终止（or-join 撤权或深度打回）
        </p>
      </el-card>
    </el-space>
  </template>
</template>

<style scoped>
.telemetry__nodes {
  width: 100%;
}

.telemetry__node-card {
  margin-bottom: 8px;
}

.telemetry__node-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.telemetry__node-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.telemetry__node-meta {
  margin: 4px 0 0;
  color: #909399;
  font-size: 13px;
}

.telemetry__node-meta--terminated {
  color: #f56c6c;
}
</style>
