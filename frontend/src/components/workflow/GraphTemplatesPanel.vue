<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { listGraphTemplates } from '@/api/workflow-graph'
import TemplateInstantiateDialog from '@/components/workflow/TemplateInstantiateDialog.vue'
import type { GraphTemplateSummary } from '@/types/workflowVideo'
import type { User } from '@/types/api'
import { getErrorMessage } from '@/utils/errors'

const props = defineProps<{
  users: User[]
  canPublish: boolean
}>()

const emit = defineEmits<{
  instantiated: [payload: { instanceId: string; rootTaskId: string }]
}>()

const loading = ref(false)
const templates = ref<GraphTemplateSummary[]>([])
const selectedTemplate = ref<GraphTemplateSummary | null>(null)
const dialogVisible = ref(false)

async function loadTemplates(): Promise<void> {
  loading.value = true
  try {
    templates.value = await listGraphTemplates()
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
  if (!props.canPublish) {
    ElMessage.warning('当前账号无权发布组织任务')
    return
  }
  selectedTemplate.value = template
  dialogVisible.value = true
}

function handleCreated(payload: { instanceId: string; rootTaskId: string }): void {
  emit('instantiated', payload)
}

onMounted(() => {
  void loadTemplates()
})
</script>

<template>
  <div class="graph-templates" data-testid="graph-templates-panel">
    <el-card shadow="never" v-loading="loading">
      <template #header>
        <div class="graph-templates__header">
          <div>
            <strong>图模板库</strong>
            <p class="graph-templates__hint">与任务模板（E）区分；统一「选模板 → 实例化」入口。</p>
          </div>
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
        <el-table-column label="类型" width="100">
          <template #default="{ row }: { row: GraphTemplateSummary }">
            <el-tag effect="plain" type="primary">
              {{ row.run_kind === 'batch' ? '批次' : row.run_kind === 'production' ? '制作' : '图' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="版本" width="72" prop="version" />
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }: { row: GraphTemplateSummary }">
            <el-button
              type="primary"
              link
              :disabled="!canPublish"
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
      :users="users"
      @created="handleCreated"
    />
  </div>
</template>

<style scoped>
.graph-templates__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.graph-templates__hint {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
