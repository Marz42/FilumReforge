<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, type UploadFile } from 'element-plus'

import { listAttachments, uploadAttachment } from '@/api/attachments'
import { listDepartments } from '@/api/departments'
import {
  createTask,
  createTaskComment,
  getTaskStatsSummary,
  getTaskWorkload,
  listTaskActivity,
  listTasks,
  updateTaskStatus,
} from '@/api/tasks'
import { listUsers } from '@/api/users'
import { useAuthStore } from '@/stores/auth'
import type {
  Attachment,
  Department,
  Task,
  TaskActivityEntry,
  TaskPriority,
  TaskStatus,
  TaskStatsSummary,
  TaskWorkloadRow,
  User,
} from '@/types/api'
import { getErrorMessage } from '@/utils/errors'
import { formatDateTime } from '@/utils/formatters'

type StatusAction = {
  label: string
  status: TaskStatus
  buttonType: 'primary' | 'warning' | 'success'
}

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

const NEXT_STATUS_ACTIONS: Record<Exclude<TaskStatus, 'done'>, StatusAction> = {
  todo: {
    label: '开始处理',
    status: 'doing',
    buttonType: 'primary',
  },
  doing: {
    label: '提交评审',
    status: 'review',
    buttonType: 'warning',
  },
  review: {
    label: '标记完成',
    status: 'done',
    buttonType: 'success',
  },
}

const authStore = useAuthStore()
const loading = ref(false)
const submitting = ref(false)
const taskAttachmentUploading = ref(false)
const commentSubmitting = ref(false)
const statusSubmitting = ref(false)
const dialogVisible = ref(false)
const tasks = ref<Task[]>([])
const taskAttachments = ref<Attachment[]>([])
const taskActivity = ref<TaskActivityEntry[]>([])
const departments = ref<Department[]>([])
const users = ref<User[]>([])
const statsSummary = ref<TaskStatsSummary | null>(null)
const workloadRows = ref<TaskWorkloadRow[]>([])
const selectedTaskId = ref('')
const selectedTaskFile = ref<File | null>(null)
const commentFiles = ref<File[]>([])

const form = reactive({
  title: '',
  description: '',
  assignee_id: '',
  department_id: '',
  priority: 'medium' as TaskPriority,
  due_date: null as Date | null,
})

const commentForm = reactive({
  content: '',
  is_internal: false,
})

const departmentNameMap = computed(
  () => new Map(departments.value.map((department) => [department.id, department.name])),
)
const userEmailMap = computed(() => new Map(users.value.map((user) => [user.id, user.email])))
const assigneeOptions = computed(() => {
  if (authStore.isManagementRole) {
    return users.value.filter((user) => user.status === 'active')
  }

  return authStore.user ? [authStore.user] : []
})
const selectedTask = computed(() => tasks.value.find((task) => task.id === selectedTaskId.value) ?? null)
const nextStatusAction = computed(() => {
  const task = selectedTask.value
  if (!task || task.status === 'done') {
    return null
  }

  return NEXT_STATUS_ACTIONS[task.status]
})
const canAdvanceSelectedTask = computed(() => {
  const task = selectedTask.value
  const user = authStore.user
  if (!task || !user) {
    return false
  }

  return authStore.isManagementRole || user.id === task.assignee_id || user.id === task.creator_id
})
const completionRateText = computed(() => formatRate(statsSummary.value?.completion_rate ?? 0))
const overdueRateText = computed(() => formatRate(statsSummary.value?.overdue_rate ?? 0))

function resolveDepartmentName(departmentId: string | null): string {
  if (!departmentId) {
    return '—'
  }

  return departmentNameMap.value.get(departmentId) ?? '—'
}

function resolveUserLabel(userId: string): string {
  return userEmailMap.value.get(userId) ?? `用户 ${userId.slice(0, 8)}`
}

function resolveStatusLabel(status: TaskStatus): string {
  return STATUS_LABELS[status]
}

function resolvePriorityLabel(priority: TaskPriority): string {
  return PRIORITY_LABELS[priority]
}

function formatRate(value: number): string {
  return `${Math.round(value * 100)}%`
}

function renderLogSummary(entry: TaskActivityEntry): string {
  const log = entry.log
  if (!log) {
    return ''
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

function resetTaskForm(): void {
  form.title = ''
  form.description = ''
  form.assignee_id = authStore.user?.id ?? ''
  form.department_id = ''
  form.priority = 'medium'
  form.due_date = null
}

function resetCommentForm(): void {
  commentForm.content = ''
  commentForm.is_internal = false
  commentFiles.value = []
}

async function loadSelectedTaskDetails(taskId: string): Promise<void> {
  const [attachments, activity] = await Promise.all([
    listAttachments({
      target_type: 'task',
      target_id: taskId,
    }),
    listTaskActivity(taskId),
  ])

  taskAttachments.value = attachments
  taskActivity.value = activity
}

async function loadData(): Promise<void> {
  loading.value = true

  try {
    const [taskList, departmentList, summary, workload] = await Promise.all([
      listTasks(),
      listDepartments(),
      getTaskStatsSummary(),
      getTaskWorkload(),
    ])

    tasks.value = taskList
    departments.value = departmentList
    statsSummary.value = summary
    workloadRows.value = workload

    if (authStore.isManagementRole) {
      users.value = await listUsers()
    } else if (authStore.user) {
      users.value = [authStore.user]
    }

    const stillSelected = taskList.some((task) => task.id === selectedTaskId.value)
    if (!stillSelected) {
      selectedTaskId.value = taskList[0]?.id ?? ''
    }

    if (selectedTaskId.value) {
      await loadSelectedTaskDetails(selectedTaskId.value)
    } else {
      taskAttachments.value = []
      taskActivity.value = []
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

async function handleCreateTask(): Promise<void> {
  if (!form.assignee_id) {
    ElMessage.warning('请选择执行人')
    return
  }

  submitting.value = true

  try {
    await createTask({
      title: form.title.trim(),
      description: form.description || null,
      assignee_id: form.assignee_id,
      department_id: form.department_id || null,
      priority: form.priority,
      due_date: form.due_date ? form.due_date.toISOString() : null,
    })

    ElMessage.success('任务已创建')
    dialogVisible.value = false
    resetTaskForm()
    await loadData()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    submitting.value = false
  }
}

function handleTaskClick(task: Task): void {
  selectedTaskId.value = task.id
  void loadSelectedTaskDetails(task.id)
}

function handleTaskFileChange(uploadFile: UploadFile): void {
  selectedTaskFile.value = uploadFile.raw ?? null
}

function handleTaskFileRemove(): void {
  selectedTaskFile.value = null
}

function normalizeUploadFiles(uploadFiles: UploadFile[]): File[] {
  return uploadFiles.reduce<File[]>((files, uploadFile) => {
    if (uploadFile.raw) {
      files.push(uploadFile.raw)
    }
    return files
  }, [])
}

async function handleTaskAttachmentUpload(): Promise<void> {
  if (!selectedTask.value || !selectedTaskFile.value) {
    ElMessage.warning('请选择任务并上传文件')
    return
  }

  taskAttachmentUploading.value = true

  try {
    await uploadAttachment({
      file: selectedTaskFile.value,
      target_type: 'task',
      target_id: selectedTask.value.id,
      visibility: 'private',
    })

    ElMessage.success('任务资料附件已上传')
    selectedTaskFile.value = null
    await loadSelectedTaskDetails(selectedTask.value.id)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    taskAttachmentUploading.value = false
  }
}

function handleCommentFileChange(_: UploadFile, uploadFiles: UploadFile[]): void {
  commentFiles.value = normalizeUploadFiles(uploadFiles)
}

function handleCommentFileRemove(_: UploadFile, uploadFiles: UploadFile[]): void {
  commentFiles.value = normalizeUploadFiles(uploadFiles)
}

async function handleCommentSubmit(): Promise<void> {
  if (!selectedTask.value) {
    ElMessage.warning('请先选择任务')
    return
  }
  if (!commentForm.content.trim()) {
    ElMessage.warning('请输入评论内容')
    return
  }

  commentSubmitting.value = true

  try {
    await createTaskComment(selectedTask.value.id, {
      content: commentForm.content.trim(),
      is_internal: commentForm.is_internal,
      files: commentFiles.value,
    })

    ElMessage.success('评论已提交')
    resetCommentForm()
    await loadSelectedTaskDetails(selectedTask.value.id)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    commentSubmitting.value = false
  }
}

async function handleStatusTransition(): Promise<void> {
  if (!selectedTask.value || !nextStatusAction.value) {
    return
  }

  statusSubmitting.value = true

  try {
    await updateTaskStatus(selectedTask.value.id, nextStatusAction.value.status)
    ElMessage.success(`任务已更新为${resolveStatusLabel(nextStatusAction.value.status)}`)
    await loadData()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    statusSubmitting.value = false
  }
}

onMounted(() => {
  resetTaskForm()
  void loadData()
})
</script>

<template>
  <div class="page">
    <el-row :gutter="16" class="page__summary">
      <el-col :xs="12" :lg="6">
        <el-card shadow="never">
          <el-statistic title="任务总数" :value="statsSummary?.total_tasks ?? 0" />
        </el-card>
      </el-col>
      <el-col :xs="12" :lg="6">
        <el-card shadow="never">
          <el-statistic title="已完成" :value="statsSummary?.completed_tasks ?? 0" />
          <div class="page__stat-text">完成率 {{ completionRateText }}</div>
        </el-card>
      </el-col>
      <el-col :xs="12" :lg="6">
        <el-card shadow="never">
          <el-statistic title="逾期任务" :value="statsSummary?.overdue_tasks ?? 0" />
          <div class="page__stat-text">逾期率 {{ overdueRateText }}</div>
        </el-card>
      </el-col>
      <el-col :xs="12" :lg="6">
        <el-card shadow="never">
          <el-statistic title="待办中" :value="statsSummary?.tasks_by_status?.todo ?? 0" />
          <div class="page__stat-text">
            评审中 {{ statsSummary?.tasks_by_status?.review ?? 0 }}
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20">
      <el-col :xs="24" :xl="12">
        <el-card shadow="never" v-loading="loading">
          <template #header>
            <div class="page__header">
              <span>任务中心</span>
              <el-button type="primary" @click="dialogVisible = true">新建任务</el-button>
            </div>
          </template>

          <el-table :data="tasks" stripe highlight-current-row @row-click="handleTaskClick">
            <el-table-column prop="title" label="任务标题" min-width="180" />
            <el-table-column label="执行人" min-width="180">
              <template #default="{ row }: { row: Task }">
                {{ resolveUserLabel(row.assignee_id) }}
              </template>
            </el-table-column>
            <el-table-column label="所属部门" min-width="160">
              <template #default="{ row }: { row: Task }">
                {{ resolveDepartmentName(row.department_id) }}
              </template>
            </el-table-column>
            <el-table-column label="优先级" width="120">
              <template #default="{ row }: { row: Task }">
                <el-tag :type="PRIORITY_TAG_TYPES[row.priority]" effect="plain">
                  {{ resolvePriorityLabel(row.priority) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="120">
              <template #default="{ row }: { row: Task }">
                <el-tag :type="STATUS_TAG_TYPES[row.status]" effect="plain">
                  {{ resolveStatusLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="截止时间" min-width="180">
              <template #default="{ row }: { row: Task }">
                {{ formatDateTime(row.due_date) }}
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <el-col :xs="24" :xl="12">
        <el-card shadow="never" class="page__detail">
          <template #header>
            <div class="page__header">
              <span>任务协同详情</span>
              <el-button
                v-if="selectedTask && nextStatusAction && canAdvanceSelectedTask"
                :type="nextStatusAction.buttonType"
                :loading="statusSubmitting"
                @click="handleStatusTransition"
              >
                {{ nextStatusAction.label }}
              </el-button>
            </div>
          </template>

          <template v-if="selectedTask">
            <el-descriptions :column="1" border>
              <el-descriptions-item label="任务标题">
                {{ selectedTask.title }}
              </el-descriptions-item>
              <el-descriptions-item label="执行人">
                {{ resolveUserLabel(selectedTask.assignee_id) }}
              </el-descriptions-item>
              <el-descriptions-item label="状态">
                <el-tag :type="STATUS_TAG_TYPES[selectedTask.status]" effect="plain">
                  {{ resolveStatusLabel(selectedTask.status) }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="优先级">
                <el-tag :type="PRIORITY_TAG_TYPES[selectedTask.priority]" effect="plain">
                  {{ resolvePriorityLabel(selectedTask.priority) }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="所属部门">
                {{ resolveDepartmentName(selectedTask.department_id) }}
              </el-descriptions-item>
              <el-descriptions-item label="截止时间">
                {{ formatDateTime(selectedTask.due_date) }}
              </el-descriptions-item>
              <el-descriptions-item label="任务描述">
                {{ selectedTask.description || '—' }}
              </el-descriptions-item>
            </el-descriptions>

            <el-divider>任务资料附件</el-divider>

            <el-upload
              class="page__upload"
              :auto-upload="false"
              :limit="1"
              :show-file-list="true"
              :on-change="handleTaskFileChange"
              :on-remove="handleTaskFileRemove"
            >
              <template #trigger>
                <el-button>选择附件</el-button>
              </template>
            </el-upload>

            <el-button
              type="primary"
              class="page__upload-button"
              :loading="taskAttachmentUploading"
              @click="handleTaskAttachmentUpload"
            >
              上传到任务
            </el-button>

            <el-empty v-if="taskAttachments.length === 0" description="暂无任务资料附件" />

            <el-space v-else direction="vertical" fill>
              <el-card
                v-for="attachment in taskAttachments"
                :key="attachment.id"
                shadow="never"
                class="page__attachment-card"
              >
                <div class="page__attachment-row">
                  <div>
                    <strong>{{ attachment.original_filename }}</strong>
                    <p>{{ attachment.mime_type }} · {{ attachment.size_bytes }} bytes</p>
                  </div>
                  <el-link
                    v-if="attachment.download_url"
                    :href="attachment.download_url"
                    target="_blank"
                    type="primary"
                  >
                    下载
                  </el-link>
                </div>
              </el-card>
            </el-space>

            <el-divider>评论与留痕</el-divider>

            <el-form label-position="top">
              <el-form-item label="评论内容">
                <el-input
                  v-model="commentForm.content"
                  type="textarea"
                  :rows="4"
                  placeholder="请输入任务评论或协作说明"
                />
              </el-form-item>
              <el-form-item v-if="authStore.isManagementRole" label="内部备注">
                <el-switch v-model="commentForm.is_internal" />
              </el-form-item>
              <el-form-item label="评论附件">
                <el-upload
                  :auto-upload="false"
                  multiple
                  :show-file-list="true"
                  :on-change="handleCommentFileChange"
                  :on-remove="handleCommentFileRemove"
                >
                  <template #trigger>
                    <el-button>选择评论附件</el-button>
                  </template>
                </el-upload>
              </el-form-item>
            </el-form>

            <el-button type="primary" :loading="commentSubmitting" @click="handleCommentSubmit">
              提交评论
            </el-button>

            <el-divider>活动时间线</el-divider>

            <el-empty v-if="taskActivity.length === 0" description="暂无活动记录" />

            <el-timeline v-else>
              <el-timeline-item
                v-for="entry in taskActivity"
                :key="`${entry.entry_type}-${entry.created_at}`"
                :timestamp="formatDateTime(entry.created_at)"
                placement="top"
              >
                <el-card shadow="never">
                  <template v-if="entry.comment">
                    <div class="page__timeline-header">
                      <div>
                        <strong>{{ resolveUserLabel(entry.comment.user_id) }}</strong>
                        <el-tag
                          v-if="entry.comment.is_internal"
                          type="warning"
                          effect="plain"
                          class="page__inline-tag"
                        >
                          内部备注
                        </el-tag>
                      </div>
                      <el-tag type="primary" effect="plain">评论</el-tag>
                    </div>
                    <p class="page__timeline-text">{{ entry.comment.content }}</p>
                    <div
                      v-if="entry.comment.attachments.length > 0"
                      class="page__comment-attachments"
                    >
                      <el-link
                        v-for="attachment in entry.comment.attachments"
                        :key="attachment.id"
                        :href="attachment.download_url || undefined"
                        :underline="false"
                        target="_blank"
                        type="primary"
                      >
                        {{ attachment.original_filename }}
                      </el-link>
                    </div>
                  </template>

                  <template v-else-if="entry.log">
                    <div class="page__timeline-header">
                      <strong>{{ resolveUserLabel(entry.log.operator_id) }}</strong>
                      <el-tag effect="plain">日志</el-tag>
                    </div>
                    <p class="page__timeline-text">{{ renderLogSummary(entry) }}</p>
                  </template>
                </el-card>
              </el-timeline-item>
            </el-timeline>
          </template>

          <el-empty v-else description="点击左侧任务查看协同详情" />
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="page__workload">
      <template #header>
        <span>负载概览</span>
      </template>

      <el-table :data="workloadRows" stripe>
        <el-table-column prop="assignee_email" label="执行人" min-width="220" />
        <el-table-column prop="department_name" label="部门" min-width="160" />
        <el-table-column prop="total_tasks" label="总任务数" width="120" />
        <el-table-column prop="open_tasks" label="进行中/待处理" width="140" />
        <el-table-column prop="completed_tasks" label="已完成" width="100" />
        <el-table-column prop="overdue_tasks" label="逾期" width="100" />
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" title="新建任务" width="560px" @closed="resetTaskForm">
      <el-form label-position="top">
        <el-form-item label="任务标题">
          <el-input v-model="form.title" />
        </el-form-item>
        <el-form-item label="任务描述">
          <el-input v-model="form.description" type="textarea" :rows="4" />
        </el-form-item>
        <el-form-item label="执行人">
          <el-select v-model="form.assignee_id" placeholder="请选择执行人">
            <el-option
              v-for="user in assigneeOptions"
              :key="user.id"
              :label="user.email"
              :value="user.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="所属部门">
          <el-select v-model="form.department_id" clearable placeholder="可选">
            <el-option
              v-for="department in departments"
              :key="department.id"
              :label="department.name"
              :value="department.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="form.priority">
            <el-option label="低" value="low" />
            <el-option label="中" value="medium" />
            <el-option label="高" value="high" />
            <el-option label="紧急" value="urgent" />
          </el-select>
        </el-form-item>
        <el-form-item label="截止时间">
          <el-date-picker
            v-model="form.due_date"
            type="datetime"
            placeholder="可选"
            class="page__date-picker"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleCreateTask">
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.page__summary {
  margin-bottom: 4px;
}

.page__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.page__detail,
.page__workload {
  min-height: 100%;
}

.page__stat-text {
  margin-top: 8px;
  color: #606266;
  font-size: 13px;
}

.page__upload {
  margin-top: 12px;
}

.page__upload-button {
  margin: 12px 0 16px;
}

.page__attachment-card {
  width: 100%;
}

.page__attachment-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.page__attachment-row p,
.page__timeline-text {
  margin: 8px 0 0;
  color: #606266;
}

.page__timeline-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.page__inline-tag {
  margin-left: 8px;
}

.page__comment-attachments {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 12px;
}

.page__date-picker {
  width: 100%;
}
</style>
