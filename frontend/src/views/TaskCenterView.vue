<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'

import { createTask, createTaskComment } from '@/api/tasks'
import { createTaskMemo, deleteTaskMemo, getTaskCenterSnapshot, updateTaskMemo } from '@/api/task-center'
import TaskTemplatesView from '@/views/TaskTemplatesView.vue'
import TasksView from '@/views/TasksView.vue'
import type {
  TaskCenterHistoryItem,
  TaskCenterInboxItem,
  TaskCenterSnapshot,
  TaskCenterTrackingItem,
  TaskMemo,
  TaskPriority,
  TaskSourceType,
  TaskStatus,
} from '@/types/api'
import { getErrorMessage } from '@/utils/errors'
import { formatDateTime } from '@/utils/formatters'

type TaskCenterTab = 'templates' | 'inbox' | 'tracking' | 'memos'

const STATUS_LABELS: Record<TaskStatus, string> = {
  todo: '待办',
  doing: '进行中',
  review: '评审中',
  done: '已完成',
}

const STATUS_TAG_TYPES: Record<TaskStatus, '' | 'info' | 'warning' | 'success'> = {
  todo: 'info',
  doing: 'warning',
  review: '',
  done: 'success',
}

const PRIORITY_LABELS: Record<TaskPriority, string> = {
  low: '低',
  medium: '中',
  high: '高',
  urgent: '紧急',
}

const PRIORITY_TAG_TYPES: Record<TaskPriority, '' | 'info' | 'warning' | 'danger'> = {
  low: 'info',
  medium: '',
  high: 'warning',
  urgent: 'danger',
}

const SOURCE_TYPE_LABELS: Record<TaskSourceType, string> = {
  manual: '手动发布',
  template: '模板任务',
  event: '事件触发',
  ai: 'AI 工具',
}

const LEGACY_TAB_MAP: Record<string, TaskCenterTab> = {
  tasks: 'tracking',
  templates: 'templates',
  history: 'tracking',
  publish: 'inbox',
}

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const taskDrawerVisible = ref(false)
const publishSubmitting = ref(false)
const memoSubmitting = ref(false)
const snapshot = ref<TaskCenterSnapshot | null>(null)

const publishForm = reactive({
  title: '',
  description: '',
  assignee_user_id: '',
  department_id: '',
  priority: 'medium' as TaskPriority,
  due_date: null as Date | null,
})

const memoForm = reactive({
  memo_id: '',
  content: '',
  related_task_id: '',
  is_pinned: false,
})

const activeTab = computed<TaskCenterTab>(() => normalizeTab(route.query.tab))
const selectedTaskId = computed(() => (typeof route.query.selected === 'string' ? route.query.selected : ''))
const permissions = computed(() => {
  return (
    snapshot.value?.permissions ?? {
      can_manage_templates: false,
      can_publish_task: false,
    }
  )
})
const publishDepartmentOptions = computed(() => snapshot.value?.publish_department_options ?? [])
const publishUserOptions = computed(() => snapshot.value?.publish_user_options ?? [])
const pinnedMemos = computed(() => (snapshot.value?.task_memos ?? []).filter((memo) => memo.is_pinned))
const regularMemos = computed(() => (snapshot.value?.task_memos ?? []).filter((memo) => !memo.is_pinned))
const memoTaskOptions = computed(() => {
  const options = new Map<string, { id: string; label: string }>()

  const addOption = (id: string, title: string): void => {
    if (!options.has(id)) {
      options.set(id, { id, label: title })
    }
  }

  for (const item of snapshot.value?.task_inbox ?? []) {
    addOption(item.task_id, item.title)
  }
  for (const item of snapshot.value?.task_tracking ?? []) {
    addOption(item.task_id, item.title)
  }
  for (const item of snapshot.value?.task_history ?? []) {
    addOption(item.task_id, item.title)
  }

  return Array.from(options.values())
})

function normalizeTab(rawTab: unknown): TaskCenterTab {
  if (typeof rawTab !== 'string') {
    return 'inbox'
  }
  const legacyTab = LEGACY_TAB_MAP[rawTab]
  if (legacyTab) {
    return legacyTab
  }
  if (
    rawTab === 'templates' ||
    rawTab === 'inbox' ||
    rawTab === 'tracking' ||
    rawTab === 'memos'
  ) {
    return rawTab
  }
  return 'inbox'
}

function resolveStatusLabel(status: TaskStatus): string {
  return STATUS_LABELS[status]
}

function resolvePriorityLabel(priority: TaskPriority): string {
  return PRIORITY_LABELS[priority]
}

function resolveSourceTypeLabel(sourceType: TaskSourceType): string {
  return SOURCE_TYPE_LABELS[sourceType]
}

function resetPublishForm(): void {
  publishForm.title = ''
  publishForm.description = ''
  publishForm.assignee_user_id = ''
  publishForm.department_id = publishDepartmentOptions.value[0]?.id ?? ''
  publishForm.priority = 'medium'
  publishForm.due_date = null
}

function resetMemoForm(): void {
  memoForm.memo_id = ''
  memoForm.content = ''
  memoForm.related_task_id = ''
  memoForm.is_pinned = false
}

function openTaskDrawer(): void {
  if (!permissions.value.can_publish_task) {
    return
  }
  resetPublishForm()
  taskDrawerVisible.value = true
}

async function loadSnapshot(): Promise<void> {
  loading.value = true
  try {
    snapshot.value = await getTaskCenterSnapshot()
    if (!publishForm.department_id && publishDepartmentOptions.value.length > 0) {
      publishForm.department_id = publishDepartmentOptions.value[0]!.id
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

function handleTabChange(value: string): void {
  const nextTab = normalizeTab(value)
  const selectedQuery = typeof route.query.selected === 'string' ? route.query.selected : undefined
  const nextQuery = nextTab === 'inbox'
    ? undefined
    : nextTab === 'tracking'
      ? selectedQuery
        ? { tab: nextTab, selected: selectedQuery }
        : { tab: nextTab }
      : { tab: nextTab }

  void router.replace({
    name: 'task-center',
    query: nextQuery,
  })
}

async function handlePublishTask(): Promise<void> {
  if (!publishForm.title.trim()) {
    ElMessage.warning('请输入任务标题')
    return
  }
  if (!publishForm.assignee_user_id) {
    ElMessage.warning('请选择执行人')
    return
  }

  publishSubmitting.value = true
  try {
    await createTask({
      title: publishForm.title.trim(),
      description: publishForm.description.trim() || null,
      assignee_id: publishForm.assignee_user_id,
      department_id: publishForm.department_id || null,
      priority: publishForm.priority,
      due_date: publishForm.due_date ? publishForm.due_date.toISOString() : null,
    })
    ElMessage.success('任务已发布')
    taskDrawerVisible.value = false
    resetPublishForm()
    await loadSnapshot()
    handleTabChange('inbox')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    publishSubmitting.value = false
  }
}

function startEditMemo(memo: TaskMemo): void {
  memoForm.memo_id = memo.id
  memoForm.content = memo.content
  memoForm.related_task_id = memo.related_task_id ?? ''
  memoForm.is_pinned = memo.is_pinned
}

async function handleMemoSubmit(): Promise<void> {
  if (!memoForm.content.trim()) {
    ElMessage.warning('请输入备忘内容')
    return
  }

  memoSubmitting.value = true
  try {
    if (memoForm.memo_id) {
      await updateTaskMemo(memoForm.memo_id, {
        content: memoForm.content.trim(),
        related_task_id: memoForm.related_task_id || null,
        is_pinned: memoForm.is_pinned,
      })
      ElMessage.success('备忘已更新')
    } else {
      await createTaskMemo({
        content: memoForm.content.trim(),
        related_task_id: memoForm.related_task_id || null,
        is_pinned: memoForm.is_pinned,
      })
      ElMessage.success('备忘已创建')
    }
    resetMemoForm()
    await loadSnapshot()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    memoSubmitting.value = false
  }
}

async function handleDeleteMemo(memo: TaskMemo): Promise<void> {
  try {
    await ElMessageBox.confirm('删除后无法恢复，是否继续？', '删除备忘', {
      type: 'warning',
    })
    await deleteTaskMemo(memo.id)
    if (memoForm.memo_id === memo.id) {
      resetMemoForm()
    }
    ElMessage.success('备忘已删除')
    await loadSnapshot()
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }
    if (error instanceof Error && (error.message === 'cancel' || error.message === 'close')) {
      return
    }
    ElMessage.error(getErrorMessage(error))
  }
}

function renderRelationTypes(item: TaskCenterTrackingItem | TaskCenterHistoryItem): string {
  return item.relation_types.join(' / ') || '—'
}

function isOverdue(item: TaskCenterTrackingItem): boolean {
  return !!(item.due_date && new Date(item.due_date) < new Date() && item.status !== 'done')
}

const nudgingTaskIds = ref<Set<string>>(new Set())

async function handleNudge(taskId: string): Promise<void> {
  nudgingTaskIds.value = new Set([...nudgingTaskIds.value, taskId])
  try {
    await createTaskComment(taskId, { content: '【催办】请及时处理此任务' })
    ElMessage.success('催办消息已发送')
  } catch {
    ElMessage.error('催办失败，请稍后重试')
  } finally {
    nudgingTaskIds.value = new Set([...nudgingTaskIds.value].filter((id) => id !== taskId))
  }
}

function renderTrackingSignals(item: TaskCenterTrackingItem): string {
  const signals: string[] = []
  if (item.is_pending_review) {
    signals.push('待验收')
  }
  if ((item.rework_count ?? 0) > 0) {
    signals.push(`返工 ${item.rework_count} 次`)
  }
  if (typeof item.review_quality_score === 'number') {
    signals.push(`质量 ${item.review_quality_score}/5`)
  }
  return signals.join(' / ') || '—'
}

function rowKey(item: TaskCenterInboxItem | TaskCenterTrackingItem | TaskCenterHistoryItem): string {
  return item.task_id
}

onMounted(() => {
  resetPublishForm()
  void loadSnapshot()
})
</script>

<template>
  <div class="task-center-view filum-page">
    <el-card shadow="never" class="filum-panel-card" v-loading="loading">
      <template #header>
        <div class="task-center-view__header filum-page-header">
          <div class="filum-page-header__copy">
            <span class="filum-page-header__eyebrow">Workflow</span>
            <strong class="filum-page-header__title">任务中心</strong>
            <p class="task-center-view__subtitle">默认聚焦待处理、任务跟踪、个人备忘与任务模板，建立任务改为全局入口。</p>
          </div>
          <el-space wrap>
            <el-tag :type="permissions.can_publish_task ? 'success' : 'info'" effect="plain">
              {{ permissions.can_publish_task ? '可发布任务' : '仅查看任务' }}
            </el-tag>
            <el-tag :type="permissions.can_manage_templates ? 'success' : 'info'" effect="plain">
              {{ permissions.can_manage_templates ? '可管理模板' : '仅查看模板' }}
            </el-tag>
            <el-button type="primary" :disabled="!permissions.can_publish_task" @click="openTaskDrawer">
              建立任务
            </el-button>
          </el-space>
        </div>
      </template>

      <el-tabs :model-value="activeTab" @update:model-value="handleTabChange">
        <el-tab-pane label="待处理" name="inbox" />
        <el-tab-pane label="任务跟踪" name="tracking" />
        <el-tab-pane label="备忘" name="memos" />
        <el-tab-pane label="任务模板" name="templates" />
      </el-tabs>
    </el-card>

    <TaskTemplatesView
      v-if="activeTab === 'templates'"
      :can-manage-templates="permissions.can_manage_templates"
      :can-publish-task="permissions.can_publish_task"
      :department-options="publishDepartmentOptions"
    />

    <template v-else-if="activeTab === 'inbox'">
      <el-card shadow="never" class="filum-panel-card">
        <template #header>
          <div class="task-center-view__section-header">
            <span>待处理</span>
            <small>集中查看首页汇入的流转任务</small>
          </div>
        </template>

        <el-empty v-if="(snapshot?.task_inbox.length ?? 0) === 0" description="暂无待办任务" />
        <el-table v-else :data="snapshot?.task_inbox ?? []" row-key="task_id" stripe>
          <el-table-column prop="title" label="任务标题" min-width="220" />
          <el-table-column label="优先级" width="120">
            <template #default="{ row }: { row: TaskCenterInboxItem }">
              <el-tag :type="PRIORITY_TAG_TYPES[row.priority]" effect="plain">
                {{ resolvePriorityLabel(row.priority) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="120">
            <template #default="{ row }: { row: TaskCenterInboxItem }">
              <el-tag :type="STATUS_TAG_TYPES[row.status]" effect="plain">
                {{ resolveStatusLabel(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="department_name" label="部门" min-width="180" />
          <el-table-column prop="current_stage_label" label="当前阶段" min-width="160" />
          <el-table-column prop="current_handler_label" label="当前处理人" min-width="180" />
          <el-table-column label="截止时间" min-width="180">
            <template #default="{ row }: { row: TaskCenterInboxItem }">
              {{ formatDateTime(row.due_date) }}
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </template>

    <template v-else-if="activeTab === 'tracking'">
      <el-card shadow="never" class="filum-panel-card">
        <template #header>
          <span>任务跟踪</span>
        </template>

        <el-empty v-if="(snapshot?.task_tracking.length ?? 0) === 0" description="暂无需要跟踪的任务" />
        <el-table v-else :data="snapshot?.task_tracking ?? []" :row-key="rowKey" stripe>
          <el-table-column label="任务标题" min-width="220">
            <template #default="{ row }: { row: TaskCenterTrackingItem }">
              <el-space wrap>
                <span>{{ row.title }}</span>
                <el-tag v-if="isOverdue(row)" type="danger" size="small" effect="plain">已逾期</el-tag>
              </el-space>
            </template>
          </el-table-column>
          <el-table-column prop="department_name" label="部门" min-width="160" />
          <el-table-column label="关联方式" min-width="180">
            <template #default="{ row }: { row: TaskCenterTrackingItem }">
              {{ renderRelationTypes(row) }}
            </template>
          </el-table-column>
          <el-table-column prop="current_stage_label" label="当前阶段" min-width="160" />
          <el-table-column prop="current_handler_label" label="当前处理人" min-width="180" />
          <el-table-column label="交付信号" min-width="180">
            <template #default="{ row }: { row: TaskCenterTrackingItem }">
              {{ renderTrackingSignals(row) }}
            </template>
          </el-table-column>
          <el-table-column label="最近提交" min-width="180">
            <template #default="{ row }: { row: TaskCenterTrackingItem }">
              {{ formatDateTime(row.latest_deliverable_submitted_at ?? null) }}
            </template>
          </el-table-column>
          <el-table-column label="截止时间" min-width="180">
            <template #default="{ row }: { row: TaskCenterTrackingItem }">
              {{ formatDateTime(row.due_date) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100" fixed="right">
            <template #default="{ row }: { row: TaskCenterTrackingItem }">
              <el-button
                size="small"
                :loading="nudgingTaskIds.has(row.task_id)"
                @click="handleNudge(row.task_id)"
              >
                催办
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <TasksView
        :show-create-task-composer="false"
        :initial-selected-task-id="selectedTaskId"
        :delegate-user-options="publishUserOptions"
      />

      <el-card shadow="never" class="filum-panel-card">
        <template #header>
          <span>历史任务</span>
        </template>

        <el-empty v-if="(snapshot?.task_history.length ?? 0) === 0" description="暂无历史任务" />
        <el-table v-else :data="snapshot?.task_history ?? []" :row-key="rowKey" stripe>
          <el-table-column prop="title" label="任务标题" min-width="220" />
          <el-table-column label="来源" width="120">
            <template #default="{ row }: { row: TaskCenterHistoryItem }">
              {{ resolveSourceTypeLabel(row.source_type) }}
            </template>
          </el-table-column>
          <el-table-column prop="department_name" label="部门" min-width="160" />
          <el-table-column label="关联方式" min-width="180">
            <template #default="{ row }: { row: TaskCenterHistoryItem }">
              {{ renderRelationTypes(row) }}
            </template>
          </el-table-column>
          <el-table-column label="优先级" width="120">
            <template #default="{ row }: { row: TaskCenterHistoryItem }">
              <el-tag :type="PRIORITY_TAG_TYPES[row.priority]" effect="plain">
                {{ resolvePriorityLabel(row.priority) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="截止时间" min-width="180">
            <template #default="{ row }: { row: TaskCenterHistoryItem }">
              {{ formatDateTime(row.due_date) }}
            </template>
          </el-table-column>
          <el-table-column label="完成时间" min-width="180">
            <template #default="{ row }: { row: TaskCenterHistoryItem }">
              {{ formatDateTime(row.completed_at) }}
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </template>

    <template v-else-if="activeTab === 'memos'">
      <el-row :gutter="20">
        <el-col :xs="24" :xl="10">
          <el-card shadow="never" class="filum-panel-card">
            <template #header>
              <div class="task-center-view__memo-header">
                <span>{{ memoForm.memo_id ? '编辑备忘' : '新增备忘' }}</span>
                <el-button v-if="memoForm.memo_id" text @click="resetMemoForm">取消编辑</el-button>
              </div>
            </template>

            <el-form label-position="top" class="task-center-view__form">
              <el-form-item label="内容">
                <el-input
                  v-model="memoForm.content"
                  type="textarea"
                  :rows="6"
                  placeholder="记录推进要点、跟进事项或协作提醒"
                />
              </el-form-item>
              <el-form-item label="关联任务">
                <el-select v-model="memoForm.related_task_id" clearable placeholder="可选">
                  <el-option
                    v-for="task in memoTaskOptions"
                    :key="task.id"
                    :label="task.label"
                    :value="task.id"
                  />
                </el-select>
              </el-form-item>
              <el-form-item label="置顶">
                <el-switch v-model="memoForm.is_pinned" />
              </el-form-item>
              <el-button type="primary" :loading="memoSubmitting" @click="handleMemoSubmit">
                {{ memoForm.memo_id ? '保存备忘' : '创建备忘' }}
              </el-button>
            </el-form>
          </el-card>
        </el-col>

        <el-col :xs="24" :xl="14">
          <el-card shadow="never" class="filum-panel-card">
            <template #header>
              <span>我的备忘</span>
            </template>

            <el-empty
              v-if="(snapshot?.task_memos.length ?? 0) === 0"
              description="还没有备忘，建议记录任务交接与后续提醒。"
            />

            <div v-else class="task-center-view__memo-list">
              <template v-if="pinnedMemos.length > 0">
                <div class="task-center-view__memo-section-title">置顶备忘</div>
                <el-card
                  v-for="memo in pinnedMemos"
                  :key="memo.id"
                  shadow="never"
                  class="task-center-view__memo-card"
                >
                  <div class="task-center-view__memo-actions">
                    <el-tag type="warning" effect="plain">置顶</el-tag>
                    <el-space>
                      <el-button text @click="startEditMemo(memo)">编辑</el-button>
                      <el-button text type="danger" @click="handleDeleteMemo(memo)">删除</el-button>
                    </el-space>
                  </div>
                  <p class="task-center-view__memo-content">{{ memo.content }}</p>
                  <div class="task-center-view__memo-meta">
                    <span>更新时间：{{ formatDateTime(memo.updated_at) }}</span>
                    <span v-if="memo.related_task">
                      关联任务：{{ memo.related_task.title }}
                    </span>
                  </div>
                </el-card>
              </template>

              <template v-if="regularMemos.length > 0">
                <div class="task-center-view__memo-section-title">其他备忘</div>
                <el-card
                  v-for="memo in regularMemos"
                  :key="memo.id"
                  shadow="never"
                  class="task-center-view__memo-card"
                >
                  <div class="task-center-view__memo-actions">
                    <span class="task-center-view__memo-time">
                      更新于 {{ formatDateTime(memo.updated_at) }}
                    </span>
                    <el-space>
                      <el-button text @click="startEditMemo(memo)">编辑</el-button>
                      <el-button text type="danger" @click="handleDeleteMemo(memo)">删除</el-button>
                    </el-space>
                  </div>
                  <p class="task-center-view__memo-content">{{ memo.content }}</p>
                  <div v-if="memo.related_task" class="task-center-view__memo-meta">
                    关联任务：{{ memo.related_task.title }}
                  </div>
                </el-card>
              </template>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </template>

    <el-drawer
      v-model="taskDrawerVisible"
      title="建立任务"
      size="460px"
      destroy-on-close
      @closed="resetPublishForm"
    >
      <el-form label-position="top" class="task-center-view__form">
        <el-form-item label="任务标题">
          <el-input v-model="publishForm.title" placeholder="例如：完成四月客户复盘" />
        </el-form-item>
        <el-form-item label="任务说明">
          <el-input v-model="publishForm.description" type="textarea" :rows="4" />
        </el-form-item>
        <el-form-item label="执行人">
          <el-select v-model="publishForm.assignee_user_id" placeholder="请选择执行人">
            <el-option
              v-for="user in publishUserOptions"
              :key="user.user_id"
              :label="user.label"
              :value="user.user_id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="所属部门">
          <el-select v-model="publishForm.department_id" clearable placeholder="可选">
            <el-option
              v-for="department in publishDepartmentOptions"
              :key="department.id"
              :label="department.label"
              :value="department.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="publishForm.priority">
            <el-option label="低" value="low" />
            <el-option label="中" value="medium" />
            <el-option label="高" value="high" />
            <el-option label="紧急" value="urgent" />
          </el-select>
        </el-form-item>
        <el-form-item label="截止时间">
          <el-date-picker
            v-model="publishForm.due_date"
            type="datetime"
            placeholder="可选"
            class="task-center-view__date-picker"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <div class="task-center-view__drawer-footer">
          <el-button @click="taskDrawerVisible = false">取消</el-button>
          <el-button type="primary" :loading="publishSubmitting" @click="handlePublishTask">
            建立任务
          </el-button>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<style scoped>
.task-center-view {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.task-center-view__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.task-center-view__subtitle {
  margin: 6px 0 0;
  color: var(--filum-text-secondary);
  font-size: 13px;
}

.task-center-view__section-header {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.task-center-view__section-header small {
  color: var(--filum-text-secondary);
  font-size: 12px;
}

.task-center-view__form {
  max-width: 720px;
}

.task-center-view__date-picker {
  width: 100%;
}

.task-center-view__drawer-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.task-center-view__memo-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.task-center-view__memo-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.task-center-view__memo-section-title {
  color: var(--filum-text-secondary);
  font-size: 13px;
}

.task-center-view__memo-card {
  border-radius: 10px;
  border: 1px solid var(--filum-border-strong);
  background: linear-gradient(180deg, #ffffff 0%, #f8faff 100%);
}

.task-center-view__memo-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.task-center-view__memo-content {
  margin: 12px 0;
  line-height: 1.7;
  white-space: pre-wrap;
}

.task-center-view__memo-meta,
.task-center-view__memo-time {
  color: var(--filum-text-muted);
  font-size: 13px;
}

.task-center-view__memo-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}
</style>
