<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import {
  forkGraphTemplateVersion,
  getGraphTemplateDesigner,
  publishGraphTemplate,
  saveGraphTemplateDraft,
  validateGraphTemplate,
} from '@/api/workflow-graph'
import { useTaskCenterPermissions } from '@/composables/useTaskCenterPermissions'
import type { GraphTemplateDesignerDetail, GraphTemplateNodeDetail } from '@/types/workflowVideo'
import { getErrorMessage } from '@/utils/errors'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const saving = ref(false)
const validating = ref(false)
const publishing = ref(false)
const forking = ref(false)
const detail = ref<GraphTemplateDesignerDetail | null>(null)
const validationErrors = ref<string[]>([])

const form = reactive({
  name: '',
  description: '',
  aggregateMode: 'batch' as 'batch' | 'streaming',
  launchSchemaJson: '{}',
})

const nodeRows = ref<Array<GraphTemplateNodeDetail & { configJson: string }>>([])
const selectedNodeKey = ref<string | null>(null)

const { ensureLoaded, canAdministerTaskTemplates } = useTaskCenterPermissions()

const templateId = computed(() => String(route.params.id ?? ''))
const isDraft = computed(() => detail.value?.status === 'draft')
const structureLocked = computed(() => detail.value?.structure_locked ?? false)
const selectedNode = computed(() =>
  nodeRows.value.find((node) => node.node_key === selectedNodeKey.value) ?? null,
)

function applyDetail(next: GraphTemplateDesignerDetail): void {
  detail.value = next
  form.name = next.name
  form.description = next.description ?? ''
  form.aggregateMode = (next.config?.aggregate_mode === 'streaming' ? 'streaming' : 'batch')
  const launchSchema = next.config?.launch_schema
  form.launchSchemaJson = JSON.stringify(launchSchema ?? {}, null, 2)
  nodeRows.value = next.nodes.map((node) => ({
    ...node,
    configJson: JSON.stringify(node.config ?? {}, null, 2),
  }))
  if (!selectedNodeKey.value && nodeRows.value.length > 0) {
    selectedNodeKey.value = nodeRows.value[0]!.node_key
  }
}

async function loadDesigner(): Promise<void> {
  if (!templateId.value) {
    return
  }
  loading.value = true
  try {
    applyDetail(await getGraphTemplateDesigner(templateId.value))
    validationErrors.value = []
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
    void router.push({ name: 'task-templates' })
  } finally {
    loading.value = false
  }
}

function parseLaunchSchema(): Record<string, unknown> | null {
  try {
    const parsed = JSON.parse(form.launchSchemaJson || '{}') as unknown
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>
    }
    ElMessage.warning('launch_schema 必须是 JSON 对象')
    return null
  } catch {
    ElMessage.warning('launch_schema JSON 格式无效')
    return null
  }
}

function buildDraftPayload() {
  const launchSchema = parseLaunchSchema()
  if (launchSchema === null) {
    return null
  }
  const config = {
    ...(detail.value?.config ?? {}),
    launch_schema: launchSchema,
    aggregate_mode: form.aggregateMode,
  }
  const nodes = nodeRows.value.map((node, index) => {
    let config: Record<string, unknown>
    try {
      config = JSON.parse(node.configJson || '{}') as Record<string, unknown>
    } catch {
      throw new Error(`节点 ${node.node_key} 的 config JSON 无效`)
    }
    return {
      node_key: node.node_key,
      title: node.title.trim(),
      sort_order: node.sort_order || index + 1,
      assignee_rule: node.assignee_rule ?? {},
      config,
    }
  })
  return {
    name: form.name.trim(),
    description: form.description.trim() || null,
    config,
    nodes,
  }
}

async function handleValidate(): Promise<void> {
  if (!templateId.value) {
    return
  }
  validating.value = true
  try {
    if (isDraft.value && !structureLocked.value) {
      const payload = buildDraftPayload()
      if (!payload) {
        return
      }
      await saveGraphTemplateDraft(templateId.value, payload)
      applyDetail(await getGraphTemplateDesigner(templateId.value))
    }
    const result = await validateGraphTemplate(templateId.value)
    validationErrors.value = result.errors
    if (result.valid) {
      ElMessage.success('校验通过')
    } else {
      ElMessage.warning(`发现 ${result.errors.length} 项问题`)
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    validating.value = false
  }
}

async function handleSave(): Promise<void> {
  if (!templateId.value || !isDraft.value) {
    ElMessage.info('仅 draft 模板可保存草稿')
    return
  }
  saving.value = true
  try {
    const payload = buildDraftPayload()
    if (!payload) {
      return
    }
    applyDetail(await saveGraphTemplateDraft(templateId.value, payload))
    ElMessage.success('草稿已保存')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    saving.value = false
  }
}

async function handlePublish(): Promise<void> {
  if (!templateId.value || !isDraft.value) {
    return
  }
  try {
    await ElMessageBox.confirm('发布后将归档同族其它 active 模板，确认发布？', '发布模板', {
      type: 'warning',
    })
  } catch {
    return
  }
  publishing.value = true
  try {
    const payload = buildDraftPayload()
    if (payload) {
      await saveGraphTemplateDraft(templateId.value, payload)
    }
    const result = await validateGraphTemplate(templateId.value)
    if (!result.valid) {
      validationErrors.value = result.errors
      ElMessage.error('校验未通过，无法发布')
      return
    }
    applyDetail(await publishGraphTemplate(templateId.value))
    ElMessage.success('模板已发布')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    publishing.value = false
  }
}

async function handleForkVersion(): Promise<void> {
  if (!templateId.value) {
    return
  }
  forking.value = true
  try {
    const forked = await forkGraphTemplateVersion(templateId.value)
    ElMessage.success(`已创建 v${forked.version} 草稿`)
    await router.replace({ name: 'task-template-designer', params: { id: forked.id } })
    applyDetail(forked)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    forking.value = false
  }
}

function goBack(): void {
  void router.push({ name: 'task-templates' })
}

onMounted(async () => {
  await ensureLoaded()
  if (!canAdministerTaskTemplates.value) {
    ElMessage.warning('当前账号无权编辑任务模板')
    void router.replace({ name: 'task-templates' })
    return
  }
  await loadDesigner()
})
</script>

<template>
  <div
    v-loading="loading"
    class="designer page"
    data-testid="graph-template-designer"
  >
    <header class="designer__header">
      <div>
        <el-button link type="primary" data-testid="designer-back" @click="goBack">← 返回模板列表</el-button>
        <h1 class="designer__title">
          {{ detail?.name || '模板设计器' }}
        </h1>
        <p v-if="detail" class="designer__meta">
          {{ detail.code }} · v{{ detail.version }} ·
          <el-tag size="small" effect="plain">{{ detail.status }}</el-tag>
          <el-tag v-if="structureLocked" size="small" type="warning" effect="plain">结构已锁定</el-tag>
        </p>
      </div>
      <div class="designer__actions">
        <el-button :loading="validating" data-testid="designer-validate" @click="handleValidate">校验</el-button>
        <el-button
          v-if="isDraft"
          type="primary"
          plain
          :loading="saving"
          data-testid="designer-save"
          @click="handleSave"
        >
          保存草稿
        </el-button>
        <el-button :loading="forking" data-testid="designer-fork" @click="handleForkVersion">另存新版本</el-button>
        <el-button
          v-if="isDraft"
          type="primary"
          :loading="publishing"
          data-testid="designer-publish"
          @click="handlePublish"
        >
          发布
        </el-button>
      </div>
    </header>

    <el-alert
      v-if="validationErrors.length"
      type="warning"
      :closable="false"
      show-icon
      class="designer__alert"
      :title="`校验问题（${validationErrors.length}）`"
    >
      <ul class="designer__errors">
        <li v-for="item in validationErrors" :key="item">{{ item }}</li>
      </ul>
    </el-alert>

    <div class="designer__grid">
      <el-card shadow="never" class="designer__panel">
        <template #header><strong>模板信息</strong></template>
        <el-form label-position="top">
          <el-form-item label="名称" required>
            <el-input v-model="form.name" maxlength="120" show-word-limit />
          </el-form-item>
          <el-form-item label="说明">
            <el-input v-model="form.description" type="textarea" :rows="3" maxlength="2000" show-word-limit />
          </el-form-item>
          <el-form-item label="汇总模式">
            <el-radio-group v-model="form.aggregateMode" :disabled="structureLocked && !isDraft">
              <el-radio value="batch">batch（结束采集后汇总）</el-radio>
              <el-radio value="streaming">streaming（增量派发）</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="launch_schema（JSON）">
            <el-input
              v-model="form.launchSchemaJson"
              type="textarea"
              :rows="10"
              class="designer__json"
              spellcheck="false"
            />
          </el-form-item>
        </el-form>
      </el-card>

      <el-card shadow="never" class="designer__panel designer__panel--wide">
        <template #header><strong>节点</strong></template>
        <el-table :data="nodeRows" highlight-current-row @row-click="(row) => { selectedNodeKey = row.node_key }">
          <el-table-column prop="node_key" label="节点键" min-width="140" />
          <el-table-column label="标题" min-width="160">
            <template #default="{ row }">
              <el-input v-model="row.title" :disabled="structureLocked" size="small" />
            </template>
          </el-table-column>
          <el-table-column label="顺序" width="88">
            <template #default="{ row }">
              <el-input-number v-model="row.sort_order" :disabled="structureLocked" size="small" :min="0" />
            </template>
          </el-table-column>
        </el-table>

        <div v-if="selectedNode" class="designer__node-config">
          <h3>节点 config：{{ selectedNode.node_key }}</h3>
          <el-input
            v-model="selectedNode.configJson"
            type="textarea"
            :rows="16"
            class="designer__json"
            :disabled="structureLocked"
            spellcheck="false"
          />
        </div>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.designer__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.designer__title {
  margin: 8px 0 4px;
  font-size: 22px;
}

.designer__meta {
  margin: 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.designer__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.designer__grid {
  display: grid;
  grid-template-columns: minmax(280px, 360px) 1fr;
  gap: 16px;
}

.designer__panel--wide {
  min-width: 0;
}

.designer__json :deep(textarea) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
}

.designer__node-config {
  margin-top: 16px;
}

.designer__node-config h3 {
  margin: 0 0 8px;
  font-size: 14px;
}

.designer__alert {
  margin-bottom: 16px;
}

.designer__errors {
  margin: 0;
  padding-left: 18px;
}

@media (max-width: 960px) {
  .designer__grid {
    grid-template-columns: 1fr;
  }
}
</style>
