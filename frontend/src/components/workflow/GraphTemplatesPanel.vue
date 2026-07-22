<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import { getTaskCenterSnapshot } from '@/api/task-center'
import { getProfile } from '@/api/profiles'
import {
  archiveGraphTemplate,
  cloneGraphTemplate,
  createBlankGraphTemplate,
  deleteGraphTemplate,
  listGraphTemplates,
} from '@/api/workflow-graph'
import GraphTemplateEditDialog from '@/components/workflow/GraphTemplateEditDialog.vue'
import TemplateInstantiateDialog from '@/components/workflow/TemplateInstantiateDialog.vue'
import { useAuthStore } from '@/stores/auth'
import type { GraphTemplateSummary } from '@/types/workflowVideo'
import { getErrorMessage } from '@/utils/errors'
import { templateSupportsDirectInstantiation } from '@/utils/workflowVideoSchema'

const props = defineProps<{
  canPublish: boolean
  canManage?: boolean
}>()

const emit = defineEmits<{
  instantiated: [payload: { instanceId: string; rootTaskId: string }]
}>()

const loading = ref(false)
const statusFilter = ref<'working' | 'all' | 'draft' | 'active' | 'archived'>('working')
const searchQuery = ref('')
const templates = ref<GraphTemplateSummary[]>([])
const selectedTemplate = ref<GraphTemplateSummary | null>(null)
const dialogVisible = ref(false)
const editDialogVisible = ref(false)
const departmentOptions = ref<Array<{ id: string; label: string }>>([])
const defaultDepartmentId = ref('')

const authStore = useAuthStore()
const router = useRouter()

const instantiateDepartmentOptions = computed(() => departmentOptions.value)

const listStatusParam = computed((): Array<'draft' | 'active' | 'archived'> | undefined => {
  if (statusFilter.value === 'all') {
    return ['draft', 'active', 'archived']
  }
  if (statusFilter.value === 'draft') {
    return ['draft']
  }
  if (statusFilter.value === 'active') {
    return ['active']
  }
  if (statusFilter.value === 'archived') {
    return ['archived']
  }
  return ['draft', 'active']
})

function canInstantiateTemplate(template: GraphTemplateSummary): boolean {
  return props.canPublish && templateSupportsDirectInstantiation(template)
}

async function loadInstantiateDepartmentContext(): Promise<void> {
  try {
    const snapshot = await getTaskCenterSnapshot()
    departmentOptions.value = snapshot.publish_department_options.map((option) => ({
      id: option.id,
      label: option.label,
    }))
    const userId = authStore.user?.id
    if (userId) {
      const profile = await getProfile(userId)
      if (
        profile.department_id
        && departmentOptions.value.some((option) => option.id === profile.department_id)
      ) {
        defaultDepartmentId.value = profile.department_id
        return
      }
    }
    if (departmentOptions.value.length === 1) {
      defaultDepartmentId.value = departmentOptions.value[0]!.id
      return
    }
    defaultDepartmentId.value = ''
  } catch {
    departmentOptions.value = []
    defaultDepartmentId.value = ''
  }
}

async function loadTemplates(): Promise<void> {
  loading.value = true
  try {
    templates.value = await listGraphTemplates({
      manage: props.canManage,
      status: listStatusParam.value,
      q: searchQuery.value,
    })
    if (!selectedTemplate.value && templates.value.length > 0) {
      selectedTemplate.value = templates.value[0] ?? null
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
    templates.value = []
  } finally {
    loading.value = false
  }
}

function openInstantiate(template: GraphTemplateSummary): void {
  if (!canInstantiateTemplate(template)) {
    if (template.capabilities?.derived_hints?.includes('仅子流程')) {
      ElMessage.info('仅子流程模板，不支持直接实例化')
    } else if (!props.canPublish) {
      ElMessage.warning('当前账号无权发布组织任务')
    } else {
      ElMessage.info('当前不可实例化')
    }
    return
  }
  selectedTemplate.value = template
  dialogVisible.value = true
}

function openEdit(template: GraphTemplateSummary): void {
  if (!props.canManage) {
    ElMessage.warning('当前账号无权编辑任务模板')
    return
  }
  if (template.status !== 'draft') {
    ElMessage.info('已发布模板不可原地修改。请使用另存新版本或派生草稿。')
    return
  }
  selectedTemplate.value = template
  editDialogVisible.value = true
}

function openDesigner(template: GraphTemplateSummary): void {
  if (!props.canManage) {
    ElMessage.warning('当前账号无权编辑任务模板')
    return
  }
  void router.push({ name: 'task-template-designer', params: { id: template.id } })
}

async function handleCreateBlank(): Promise<void> {
  if (!props.canManage) {
    ElMessage.warning('当前账号无权编辑任务模板')
    return
  }
  try {
    const created = await createBlankGraphTemplate('未命名模板')
    ElMessage.success('已创建空白草稿')
    void router.push({ name: 'task-template-designer', params: { id: created.id } })
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  }
}

async function handleClone(template: GraphTemplateSummary): Promise<void> {
  if (!props.canManage) {
    ElMessage.warning('当前账号无权编辑任务模板')
    return
  }
  try {
    const forked = await cloneGraphTemplate(template.id, `${template.name}（副本）`)
    ElMessage.success('已创建草稿副本')
    void router.push({ name: 'task-template-designer', params: { id: forked.id } })
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  }
}

async function handleArchive(template: GraphTemplateSummary): Promise<void> {
  if (!props.canManage || template.status !== 'active') {
    return
  }
  try {
    await ElMessageBox.confirm(
      `确认归档「${template.name}」？归档后不可原地编辑；可在列表中筛选查看。`,
      '归档任务模板',
      { type: 'warning', confirmButtonText: '归档', cancelButtonText: '取消' },
    )
    await archiveGraphTemplate(template.id)
    ElMessage.success('模板已归档')
    await loadTemplates()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(getErrorMessage(error))
    }
  }
}

async function handleDelete(template: GraphTemplateSummary): Promise<void> {
  if (!props.canManage) {
    ElMessage.warning('当前账号无权维护任务模板')
    return
  }
  const hasRuns = (template.run_count_total ?? 0) > 0
  if (hasRuns) {
    ElMessage.error('已有运行实例的模板不可删除。请先归档相关 Run。')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确定要删除模板「${template.name}」吗？此操作不可撤销。`,
      '删除任务模板',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
    await deleteGraphTemplate(template.id)
    ElMessage.success('模板已删除')
    if (selectedTemplate.value?.id === template.id) {
      selectedTemplate.value = null
    }
    await loadTemplates()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(getErrorMessage(error))
    }
  }
}

function handleCreated(payload: { instanceId: string; rootTaskId: string }): void {
  emit('instantiated', payload)
}

onMounted(() => {
  void loadTemplates()
  void loadInstantiateDepartmentContext()
})
</script>

<template>
  <div class="graph-templates" data-testid="graph-templates-panel">
    <el-card shadow="never" v-loading="loading">
      <template #header>
        <div class="graph-templates__header">
          <div>
            <strong>任务模板</strong>
            <p class="graph-templates__hint">选模板 → 填写 launch 信息 → 实例化派发。</p>
          </div>
          <el-select
            v-model="statusFilter"
            style="width: 140px"
            data-testid="graph-template-status-filter"
            @change="loadTemplates"
          >
            <el-option label="草稿+已发布" value="working" />
            <el-option label="全部" value="all" />
            <el-option label="草稿" value="draft" />
            <el-option label="已发布" value="active" />
            <el-option label="已归档" value="archived" />
          </el-select>
          <el-input
            v-model="searchQuery"
            clearable
            placeholder="搜索名称或编码"
            style="width: 200px"
            data-testid="graph-template-search"
            @clear="loadTemplates"
            @keyup.enter="loadTemplates"
          />
          <el-button v-if="canManage" type="primary" data-testid="graph-template-create" @click="handleCreateBlank">
            新建模板
          </el-button>
          <el-button @click="loadTemplates">刷新</el-button>
        </div>
      </template>

      <el-table
        :data="templates"
        highlight-current-row
        @row-click="(row: GraphTemplateSummary) => { selectedTemplate = row }"
      >
        <el-table-column prop="name" label="模板名称" min-width="180" />
        <el-table-column prop="code" label="编码" min-width="200" />
        <el-table-column label="标签 / 能力" min-width="200">
          <template #default="{ row }: { row: GraphTemplateSummary }">
            <el-tag
              v-for="tag in row.tags ?? []"
              :key="tag"
              size="small"
              effect="plain"
              class="graph-templates__tag"
            >
              {{ tag }}
            </el-tag>
            <el-tag
              v-for="hint in row.capabilities?.derived_hints ?? []"
              :key="hint"
              size="small"
              type="info"
              effect="plain"
            >
              {{ hint }}
            </el-tag>
            <span v-if="!(row.tags?.length) && !(row.capabilities?.derived_hints?.length)">—</span>
          </template>
        </el-table-column>
        <el-table-column label="版本" width="72" prop="version" />
        <el-table-column v-if="canManage" label="Run（30d）" width="96">
          <template #default="{ row }: { row: GraphTemplateSummary }">
            {{ row.run_count_30d ?? 0 }}
            <span v-if="row.active_run_count" class="graph-templates__active-runs">
              / {{ row.active_run_count }} 进行中
            </span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="88">
          <template #default="{ row }: { row: GraphTemplateSummary }">
            <el-tag size="small" effect="plain" :type="row.status === 'active' ? 'success' : 'info'">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="360" fixed="right">
          <template #default="{ row }: { row: GraphTemplateSummary }">
            <el-button
              v-if="canManage"
              type="primary"
              link
              data-testid="graph-template-design"
              @click.stop="openDesigner(row)"
            >
              设计
            </el-button>
            <el-button
              v-if="canManage"
              type="primary"
              link
              data-testid="graph-template-clone"
              @click.stop="handleClone(row)"
            >
              复制
            </el-button>
            <el-button
              v-if="canManage && row.status === 'draft'"
              link
              data-testid="graph-template-edit"
              @click.stop="openEdit(row)"
            >
              改名
            </el-button>
            <el-button
              v-if="canManage && row.status === 'active'"
              link
              type="warning"
              data-testid="graph-template-archive"
              @click.stop="handleArchive(row)"
            >
              归档
            </el-button>
            <el-tooltip
              v-if="canManage && row.status === 'draft' && (row.run_count_total ?? 0) > 0"
              content="已有运行实例，不可删除"
              placement="top"
            >
              <span>
                <el-button link disabled data-testid="graph-template-delete">删除</el-button>
              </span>
            </el-tooltip>
            <el-button
              v-else-if="canManage && row.status === 'draft'"
              link
              type="danger"
              data-testid="graph-template-delete"
              @click.stop="handleDelete(row)"
            >
              删除
            </el-button>
            <el-tooltip
              v-if="!canInstantiateTemplate(row)"
              :content="row.capabilities?.derived_hints?.includes('仅子流程') ? '仅子流程模板，不支持直接实例化' : '当前不可实例化'"
              placement="top"
            >
              <span>
                <el-button type="primary" link disabled data-testid="graph-template-instantiate">
                  实例化
                </el-button>
              </span>
            </el-tooltip>
            <el-button
              v-else
              type="primary"
              link
              data-testid="graph-template-instantiate"
              @click.stop="openInstantiate(row)"
            >
              实例化
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <TemplateInstantiateDialog
      v-model="dialogVisible"
      :template="selectedTemplate"
      :default-department-id="defaultDepartmentId"
      :department-options="instantiateDepartmentOptions"
      @created="handleCreated"
    />

    <GraphTemplateEditDialog
      v-model="editDialogVisible"
      :template="selectedTemplate"
      @saved="loadTemplates"
    />
  </div>
</template>

<style scoped>
.graph-templates__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.graph-templates__hint {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.graph-templates__active-runs {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.graph-templates__tag {
  margin-right: 4px;
  margin-bottom: 2px;
}
</style>
