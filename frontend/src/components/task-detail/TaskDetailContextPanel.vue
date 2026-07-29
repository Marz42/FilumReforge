<script setup lang="ts">
import type { TaskDetailProfile } from '@/domain/task-detail/profile'
import type { Task } from '@/types/api'
import { formatDateTime } from '@/utils/formatters'

defineProps<{
  task: Task
  profile: TaskDetailProfile
  handshakeStateLabel: string
  isGraphHandshakeTask: boolean
  workflowNodeIteration: number
  workflowDeepRejectionReason: string | null
  latestRejectReason: string
  latestDelegateReason: string
  latestDeliverableSummary: string
  latestDeliverableSubmittedAt: string | null
  latestReviewQualityScore: number | null
  reworkCount: number
  latestReworkReason: string
  graphParentInstanceId: string | null
  graphRunKind: string
  resolveDepartmentName: (departmentId: string | null) => string
  resolveUserLabel: (userId: string, preferredLabel?: string | null) => string
}>()
</script>

<template>
  <section class="task-detail-context" data-testid="task-detail-context-panel">
    <div class="task-detail-context__header">
      <strong>协同信息</strong>
      <span>交付、协商与返工记录摘要</span>
    </div>
    <el-descriptions :column="2" border>
      <el-descriptions-item label="执行人">
        {{ resolveUserLabel(task.assignee_id, task.assignee_label) }}
      </el-descriptions-item>
      <el-descriptions-item label="所属部门">
        {{ resolveDepartmentName(task.department_id) }}
      </el-descriptions-item>
      <el-descriptions-item v-if="!profile.hideHandshakeFields" label="握手状态">
        {{ handshakeStateLabel }}
      </el-descriptions-item>
      <el-descriptions-item
        v-if="!profile.hideHandshakeFields && isGraphHandshakeTask && workflowNodeIteration > 1"
        label="迭代版本"
      >
        V{{ workflowNodeIteration }}（系统深度打回重放）
      </el-descriptions-item>
      <el-descriptions-item
        v-if="isGraphHandshakeTask && workflowDeepRejectionReason"
        label="打回原因"
      >
        {{ workflowDeepRejectionReason }}
      </el-descriptions-item>
      <el-descriptions-item label="最近协商原因">
        {{ latestRejectReason }}
      </el-descriptions-item>
      <el-descriptions-item label="最近转办原因">
        {{ latestDelegateReason }}
      </el-descriptions-item>
      <el-descriptions-item label="最新交付说明">
        {{ latestDeliverableSummary }}
      </el-descriptions-item>
      <el-descriptions-item label="最近提交时间">
        {{ formatDateTime(latestDeliverableSubmittedAt) }}
      </el-descriptions-item>
      <el-descriptions-item label="完成质量评分">
        {{ latestReviewQualityScore ? `${latestReviewQualityScore}/5` : '—' }}
      </el-descriptions-item>
      <el-descriptions-item label="返工次数">
        {{ reworkCount }}
      </el-descriptions-item>
      <el-descriptions-item label="最近返工原因">
        {{ latestReworkReason }}
      </el-descriptions-item>
      <el-descriptions-item v-if="graphParentInstanceId" label="所属批次">
        实例 {{ graphParentInstanceId.slice(0, 8) }}…
      </el-descriptions-item>
      <el-descriptions-item v-if="graphRunKind" label="运行类型">
        {{
          graphRunKind === 'batch'
            ? '批次 Run'
            : graphRunKind === 'production'
              ? '制作 Run'
              : graphRunKind
        }}
      </el-descriptions-item>
    </el-descriptions>
  </section>
</template>

<style scoped>
.task-detail-context {
  margin-top: 18px;
}

.task-detail-context__header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.task-detail-context__header span {
  color: var(--filum-text-muted);
  font-size: 12px;
}
</style>
