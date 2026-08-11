<script setup lang="ts">
import AttachmentActions from '@/components/attachments/AttachmentActions.vue'
import { resolveStatusLabel } from '@/components/task-detail/task-detail-labels'
import type { TaskActivityEntry } from '@/types/api'
import { formatDateTime } from '@/utils/formatters'

defineProps<{
  entries: TaskActivityEntry[]
  resolveUserLabel: (userId: string, preferredLabel?: string | null) => string
}>()

function renderLogSummary(entry: TaskActivityEntry): string {
  const log = entry.log
  if (!log) {
    return ''
  }

  const detailAction = typeof log.detail.action === 'string' ? log.detail.action : null
  if (detailAction === 'submit_deliverable') {
    return '提交了交付物，等待验收'
  }
  if (detailAction === 'assigned') {
    return '发布了任务，等待执行人确认'
  }
  if (detailAction === 'accepted') {
    return '接受了任务，等待开工'
  }
  if (detailAction === 'rejected') {
    return `退回协商：${String(log.detail.reason ?? '请重新确认任务目标')}`
  }
  if (detailAction === 'delegated') {
    return `转办了任务：${String(log.detail.reason ?? '请由更合适的人继续处理')}`
  }
  if (detailAction === 'approve_completion') {
    const qualityScore = log.detail.quality_score
    return typeof qualityScore === 'number'
      ? `完成交付已通过验收，质量 ${qualityScore}/5`
      : '完成交付已通过验收'
  }
  if (detailAction === 'return_for_rework') {
    return `打回返工：${String(log.detail.comment ?? '请补充修改')}`
  }

  switch (log.action_type) {
    case 'created':
      return '创建了任务'
    case 'assigned':
      return '更新了执行人'
    case 'status_changed':
      return `状态从 ${resolveStatusLabel(log.from_status ?? 'todo')} 变更为 ${resolveStatusLabel(log.to_status ?? 'todo')}`
    case 'commented':
      return '添加了评论'
    case 'attachment_added':
      return `添加了附件：${String(log.detail.filename ?? '未命名文件')}`
    case 'due_date_changed':
      return '更新了截止时间'
    case 'closed':
      return '关闭了任务'
    default:
      return '更新了任务'
  }
}
</script>

<template>
  <div data-testid="task-detail-activity-timeline">
    <el-empty v-if="entries.length === 0" description="暂无活动记录" />

    <el-timeline v-else>
      <el-timeline-item
        v-for="entry in entries"
        :key="`${entry.entry_type}-${entry.created_at}`"
        :timestamp="formatDateTime(entry.created_at)"
        placement="top"
      >
        <el-card shadow="never">
          <template v-if="entry.comment">
            <div class="timeline__header">
              <div>
                <strong>
                  {{ resolveUserLabel(entry.comment.user_id, entry.comment.author_label) }}
                </strong>
                <el-tag
                  v-if="entry.comment.is_internal"
                  type="warning"
                  effect="plain"
                  class="timeline__inline-tag"
                >
                  内部备注
                </el-tag>
              </div>
              <el-tag type="primary" effect="plain">评论</el-tag>
            </div>
            <p class="timeline__text">{{ entry.comment.content }}</p>
            <div v-if="entry.comment.attachments.length > 0" class="timeline__attachments">
              <div
                v-for="attachment in entry.comment.attachments"
                :key="attachment.id"
                class="timeline__attachment-row"
              >
                <span>{{ attachment.original_filename }}</span>
                <AttachmentActions :attachment="attachment" />
              </div>
            </div>
          </template>

          <template v-else-if="entry.log">
            <div class="timeline__header">
              <strong>{{ resolveUserLabel(entry.log.operator_id, entry.log.operator_label) }}</strong>
              <el-tag effect="plain">日志</el-tag>
            </div>
            <p class="timeline__text">{{ renderLogSummary(entry) }}</p>
          </template>
        </el-card>
      </el-timeline-item>
    </el-timeline>
  </div>
</template>

<style scoped>
.timeline__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.timeline__text {
  margin: 0;
  color: #606266;
}

.timeline__inline-tag {
  margin-left: 8px;
}

.timeline__attachments {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 8px;
}

.timeline__attachment-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
</style>
