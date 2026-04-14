<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { listDepartments } from '@/api/departments'
import {
  type TaskTemplateStepPayload,
  createTaskSchedule,
  createTaskTemplate,
  instantiateTaskTemplate,
  listTaskSchedules,
  listTaskTemplates,
} from '@/api/task-templates'
import { useAuthStore } from '@/stores/auth'
import type { Department, Task, TaskSchedule, TaskTemplate } from '@/types/api'
import { getErrorMessage } from '@/utils/errors'
import { formatDateTime } from '@/utils/formatters'

const authStore = useAuthStore()
const loading = ref(false)
const createDialogVisible = ref(false)
const createSubmitting = ref(false)
const instantiateSubmitting = ref(false)
const scheduleSubmitting = ref(false)
const templates = ref<TaskTemplate[]>([])
const schedules = ref<TaskSchedule[]>([])
const departments = ref<Department[]>([])
const instantiatedTasks = ref<Task[]>([])
const selectedTemplateId = ref('')

const createForm = reactive({
  code: '',
  name: '',
  category: 'ops',
  description: '',
  stepsText:
    '[\n  {\n    "step_key": "draft",\n    "title": "发起执行",\n    "default_assignee_rule": { "type": "initiator" }\n  }\n]',
})

const instantiateForm = reactive({
  department_id: '',
})

const scheduleForm = reactive({
  template_id: '',
  cron_expr: '0 9 * * 1-5',
  timezone: 'UTC',
  payloadText: '{}',
})

const selectedTemplate = computed(
  () => templates.value.find((template) => template.id === selectedTemplateId.value) ?? null,
)

function parseJsonValue<T>(text: string, fallback: T): T {
  if (!text.trim()) {
    return fallback
  }
  return JSON.parse(text) as T
}

function resetCreateForm(): void {
  createForm.code = ''
  createForm.name = ''
  createForm.category = 'ops'
  createForm.description = ''
  createForm.stepsText =
    '[\n  {\n    "step_key": "draft",\n    "title": "发起执行",\n    "default_assignee_rule": { "type": "initiator" }\n  }\n]'
}

async function loadData(): Promise<void> {
  loading.value = true
  try {
    const [templateList, scheduleList, departmentList] = await Promise.all([
      listTaskTemplates(),
      authStore.isManagementRole ? listTaskSchedules() : Promise.resolve([]),
      listDepartments(),
    ])
    templates.value = templateList
    schedules.value = scheduleList
    departments.value = departmentList
    if (!selectedTemplateId.value || !templateList.some((template) => template.id === selectedTemplateId.value)) {
      selectedTemplateId.value = templateList[0]?.id ?? ''
      scheduleForm.template_id = templateList[0]?.id ?? ''
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

async function handleCreateTemplate(): Promise<void> {
  createSubmitting.value = true
  try {
    await createTaskTemplate({
      code: createForm.code.trim(),
      name: createForm.name.trim(),
      category: createForm.category.trim(),
      description: createForm.description || null,
      steps: parseJsonValue<TaskTemplateStepPayload[]>(createForm.stepsText, []),
    })
    ElMessage.success('模板已创建')
    createDialogVisible.value = false
    resetCreateForm()
    await loadData()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    createSubmitting.value = false
  }
}

async function handleInstantiateTemplate(): Promise<void> {
  if (!selectedTemplate.value) {
    ElMessage.warning('请先选择模板')
    return
  }
  instantiateSubmitting.value = true
  try {
    const result = await instantiateTaskTemplate(selectedTemplate.value.id, {
      department_id: instantiateForm.department_id || null,
      payload: instantiateForm.department_id
        ? { department_id: instantiateForm.department_id }
        : {},
    })
    instantiatedTasks.value = result.tasks
    ElMessage.success(`模板已实例化，生成 ${result.tasks.length} 条任务`)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    instantiateSubmitting.value = false
  }
}

async function handleCreateSchedule(): Promise<void> {
  if (!scheduleForm.template_id) {
    ElMessage.warning('请选择模板')
    return
  }
  scheduleSubmitting.value = true
  try {
    await createTaskSchedule({
      template_id: scheduleForm.template_id,
      cron_expr: scheduleForm.cron_expr.trim(),
      timezone: scheduleForm.timezone.trim(),
      payload: parseJsonValue(scheduleForm.payloadText, {}),
    })
    ElMessage.success('调度已创建')
    await loadData()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    scheduleSubmitting.value = false
  }
}

onMounted(() => {
  void loadData()
})
</script>

<template>
  <div class="page">
    <el-row :gutter="20">
      <el-col :xs="24" :xl="13">
        <el-card shadow="never" v-loading="loading">
          <template #header>
            <div class="page__header">
              <span>任务模板</span>
              <el-button v-if="authStore.isManagementRole" type="primary" @click="createDialogVisible = true">
                新建模板
              </el-button>
            </div>
          </template>

          <el-table :data="templates" highlight-current-row @row-click="(row: TaskTemplate) => (selectedTemplateId = row.id)">
            <el-table-column prop="name" label="模板名称" min-width="180" />
            <el-table-column prop="category" label="分类" width="120" />
            <el-table-column label="步骤数" width="100">
              <template #default="{ row }: { row: TaskTemplate }">
                {{ row.steps.length }}
              </template>
            </el-table-column>
            <el-table-column label="启用" width="100">
              <template #default="{ row }: { row: TaskTemplate }">
                <el-tag :type="row.is_active ? 'success' : 'info'" effect="plain">
                  {{ row.is_active ? '启用中' : '停用' }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <el-col :xs="24" :xl="11">
        <el-card shadow="never" class="page__detail">
          <template #header>
            <span>模板详情</span>
          </template>

          <template v-if="selectedTemplate">
            <el-descriptions :column="1" border>
              <el-descriptions-item label="模板编码">{{ selectedTemplate.code }}</el-descriptions-item>
              <el-descriptions-item label="分类">{{ selectedTemplate.category }}</el-descriptions-item>
              <el-descriptions-item label="触发方式">{{ selectedTemplate.trigger_type }}</el-descriptions-item>
              <el-descriptions-item label="说明">
                {{ selectedTemplate.description || '—' }}
              </el-descriptions-item>
            </el-descriptions>

            <el-divider>步骤</el-divider>
            <el-timeline>
              <el-timeline-item
                v-for="step in selectedTemplate.steps"
                :key="step.id"
                :timestamp="`排序 ${step.sort_order}`"
              >
                <strong>{{ step.title }}</strong>
                <p>{{ step.step_key }} · 依赖 {{ step.depends_on_step_keys.join(', ') || '无' }}</p>
              </el-timeline-item>
            </el-timeline>

            <el-divider>实例化</el-divider>
            <el-form label-position="top">
              <el-form-item label="所属部门（可选）">
                <el-select v-model="instantiateForm.department_id" clearable placeholder="默认使用当前用户部门">
                  <el-option
                    v-for="department in departments"
                    :key="department.id"
                    :label="department.name"
                    :value="department.id"
                  />
                </el-select>
              </el-form-item>
            </el-form>
            <el-button type="primary" :loading="instantiateSubmitting" @click="handleInstantiateTemplate">
              实例化模板
            </el-button>

            <el-divider>最近实例化结果</el-divider>
            <el-empty v-if="instantiatedTasks.length === 0" description="尚未实例化模板" />
            <el-table v-else :data="instantiatedTasks" size="small">
              <el-table-column prop="title" label="任务标题" min-width="180" />
              <el-table-column prop="status" label="状态" width="100" />
            </el-table>
          </template>

          <el-empty v-else description="请选择左侧模板查看详情" />
        </el-card>
      </el-col>
    </el-row>

    <el-card v-if="authStore.isManagementRole" shadow="never">
      <template #header>
        <span>周期调度</span>
      </template>

      <el-form label-position="top" class="page__schedule-form">
        <el-form-item label="模板">
          <el-select v-model="scheduleForm.template_id" placeholder="请选择模板">
            <el-option
              v-for="template in templates"
              :key="template.id"
              :label="template.name"
              :value="template.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="Cron 表达式">
          <el-input v-model="scheduleForm.cron_expr" />
        </el-form-item>
        <el-form-item label="时区">
          <el-input v-model="scheduleForm.timezone" />
        </el-form-item>
        <el-form-item label="调度 payload(JSON)">
          <el-input v-model="scheduleForm.payloadText" type="textarea" :rows="4" />
        </el-form-item>
      </el-form>
      <el-button type="primary" :loading="scheduleSubmitting" @click="handleCreateSchedule">
        创建调度
      </el-button>

      <el-divider>现有调度</el-divider>
      <el-table :data="schedules" size="small">
        <el-table-column prop="cron_expr" label="Cron" min-width="180" />
        <el-table-column prop="timezone" label="时区" width="120" />
        <el-table-column label="下次执行" min-width="180">
          <template #default="{ row }: { row: TaskSchedule }">
            {{ formatDateTime(row.next_run_at) }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="createDialogVisible" title="新建模板" width="640px" @closed="resetCreateForm">
      <el-form label-position="top">
        <el-form-item label="模板编码">
          <el-input v-model="createForm.code" />
        </el-form-item>
        <el-form-item label="模板名称">
          <el-input v-model="createForm.name" />
        </el-form-item>
        <el-form-item label="分类">
          <el-input v-model="createForm.category" />
        </el-form-item>
        <el-form-item label="模板说明">
          <el-input v-model="createForm.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="步骤定义(JSON)">
          <el-input v-model="createForm.stepsText" type="textarea" :rows="10" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="createSubmitting" @click="handleCreateTemplate">
          保存模板
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

.page__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.page__detail {
  min-height: 100%;
}

.page__schedule-form {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
}
</style>
