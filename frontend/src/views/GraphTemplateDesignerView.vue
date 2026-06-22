<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import {
  dryRunGraphTemplate,
  exportGraphTemplate,
  forkGraphTemplateVersion,
  getGraphTemplateDesigner,
  importGraphTemplateDraft,
  publishGraphTemplate,
  saveGraphTemplateDraft,
  validateGraphTemplate,
} from '@/api/workflow-graph'
import GraphTemplateDagPreview from '@/components/workflow/GraphTemplateDagPreview.vue'
import { useTaskCenterPermissions } from '@/composables/useTaskCenterPermissions'
import type {
  GraphTemplateDesignerDetail,
  GraphTemplateDryRunResult,
  GraphTemplateNodeDetail,
} from '@/types/workflowVideo'
import { getErrorMessage } from '@/utils/errors'

type DesignerNodeRow = GraphTemplateNodeDetail & {
  configJson: string
  routingRulesJson: string
}

type DesignerEdgeRow = {
  from_node_key: string
  to_node_key: string
  is_reject_path: boolean
  conditionJson: string
  priority: number
}

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const saving = ref(false)
const validating = ref(false)
const publishing = ref(false)
const forking = ref(false)
const dryRunning = ref(false)
const dryRunVisible = ref(false)
const dryRunResult = ref<GraphTemplateDryRunResult | null>(null)
const importInputRef = ref<HTMLInputElement | null>(null)
const detail = ref<GraphTemplateDesignerDetail | null>(null)
const validationErrors = ref<string[]>([])

const form = reactive({
  name: '',
  description: '',
  aggregateMode: 'batch' as 'batch' | 'streaming',
  launchSchemaJson: '{}',
})

const nodeRows = ref<DesignerNodeRow[]>([])
const edgeRows = ref<DesignerEdgeRow[]>([])
const selectedNodeKey = ref<string | null>(null)

const { ensureLoaded, canAdministerTaskTemplates } = useTaskCenterPermissions()

const templateId = computed(() => String(route.params.id ?? ''))
const isDraft = computed(() => detail.value?.status === 'draft')
const structureLocked = computed(() => detail.value?.structure_locked ?? false)
const selectedNode = computed(() =>
  nodeRows.value.find((node) => node.node_key === selectedNodeKey.value) ?? null,
)
const nodeKeyOptions = computed(() =>
  nodeRows.value.map((node) => ({ value: node.node_key, label: `${node.node_key} · ${node.title}` })),
)
const dagNodes = computed(() =>
  nodeRows.value.map((node) => ({ node_key: node.node_key, title: node.title })),
)
const dagEdges = computed(() =>
  edgeRows.value.map((edge) => ({
    from_node_key: edge.from_node_key,
    to_node_key: edge.to_node_key,
    is_reject_path: edge.is_reject_path,
  })),
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
    assignment_mode: node.assignment_mode ?? 'single',
    join_mode: node.join_mode ?? 'all',
    configJson: JSON.stringify(node.config ?? {}, null, 2),
    routingRulesJson: JSON.stringify((node.config?.routing_rules as unknown) ?? [], null, 2),
  }))
  edgeRows.value = (next.edges ?? []).map((edge) => ({
    from_node_key: edge.from_node_key,
    to_node_key: edge.to_node_key,
    is_reject_path: Boolean(edge.is_reject_path),
    conditionJson: JSON.stringify(edge.condition ?? {}, null, 2),
    priority: edge.priority ?? 0,
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
    let nodeConfig: Record<string, unknown>
    try {
      nodeConfig = JSON.parse(node.configJson || '{}') as Record<string, unknown>
    } catch {
      throw new Error(`节点 ${node.node_key} 的 config JSON 无效`)
    }
    try {
      const routingRules = JSON.parse(node.routingRulesJson || '[]') as unknown
      if (routingRules !== undefined) {
        if (!Array.isArray(routingRules)) {
          throw new Error(`节点 ${node.node_key} 的 routing_rules 必须是数组`)
        }
        if (routingRules.length > 0) {
          nodeConfig.routing_rules = routingRules
        } else {
          delete nodeConfig.routing_rules
        }
      }
    } catch (error) {
      if (error instanceof Error && error.message.includes('routing_rules')) {
        throw error
      }
      throw new Error(`节点 ${node.node_key} 的 routing_rules JSON 无效`)
    }
    const assignmentMode = node.assignment_mode === 'fan_out' ? 'fan_out' : 'single'
    return {
      node_key: node.node_key,
      title: node.title.trim(),
      sort_order: node.sort_order || index + 1,
      assignment_mode: assignmentMode,
      join_mode: assignmentMode === 'single' ? 'all' : (node.join_mode === 'any' ? 'any' : 'all'),
      assignee_rule: node.assignee_rule ?? {},
      config: nodeConfig,
    }
  })
  const edges = edgeRows.value.map((edge) => {
    let condition: Record<string, unknown>
    try {
      condition = JSON.parse(edge.conditionJson || '{}') as Record<string, unknown>
    } catch {
      throw new Error(`边 ${edge.from_node_key} → ${edge.to_node_key} 的 condition JSON 无效`)
    }
    return {
      from_node_key: edge.from_node_key,
      to_node_key: edge.to_node_key,
      is_reject_path: edge.is_reject_path,
      condition,
      priority: edge.priority ?? 0,
    }
  })
  return {
    name: form.name.trim(),
    description: form.description.trim() || null,
    config,
    nodes,
    edges,
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

async function handleExportJson(): Promise<void> {
  if (!templateId.value) {
    return
  }
  try {
    const bundle = await exportGraphTemplate(templateId.value)
    const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${detail.value?.code ?? 'template'}.json`
    anchor.click()
    URL.revokeObjectURL(url)
    ElMessage.success('模板 JSON 已导出')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  }
}

function openImportPicker(): void {
  importInputRef.value?.click()
}

async function handleImportFile(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file || !templateId.value) {
    return
  }
  if (!isDraft.value || structureLocked.value) {
    ElMessage.warning('仅可编辑的 draft 模板支持导入 JSON')
    return
  }
  try {
    const text = await file.text()
    const bundle = JSON.parse(text) as Parameters<typeof importGraphTemplateDraft>[1]
    applyDetail(await importGraphTemplateDraft(templateId.value, bundle))
    ElMessage.success('模板 JSON 已导入')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  }
}

async function handleDryRun(): Promise<void> {
  if (!templateId.value) {
    return
  }
  dryRunning.value = true
  try {
    const payload = buildDraftPayload()
    const result = await dryRunGraphTemplate(templateId.value, {
      draft: payload ?? undefined,
      inputs: {},
    })
    dryRunResult.value = result
    dryRunVisible.value = true
    if (result.valid) {
      ElMessage.success('试跑通过')
    } else {
      ElMessage.warning(`试跑发现 ${result.errors.length} 项问题`)
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    dryRunning.value = false
  }
}

function addEdgeRow(): void {
  const first = nodeRows.value[0]?.node_key ?? ''
  const second = nodeRows.value[1]?.node_key ?? first
  edgeRows.value.push({
    from_node_key: first,
    to_node_key: second,
    is_reject_path: false,
    conditionJson: '{}',
    priority: 0,
  })
}

function removeEdgeRow(index: number): void {
  edgeRows.value.splice(index, 1)
}

function handleAssignmentModeChange(row: DesignerNodeRow): void {
  if (row.assignment_mode === 'single') {
    row.join_mode = 'all'
  }
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
        <el-button :loading="dryRunning" data-testid="designer-dry-run" @click="handleDryRun">试跑</el-button>
        <el-button data-testid="designer-export" @click="handleExportJson">导出 JSON</el-button>
        <el-button
          v-if="isDraft && !structureLocked"
          data-testid="designer-import"
          @click="openImportPicker"
        >
          导入 JSON
        </el-button>
        <input ref="importInputRef" type="file" accept="application/json,.json" hidden @change="handleImportFile" />
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
        <template #header><strong>拓扑预览</strong></template>
        <GraphTemplateDagPreview :nodes="dagNodes" :edges="dagEdges" />
      </el-card>

      <el-card shadow="never" class="designer__panel designer__panel--full">
        <template #header><strong>节点</strong></template>
        <el-table :data="nodeRows" highlight-current-row @row-click="(row) => { selectedNodeKey = row.node_key }">
          <el-table-column prop="node_key" label="节点键" min-width="120" />
          <el-table-column label="标题" min-width="140">
            <template #default="{ row }">
              <el-input v-model="row.title" :disabled="structureLocked" size="small" />
            </template>
          </el-table-column>
          <el-table-column label="派发" width="96">
            <template #default="{ row }">
              <el-select
                v-model="row.assignment_mode"
                :disabled="structureLocked"
                size="small"
                @change="handleAssignmentModeChange(row)"
              >
                <el-option label="single" value="single" />
                <el-option label="fan_out" value="fan_out" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="汇聚" width="88">
            <template #default="{ row }">
              <el-select
                v-model="row.join_mode"
                :disabled="structureLocked || row.assignment_mode === 'single'"
                size="small"
              >
                <el-option label="all" value="all" />
                <el-option label="any" value="any" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="顺序" width="80">
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
            :rows="12"
            class="designer__json"
            :disabled="structureLocked"
            spellcheck="false"
          />
          <h3 class="designer__subheading">routing_rules（JSON 数组）</h3>
          <p class="designer__hint">
            示例 IF：<code>{"condition":{"field":"amount","operator":"gt","value":1},"target_node_key":"STEP_B"}</code>
            · ELSE：<code>{"else":true,"target_node_key":"STEP_C"}</code>
          </p>
          <el-input
            v-model="selectedNode.routingRulesJson"
            type="textarea"
            :rows="8"
            class="designer__json"
            :disabled="structureLocked"
            spellcheck="false"
          />
        </div>
      </el-card>

      <el-card shadow="never" class="designer__panel designer__panel--full">
        <template #header>
          <div class="designer__card-header">
            <strong>边与路由</strong>
            <el-button
              v-if="!structureLocked"
              size="small"
              data-testid="designer-add-edge"
              @click="addEdgeRow"
            >
              添加边
            </el-button>
          </div>
        </template>
        <el-table :data="edgeRows" empty-text="暂无边">
          <el-table-column label="起点" min-width="140">
            <template #default="{ row }">
              <el-select v-model="row.from_node_key" :disabled="structureLocked" size="small" filterable>
                <el-option
                  v-for="option in nodeKeyOptions"
                  :key="option.value"
                  :label="option.label"
                  :value="option.value"
                />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="终点" min-width="140">
            <template #default="{ row }">
              <el-select v-model="row.to_node_key" :disabled="structureLocked" size="small" filterable>
                <el-option
                  v-for="option in nodeKeyOptions"
                  :key="option.value"
                  :label="option.label"
                  :value="option.value"
                />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="reject" width="72">
            <template #default="{ row }">
              <el-checkbox v-model="row.is_reject_path" :disabled="structureLocked" />
            </template>
          </el-table-column>
          <el-table-column label="priority" width="88">
            <template #default="{ row }">
              <el-input-number v-model="row.priority" :disabled="structureLocked" size="small" :min="0" />
            </template>
          </el-table-column>
          <el-table-column label="condition JSON" min-width="220">
            <template #default="{ row }">
              <el-input
                v-model="row.conditionJson"
                :disabled="structureLocked"
                size="small"
                spellcheck="false"
              />
            </template>
          </el-table-column>
          <el-table-column v-if="!structureLocked" label="" width="64">
            <template #default="{ $index }">
              <el-button link type="danger" @click="removeEdgeRow($index)">删</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>

    <el-dialog v-model="dryRunVisible" title="试跑结果" width="720px" data-testid="designer-dry-run-dialog">
      <template v-if="dryRunResult">
        <el-alert
          :type="dryRunResult.valid ? 'success' : 'warning'"
          :closable="false"
          show-icon
          :title="dryRunResult.valid ? '结构校验通过' : '试跑发现问题'"
        />
        <div v-if="dryRunResult.errors.length" class="designer__dry-run-block">
          <h4>问题</h4>
          <ul class="designer__errors">
            <li v-for="item in dryRunResult.errors" :key="item">{{ item }}</li>
          </ul>
        </div>
        <div v-if="dryRunResult.entry_node_keys.length" class="designer__dry-run-block">
          <h4>起始节点</h4>
          <p>{{ dryRunResult.entry_node_keys.join(' · ') }}</p>
        </div>
        <div v-if="dryRunResult.participant_previews.length" class="designer__dry-run-block">
          <h4>参与人策略预览</h4>
          <el-table :data="dryRunResult.participant_previews" size="small">
            <el-table-column prop="policy_ref" label="策略" width="120" />
            <el-table-column prop="mode" label="模式" width="88" />
            <el-table-column prop="user_count" label="人数" width="72" />
          </el-table>
        </div>
        <div class="designer__dry-run-block">
          <h4>schema_snapshot</h4>
          <pre class="designer__json-preview">{{ JSON.stringify(dryRunResult.schema_snapshot, null, 2) }}</pre>
        </div>
      </template>
    </el-dialog>
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

.designer__card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.designer__subheading {
  margin: 16px 0 8px;
  font-size: 14px;
}

.designer__hint {
  margin: 0 0 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.designer__hint code {
  font-size: 11px;
}

.designer__dry-run-block {
  margin-top: 16px;
}

.designer__dry-run-block h4 {
  margin: 0 0 8px;
  font-size: 14px;
}

.designer__json-preview {
  margin: 0;
  padding: 12px;
  overflow: auto;
  max-height: 240px;
  border-radius: 8px;
  background: var(--el-fill-color-light);
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
}

.designer__panel--wide {
  min-width: 0;
}

.designer__panel--full {
  grid-column: 1 / -1;
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
