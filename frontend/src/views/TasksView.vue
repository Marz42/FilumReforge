<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, type UploadFile } from 'element-plus'

import { listAttachments, uploadAttachment } from '@/api/attachments'
import { listDepartments } from '@/api/departments'
import { createTask, listTasks } from '@/api/tasks'
import { listUsers } from '@/api/users'
import { useAuthStore } from '@/stores/auth'
import type { Attachment, Department, Task, TaskPriority, User } from '@/types/api'
import { formatDateTime } from '@/utils/formatters'
import { getErrorMessage } from '@/utils/errors'

const authStore = useAuthStore()
const loading = ref(false)
const submitting = ref(false)
const uploading = ref(false)
const dialogVisible = ref(false)
const tasks = ref<Task[]>([])
const attachments = ref<Attachment[]>([])
const departments = ref<Department[]>([])
const users = ref<User[]>([])
const selectedTaskId = ref('')
const selectedFile = ref<File | null>(null)

const form = reactive({
  title: '',
  description: '',
  assignee_id: '',
  department_id: '',
  priority: 'medium' as TaskPriority,
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

function resolveDepartmentName(departmentId: string | null): string {
  if (!departmentId) {
    return '—'
  }

  return departmentNameMap.value.get(departmentId) ?? '—'
}

function resolveUserEmail(userId: string): string {
  return userEmailMap.value.get(userId) ?? '—'
}

function resetForm(): void {
  form.title = ''
  form.description = ''
  form.assignee_id = authStore.user?.id ?? ''
  form.department_id = ''
  form.priority = 'medium'
}

async function loadAttachmentsForTask(taskId: string): Promise<void> {
  try {
    attachments.value = await listAttachments({
      target_type: 'task',
      target_id: taskId,
    })
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  }
}

async function loadData(): Promise<void> {
  loading.value = true

  try {
    const [taskList, departmentList] = await Promise.all([
      listTasks(),
      listDepartments(),
    ])

    tasks.value = taskList
    departments.value = departmentList

    if (authStore.isManagementRole) {
      users.value = await listUsers()
    } else if (authStore.user) {
      users.value = [authStore.user]
    }

    if (!selectedTaskId.value && tasks.value.length > 0) {
      const firstTask = tasks.value[0]
      if (firstTask) {
        selectedTaskId.value = firstTask.id
      }
    }

    if (selectedTaskId.value) {
      await loadAttachmentsForTask(selectedTaskId.value)
    } else {
      attachments.value = []
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
    })

    ElMessage.success('任务已创建')
    dialogVisible.value = false
    resetForm()
    await loadData()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    submitting.value = false
  }
}

function handleTaskClick(task: Task): void {
  selectedTaskId.value = task.id
  void loadAttachmentsForTask(task.id)
}

function handleFileChange(uploadFile: UploadFile): void {
  selectedFile.value = uploadFile.raw ?? null
}

function handleFileRemove(): void {
  selectedFile.value = null
}

async function handleAttachmentUpload(): Promise<void> {
  if (!selectedTask.value || !selectedFile.value) {
    ElMessage.warning('请选择任务并上传文件')
    return
  }

  uploading.value = true

  try {
    await uploadAttachment({
      file: selectedFile.value,
      target_type: 'task',
      target_id: selectedTask.value.id,
      visibility: 'private',
    })

    ElMessage.success('附件已上传')
    selectedFile.value = null
    await loadAttachmentsForTask(selectedTask.value.id)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    uploading.value = false
  }
}

onMounted(() => {
  resetForm()
  void loadData()
})
</script>

<template>
  <div class="page">
    <el-row :gutter="20">
      <el-col :xs="24" :lg="16">
        <el-card shadow="never" v-loading="loading">
          <template #header>
            <div class="page__header">
              <span>任务中心</span>
              <el-button type="primary" @click="dialogVisible = true">新建任务</el-button>
            </div>
          </template>

          <el-table :data="tasks" stripe @row-click="handleTaskClick">
            <el-table-column prop="title" label="任务标题" min-width="180" />
            <el-table-column label="执行人" min-width="180">
              <template #default="{ row }: { row: Task }">
                {{ resolveUserEmail(row.assignee_id) }}
              </template>
            </el-table-column>
            <el-table-column label="所属部门" min-width="160">
              <template #default="{ row }: { row: Task }">
                {{ resolveDepartmentName(row.department_id) }}
              </template>
            </el-table-column>
            <el-table-column label="优先级" width="120">
              <template #default="{ row }: { row: Task }">
                <el-tag effect="plain">{{ row.priority }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="120">
              <template #default="{ row }: { row: Task }">
                <el-tag type="success" effect="plain">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="创建时间" min-width="180">
              <template #default="{ row }: { row: Task }">
                {{ formatDateTime(row.created_at) }}
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="8">
        <el-card shadow="never" class="page__attachments">
          <template #header>
            <span>任务附件</span>
          </template>

          <template v-if="selectedTask">
            <el-descriptions :column="1" border>
              <el-descriptions-item label="当前任务">
                {{ selectedTask.title }}
              </el-descriptions-item>
              <el-descriptions-item label="执行人">
                {{ resolveUserEmail(selectedTask.assignee_id) }}
              </el-descriptions-item>
            </el-descriptions>

            <el-upload
              class="page__upload"
              :auto-upload="false"
              :limit="1"
              :show-file-list="true"
              :on-change="handleFileChange"
              :on-remove="handleFileRemove"
            >
              <template #trigger>
                <el-button>选择附件</el-button>
              </template>
            </el-upload>

            <el-button
              type="primary"
              class="page__upload-button"
              :loading="uploading"
              @click="handleAttachmentUpload"
            >
              上传到当前任务
            </el-button>

            <el-divider />

            <el-empty v-if="attachments.length === 0" description="暂无附件" />

            <el-space v-else direction="vertical" fill>
              <el-card
                v-for="attachment in attachments"
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
          </template>

          <el-empty v-else description="点击左侧任务查看附件" />
        </el-card>
      </el-col>
    </el-row>

    <el-dialog v-model="dialogVisible" title="新建任务" width="560px" @closed="resetForm">
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
.page__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.page__attachments {
  min-height: 100%;
}

.page__upload {
  margin-top: 20px;
}

.page__upload-button {
  margin-top: 12px;
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

.page__attachment-row p {
  margin: 8px 0 0;
  color: #606266;
}
</style>
