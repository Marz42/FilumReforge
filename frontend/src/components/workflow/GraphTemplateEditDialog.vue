<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import { getGraphTemplateDetail, updateGraphTemplate } from '@/api/workflow-graph'
import type { GraphTemplateSummary } from '@/types/workflowVideo'
import { getErrorMessage } from '@/utils/errors'

const props = defineProps<{
  modelValue: boolean
  template: GraphTemplateSummary | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  saved: []
}>()

const loading = ref(false)
const saving = ref(false)
const nodeSummaries = ref<Array<{ node_key: string; title: string; sort_order: number }>>([])
const form = reactive({
  name: '',
  description: '',
})

const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})

const definitionLocked = computed(() => {
  const status = props.template?.status
  return status === 'active' || status === 'archived'
})

async function loadDetail(): Promise<void> {
  if (!props.template) {
    return
  }
  loading.value = true
  try {
    const detail = await getGraphTemplateDetail(props.template.id)
    form.name = detail.name
    form.description = detail.description ?? ''
    nodeSummaries.value = detail.nodes.map((node) => ({
      node_key: node.node_key,
      title: node.title,
      sort_order: node.sort_order,
    }))
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
    visible.value = false
  } finally {
    loading.value = false
  }
}

async function handleSave(): Promise<void> {
  if (!props.template || definitionLocked.value) {
    return
  }
  const name = form.name.trim()
  if (!name) {
    ElMessage.warning('请填写模板名称')
    return
  }
  saving.value = true
  try {
    await updateGraphTemplate(props.template.id, {
      name,
      description: form.description.trim() || null,
    })
    ElMessage.success('模板已更新')
    visible.value = false
    emit('saved')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    saving.value = false
  }
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      void loadDetail()
    }
  },
)
</script>

<template>
  <el-dialog
    v-model="visible"
    :title="template ? `编辑模板：${template.code}` : '编辑模板'"
    width="560px"
    destroy-on-close
    data-testid="graph-template-edit-dialog"
  >
    <div v-loading="loading">
      <el-form label-position="top" @submit.prevent>
        <el-form-item label="模板名称" required>
          <el-input
            v-model="form.name"
            :disabled="definitionLocked"
            maxlength="120"
            show-word-limit
          />
        </el-form-item>
        <el-form-item label="说明">
          <el-input
            v-model="form.description"
            :disabled="definitionLocked"
            type="textarea"
            :rows="3"
            maxlength="2000"
            show-word-limit
          />
        </el-form-item>
        <el-form-item v-if="template" label="元数据">
          <p class="graph-template-edit__meta">
            编码 {{ template.code }} · 版本 v{{ template.version }}
          </p>
          <div v-if="template.tags?.length" class="graph-template-edit__chips">
            <el-tag
              v-for="tag in template.tags"
              :key="tag"
              size="small"
              effect="plain"
            >
              {{ tag }}
            </el-tag>
          </div>
          <div v-if="template.capabilities?.derived_hints?.length" class="graph-template-edit__chips">
            <el-tag
              v-for="hint in template.capabilities.derived_hints"
              :key="hint"
              size="small"
              type="info"
              effect="plain"
            >
              {{ hint }}
            </el-tag>
          </div>
        </el-form-item>
        <el-form-item v-if="nodeSummaries.length" label="节点一览（只读）">
          <el-table :data="nodeSummaries" size="small" border>
            <el-table-column prop="node_key" label="节点键" min-width="140" />
            <el-table-column prop="title" label="标题" min-width="120" />
            <el-table-column prop="sort_order" label="顺序" width="72" />
          </el-table>
        </el-form-item>
      </el-form>
    </div>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button
        v-if="!definitionLocked"
        type="primary"
        :loading="saving"
        data-testid="graph-template-edit-save"
        @click="handleSave"
      >
        保存
      </el-button>
      <p v-else class="graph-template-edit__meta">已发布模板请在设计器中「另存新版本」后改名。</p>
    </template>
  </el-dialog>
</template>

<style scoped>
.graph-template-edit__meta {
  margin: 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.graph-template-edit__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 8px;
}
</style>
