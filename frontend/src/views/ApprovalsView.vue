<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import {
  type WorkflowStepPayload,
  actWorkflowStepRun,
  createWorkflowDefinition,
  listPendingWorkflowStepRuns,
  listWorkflowDefinitions,
  listWorkflowInstances,
  startWorkflow,
} from '@/api/workflows'
import { useAuthStore } from '@/stores/auth'
import type { WorkflowDefinition, WorkflowInstance, WorkflowStepRun } from '@/types/api'
import { getErrorMessage } from '@/utils/errors'
import { formatDateTime } from '@/utils/formatters'

const authStore = useAuthStore()
const loading = ref(false)
const actionSubmitting = ref(false)
const createDialogVisible = ref(false)
const createSubmitting = ref(false)
const startSubmitting = ref(false)
const pendingStepRuns = ref<WorkflowStepRun[]>([])
const workflowInstances = ref<WorkflowInstance[]>([])
const workflowDefinitions = ref<WorkflowDefinition[]>([])

const createForm = reactive({
  code: '',
  name: '',
  scope_type: 'task',
  stepsText:
    '[\n  {\n    "step_key": "approve",\n    "name": "直属审批",\n    "step_type": "approval",\n    "assignee_rule": { "type": "department_manager" }\n  }\n]',
})

const startForm = reactive({
  definition_id: '',
  source_type: 'task_request',
})

const latestInstance = computed(() => workflowInstances.value[0] ?? null)

function parseJsonArray(text: string): WorkflowStepPayload[] {
  return JSON.parse(text) as WorkflowStepPayload[]
}

async function loadData(): Promise<void> {
  loading.value = true
  try {
    const [stepRunList, instanceList, definitionList] = await Promise.all([
      listPendingWorkflowStepRuns(),
      listWorkflowInstances(),
      listWorkflowDefinitions(),
    ])
    pendingStepRuns.value = stepRunList
    workflowInstances.value = instanceList
    workflowDefinitions.value = definitionList
    if (!startForm.definition_id) {
      startForm.definition_id = definitionList[0]?.id ?? ''
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

async function handleAction(
  stepRunId: string,
  action: 'approve' | 'reject' | 'return',
): Promise<void> {
  actionSubmitting.value = true
  try {
    await actWorkflowStepRun(stepRunId, action)
    ElMessage.success('审批动作已提交')
    await loadData()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    actionSubmitting.value = false
  }
}

async function handleCreateDefinition(): Promise<void> {
  createSubmitting.value = true
  try {
    await createWorkflowDefinition({
      code: createForm.code.trim(),
      name: createForm.name.trim(),
      scope_type: createForm.scope_type.trim(),
      status: 'active',
      steps: parseJsonArray(createForm.stepsText),
    })
    ElMessage.success('审批定义已创建')
    createDialogVisible.value = false
    await loadData()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    createSubmitting.value = false
  }
}

async function handleStartWorkflow(): Promise<void> {
  if (!startForm.definition_id) {
    ElMessage.warning('请选择审批定义')
    return
  }
  startSubmitting.value = true
  try {
    await startWorkflow({
      definition_id: startForm.definition_id,
      source_type: startForm.source_type.trim(),
      payload: {},
    })
    ElMessage.success('审批流已发起')
    await loadData()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    startSubmitting.value = false
  }
}

onMounted(() => {
  void loadData()
})
</script>

<template>
  <div class="page">
    <el-row :gutter="20">
      <el-col :xs="24" :xl="14">
        <el-card shadow="never" v-loading="loading">
          <template #header>
            <div class="page__header">
              <span>待处理审批</span>
              <el-button v-if="authStore.isManagementRole" type="primary" @click="createDialogVisible = true">
                新建审批定义
              </el-button>
            </div>
          </template>

          <el-empty v-if="pendingStepRuns.length === 0" description="暂无待处理审批" />
          <el-table v-else :data="pendingStepRuns">
            <el-table-column label="步骤" min-width="180">
              <template #default="{ row }: { row: WorkflowStepRun }">
                {{ row.step?.name ?? row.step_id }}
              </template>
            </el-table-column>
            <el-table-column label="委托来源" min-width="180">
              <template #default="{ row }: { row: WorkflowStepRun }">
                {{ row.delegated_from_user_id || '—' }}
              </template>
            </el-table-column>
            <el-table-column label="创建时间" min-width="180">
              <template #default="{ row }: { row: WorkflowStepRun }">
                {{ formatDateTime(row.created_at) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="220">
              <template #default="{ row }: { row: WorkflowStepRun }">
                <el-space>
                  <el-button size="small" type="primary" :loading="actionSubmitting" @click="handleAction(row.id, 'approve')">
                    通过
                  </el-button>
                  <el-button size="small" type="warning" :loading="actionSubmitting" @click="handleAction(row.id, 'return')">
                    打回
                  </el-button>
                  <el-button size="small" type="danger" :loading="actionSubmitting" @click="handleAction(row.id, 'reject')">
                    驳回
                  </el-button>
                </el-space>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <el-col :xs="24" :xl="10">
        <el-card shadow="never">
          <template #header>
            <span>发起审批</span>
          </template>

          <el-form label-position="top">
            <el-form-item label="审批定义">
              <el-select v-model="startForm.definition_id" placeholder="请选择审批定义">
                <el-option
                  v-for="definition in workflowDefinitions"
                  :key="definition.id"
                  :label="definition.name"
                  :value="definition.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="来源类型">
              <el-input v-model="startForm.source_type" />
            </el-form-item>
          </el-form>
          <el-button type="primary" :loading="startSubmitting" @click="handleStartWorkflow">
            发起审批
          </el-button>

          <el-divider>最近实例</el-divider>
          <el-empty v-if="!latestInstance" description="暂无审批实例" />
          <el-descriptions v-else :column="1" border>
            <el-descriptions-item label="流程">{{ latestInstance.definition?.name ?? latestInstance.definition_id }}</el-descriptions-item>
            <el-descriptions-item label="状态">{{ latestInstance.status }}</el-descriptions-item>
            <el-descriptions-item label="当前步骤">{{ latestInstance.current_step_key || '已结束' }}</el-descriptions-item>
            <el-descriptions-item label="发起时间">
              {{ formatDateTime(latestInstance.started_at) }}
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never">
      <template #header>
        <span>审批实例列表</span>
      </template>
      <el-table :data="workflowInstances" size="small">
        <el-table-column label="流程" min-width="180">
          <template #default="{ row }: { row: WorkflowInstance }">
            {{ row.definition?.name ?? row.definition_id }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="140" />
        <el-table-column prop="current_step_key" label="当前步骤" width="140" />
        <el-table-column label="发起时间" min-width="180">
          <template #default="{ row }: { row: WorkflowInstance }">
            {{ formatDateTime(row.started_at) }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="createDialogVisible" title="新建审批定义" width="640px">
      <el-form label-position="top">
        <el-form-item label="编码">
          <el-input v-model="createForm.code" />
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="createForm.name" />
        </el-form-item>
        <el-form-item label="范围">
          <el-input v-model="createForm.scope_type" />
        </el-form-item>
        <el-form-item label="步骤定义(JSON)">
          <el-input v-model="createForm.stepsText" type="textarea" :rows="10" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="createSubmitting" @click="handleCreateDefinition">
          保存定义
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
</style>
