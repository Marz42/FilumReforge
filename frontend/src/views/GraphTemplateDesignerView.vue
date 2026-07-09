<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import { listDepartments, listDepartmentTree } from '@/api/departments'
import {
  dryRunGraphTemplate,
  exportGraphTemplate,
  forkGraphTemplateVersion,
  getGraphTemplateDesigner,
  importGraphTemplateDraft,
  publishGraphTemplate,
  saveGraphTemplateDraft,
  updateGraphTemplate,
  validateGraphTemplate,
} from '@/api/workflow-graph'
import GraphTemplateDagPreview from '@/components/workflow/GraphTemplateDagPreview.vue'
import { useTaskCenterPermissions } from '@/composables/useTaskCenterPermissions'
import type {
  GraphTemplateDesignerDetail,
  GraphTemplateDryRunResult,
  GraphTemplateNodeDetail,
} from '@/types/workflowVideo'
import { analyzeEdgeTopology } from '@/utils/graphTemplateTopology'
import { getErrorMessage } from '@/utils/errors'

type DepartmentPoolRow = {
  pool_key: string
  department_id: string
}

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
  runKind: 'batch' as 'batch' | 'production',
  aggregateMode: 'streaming' as 'batch' | 'streaming',
  launchSchemaJson: '{}',
  rootAssigneeVar: '',
  aggregateNodeKey: '',
  schedulable: false,
  onCompleteEnabled: false,
  onCompleteNextTemplateCode: '',
  onCompleteCarryInputs: true,
  scopeDepartmentIds: [] as string[],
})

type ParticipantPolicyRow = {
  policy_ref: string
  department_id: string
}

const departmentTree = ref<Array<{ id: string; label: string; children?: Array<{ id: string; label: string; children?: unknown[] }> }>>([])
const departmentOptions = ref<Array<{ value: string; label: string }>>([])
const departmentPoolRows = ref<DepartmentPoolRow[]>([])
const participantPolicyRows = ref<ParticipantPolicyRow[]>([])

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
  nodeRows.value.map((node) => ({
    node_key: node.node_key,
    title: node.title,
    sort_order: node.sort_order,
  })),
)
const dagEdges = computed(() =>
  edgeRows.value.map((edge) => ({
    from_node_key: edge.from_node_key,
    to_node_key: edge.to_node_key,
    is_reject_path: edge.is_reject_path,
  })),
)
const edgeTopologyIssues = computed(() =>
  analyzeEdgeTopology(
    nodeRows.value.map((node) => ({ node_key: node.node_key, sort_order: node.sort_order })),
    edgeRows.value,
  ),
)
const edgeTopologyErrors = computed(() => edgeTopologyIssues.value.filter((item) => item.level === 'error'))
const edgeTopologyWarnings = computed(() => edgeTopologyIssues.value.filter((item) => item.level === 'warning'))

function applyDetail(next: GraphTemplateDesignerDetail): void {
  detail.value = next
  form.name = next.name
  form.description = next.description ?? ''
  form.runKind = (next.config?.run_kind === 'production' ? 'production' : 'batch')
  form.aggregateMode = (next.config?.aggregate_mode === 'streaming' ? 'streaming' : 'batch')
  form.rootAssigneeVar = (next.config?.root_assignee_var as string) ?? ''
  form.aggregateNodeKey = (next.config?.aggregate_node_key as string) ?? ''
  const launchSchema = next.config?.launch_schema
  form.launchSchemaJson = JSON.stringify(launchSchema ?? {}, null, 2)
  const onComplete = next.config?.on_complete as
    | { next_template_code?: string; carry_inputs?: boolean }
    | undefined
  form.onCompleteEnabled = Boolean(onComplete?.next_template_code)
  form.onCompleteNextTemplateCode = onComplete?.next_template_code ?? ''
  form.onCompleteCarryInputs = onComplete?.carry_inputs !== false
  form.schedulable = next.config?.schedulable === true
  form.scopeDepartmentIds = next.scope_department_ids ?? []
  const pools = next.config?.department_pools
  departmentPoolRows.value =
    pools && typeof pools === 'object' && !Array.isArray(pools)
      ? Object.entries(pools as Record<string, string>).map(([pool_key, department_id]) => ({
          pool_key,
          department_id: String(department_id),
        }))
      : []
  const policies = next.config?.participant_policies
  participantPolicyRows.value =
    policies && typeof policies === 'object' && !Array.isArray(policies)
      ? Object.entries(policies as Record<string, unknown>).map(([policy_ref, definition]) => ({
          policy_ref,
          department_id: String((definition as Record<string, unknown>).department_id ?? ''),
        }))
      : []
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

function addDepartmentPoolRow(): void {
  departmentPoolRows.value.push({ pool_key: '', department_id: '' })
}

function removeDepartmentPoolRow(index: number): void {
  departmentPoolRows.value.splice(index, 1)
}

function addParticipantPolicyRow(): void {
  participantPolicyRows.value.push({ policy_ref: '', department_id: '' })
}

function removeParticipantPolicyRow(index: number): void {
  participantPolicyRows.value.splice(index, 1)
}

async function loadDepartments(): Promise<void> {
  try {
    const departments = await listDepartments()
    departmentOptions.value = departments.map((department) => ({
      value: department.id,
      label: `${department.name} (${department.code})`,
    }))
  } catch {
    departmentOptions.value = []
  }
}

async function loadDepartmentTree(): Promise<void> {
  try {
    const tree = await listDepartmentTree()
    departmentTree.value = tree.map((node) => ({
      id: node.id,
      label: node.name,
      children: (node.children ?? []).map((child: { id: string; name: string; children?: unknown[] }) => ({
        id: child.id,
        label: child.name,
        children: child.children ?? [],
      })),
    }))
  } catch {
    departmentTree.value = []
  }
}

function buildTemplateConfig(): Record<string, unknown> | null {
  const launchSchema = parseLaunchSchema()
  if (launchSchema === null) {
    return null
  }
  const config: Record<string, unknown> = {
    ...(detail.value?.config ?? {}),
    run_kind: form.runKind,
    launch_schema: launchSchema,
    aggregate_mode: form.aggregateMode,
  }
  if (typeof (detail.value?.config as Record<string, unknown>)?.seed_version === 'number') {
    config.seed_version = (detail.value?.config as Record<string, unknown>).seed_version
  }
  if (form.rootAssigneeVar.trim()) {
    config.root_assignee_var = form.rootAssigneeVar.trim()
  } else {
    delete config.root_assignee_var
  }
  if (form.aggregateNodeKey.trim()) {
    config.aggregate_node_key = form.aggregateNodeKey.trim()
  } else {
    delete config.aggregate_node_key
  }
  if (form.onCompleteEnabled && form.onCompleteNextTemplateCode.trim()) {
    config.on_complete = {
      next_template_code: form.onCompleteNextTemplateCode.trim(),
      carry_inputs: form.onCompleteCarryInputs,
    }
  } else {
    delete config.on_complete
  }
  if (form.schedulable) {
    config.schedulable = true
  } else {
    delete config.schedulable
  }
  const departmentPools: Record<string, string> = {}
  for (const row of departmentPoolRows.value) {
    const poolKey = row.pool_key.trim()
    if (!poolKey || !row.department_id) {
      continue
    }
    departmentPools[poolKey] = row.department_id
  }
  if (Object.keys(departmentPools).length > 0) {
    config.department_pools = departmentPools
  } else {
    delete config.department_pools
  }
  const participantPolicies: Record<string, Record<string, unknown>> = {}
  for (const row of participantPolicyRows.value) {
    const policyRef = row.policy_ref.trim()
    if (!policyRef || !row.department_id) {
      continue
    }
    participantPolicies[policyRef] = {
      type: 'department_members',
      department_id: row.department_id,
    }
  }
  if (Object.keys(participantPolicies).length > 0) {
    config.participant_policies = participantPolicies
  } else {
    delete config.participant_policies
  }
  return config
}

function buildDraftPayload() {
  const config = buildTemplateConfig()
  if (config === null) {
    return null
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
    scope_department_ids: form.scopeDepartmentIds,
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

async function handleSaveActiveSettings(): Promise<void> {
  if (!templateId.value || isDraft.value) {
    return
  }
  saving.value = true
  try {
    const config = buildTemplateConfig()
    if (config === null) {
      return
    }
    await updateGraphTemplate(templateId.value, {
      name: form.name.trim(),
      description: form.description.trim() || null,
      config,
    })
    applyDetail(await getGraphTemplateDesigner(templateId.value))
    ElMessage.success('设置已保存')
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

function handleNodeRowClick(row: DesignerNodeRow): void {
  selectedNodeKey.value = row.node_key
}

onMounted(async () => {
  await ensureLoaded()
  if (!canAdministerTaskTemplates.value) {
    ElMessage.warning('当前账号无权编辑任务模板')
    void router.replace({ name: 'task-templates' })
    return
  }
  await Promise.all([loadDesigner(), loadDepartments(), loadDepartmentTree()])
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
        <el-button
          v-if="!isDraft"
          type="primary"
          plain
          :loading="saving"
          data-testid="designer-save-settings"
          @click="handleSaveActiveSettings"
        >
          保存设置
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
      v-if="detail && !isDraft"
      type="info"
      :closable="false"
      show-icon
      class="designer__alert"
      title="已发布模板：可「保存设置」更新名称、schedulable、launch_schema 等；改节点/边请「另存新版本」。"
    />

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
          <el-form-item label="模板类型">
            <el-radio-group v-model="form.runKind" :disabled="structureLocked && !isDraft">
              <el-radio value="batch">批次（选题会 / 多步骤流程）</el-radio>
              <el-radio value="production">制作（由批次 fork，不可直接实例化）</el-radio>
            </el-radio-group>
            <p class="designer__hint">创建后不可更改。批次模板可直接实例化；制作模板由选题会汇总派发后自动 fork。</p>
          </el-form-item>
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
          <el-form-item label="根任务执行人变量">
            <el-input
              v-model="form.rootAssigneeVar"
              maxlength="64"
              placeholder="例如 manager_user_id"
            />
            <p class="designer__hint">实例化时从 launch inputs 中读取此键的值作为根任务（ROOT）执行人。空则使用当前用户。</p>
          </el-form-item>
          <el-form-item label="汇总节点键">
            <el-input
              v-model="form.aggregateNodeKey"
              maxlength="64"
              placeholder="例如 N2_AGGREGATE"
            />
            <p class="designer__hint">streaming 模式下分配菜单的控制节点。与对应节点的 node_key 一致。</p>
          </el-form-item>
          <el-form-item label="允许周期定时（F-24 schedulable）">
            <el-switch v-model="form.schedulable" data-testid="designer-schedulable" />
            <p class="designer__hint">开启后模板可被「建立任务 → 定时派发」选用；须为 batch 采集类模板。</p>
          </el-form-item>
          <el-form-item label="完成后触发下一模板（F-23）">
            <el-switch v-model="form.onCompleteEnabled" />
          </el-form-item>
          <el-form-item v-if="form.onCompleteEnabled" label="下一模板 code">
            <el-input
              v-model="form.onCompleteNextTemplateCode"
              maxlength="64"
              placeholder="例如 video_production_per_topic_v1"
              data-testid="designer-on-complete-code"
            />
          </el-form-item>
          <el-form-item v-if="form.onCompleteEnabled" label="继承 inputs">
            <el-switch v-model="form.onCompleteCarryInputs" />
          </el-form-item>
          <el-form-item label="作用范围（部门可见与可发起）">
            <el-tree-select
              v-model="form.scopeDepartmentIds"
              :data="departmentTree"
              multiple
              show-checkbox
              check-strictly
              clearable
              placeholder="留空表示对所有部门可见"
              class="designer__tree-select"
              data-testid="designer-scope-departments"
            />
            <p class="designer__hint">选择对此模板可见的部门。留空则所有部门可见。影响模板列表过滤与实例化部门下拉。</p>
          </el-form-item>
          <el-form-item label="参与者策略（participant_policies）">
            <div class="designer__pool-list">
              <div
                v-for="(row, index) in participantPolicyRows"
                :key="`${row.policy_ref}-${index}`"
                class="designer__pool-row"
              >
                <el-input
                  v-model="row.policy_ref"
                  placeholder="策略名（如 copywriters）"
                  data-testid="designer-policy-ref"
                />
                <el-select
                  v-model="row.department_id"
                  filterable
                  clearable
                  placeholder="选择部门"
                  data-testid="designer-policy-department"
                >
                  <el-option
                    v-for="option in departmentOptions"
                    :key="option.value"
                    :label="option.label"
                    :value="option.value"
                  />
                </el-select>
                <el-button link type="danger" @click="removeParticipantPolicyRow(index)">删除</el-button>
              </div>
              <el-button size="small" data-testid="designer-add-policy" @click="addParticipantPolicyRow">
                添加策略
              </el-button>
            </div>
            <p class="designer__hint">定义实例化时可选的参与者分组。策略名与节点 config.expand_from 对应。留空则实例化时不可选参与者子集。</p>
          </el-form-item>
          <el-form-item label="department_pools（F-26）">
            <div class="designer__pool-list">
              <div
                v-for="(row, index) in departmentPoolRows"
                :key="`${row.pool_key}-${index}`"
                class="designer__pool-row"
              >
                <el-input
                  v-model="row.pool_key"
                  placeholder="pool_key"
                  data-testid="designer-pool-key"
                />
                <el-select
                  v-model="row.department_id"
                  filterable
                  clearable
                  placeholder="选择部门"
                  data-testid="designer-pool-department"
                >
                  <el-option
                    v-for="option in departmentOptions"
                    :key="option.value"
                    :label="option.label"
                    :value="option.value"
                  />
                </el-select>
                <el-button link type="danger" @click="removeDepartmentPoolRow(index)">删除</el-button>
              </div>
              <el-button size="small" data-testid="designer-add-pool" @click="addDepartmentPoolRow">
                添加 pool
              </el-button>
            </div>
          </el-form-item>
        </el-form>
      </el-card>

      <el-card shadow="never" class="designer__panel designer__panel--wide designer__panel--topology">
        <template #header><strong>拓扑预览</strong></template>
        <GraphTemplateDagPreview :nodes="dagNodes" :edges="dagEdges" />
      </el-card>

      <el-card shadow="never" class="designer__panel designer__panel--full">
        <template #header><strong>节点</strong></template>
        <el-table
          class="designer__data-table"
          :data="nodeRows"
          highlight-current-row
          @row-click="handleNodeRowClick"
        >
          <el-table-column prop="node_key" label="节点键" min-width="100" show-overflow-tooltip />
          <el-table-column label="标题" min-width="120">
            <template #default="{ row }">
              <el-input v-model="row.title" :disabled="structureLocked" size="small" />
            </template>
          </el-table-column>
          <el-table-column label="派发" width="112">
            <template #default="{ row }">
              <el-select
                v-model="row.assignment_mode"
                :disabled="structureLocked"
                size="small"
                class="designer__cell-select"
                @change="handleAssignmentModeChange(row)"
              >
                <el-option label="single" value="single" />
                <el-option label="fan_out" value="fan_out" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="汇聚" width="100">
            <template #default="{ row }">
              <el-select
                v-model="row.join_mode"
                :disabled="structureLocked || row.assignment_mode === 'single'"
                size="small"
                class="designer__cell-select"
              >
                <el-option label="all" value="all" />
                <el-option label="any" value="any" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="顺序" width="128" align="center">
            <template #default="{ row }">
              <el-input-number
                v-model="row.sort_order"
                :disabled="structureLocked"
                size="small"
                class="designer__cell-number"
                :min="0"
                controls-position="right"
              />
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
        <p class="designer__hint designer__hint--edge-guide">
          <strong>正常流转</strong>（未勾选打回）：须构成无环 DAG，表示主流程顺序推进。
          <strong>审核 / 打回</strong>（勾选打回）：允许指向上游节点，不参与主流程分层，在预览中以虚线显示。
        </p>
        <el-alert
          v-if="edgeTopologyErrors.length"
          type="error"
          :closable="false"
          show-icon
          class="designer__edge-alert"
          title="边与路由存在问题"
          data-testid="designer-edge-topology-errors"
        >
          <ul class="designer__errors">
            <li v-for="item in edgeTopologyErrors" :key="item.message">{{ item.message }}</li>
          </ul>
        </el-alert>
        <el-alert
          v-if="edgeTopologyWarnings.length"
          type="warning"
          :closable="false"
          show-icon
          class="designer__edge-alert"
          title="边与路由提示"
          data-testid="designer-edge-topology-warnings"
        >
          <ul class="designer__errors">
            <li v-for="item in edgeTopologyWarnings" :key="item.message">{{ item.message }}</li>
          </ul>
        </el-alert>
        <el-table class="designer__data-table" :data="edgeRows" empty-text="暂无边">
          <el-table-column label="起点" min-width="128">
            <template #default="{ row }">
              <el-select
                v-model="row.from_node_key"
                :disabled="structureLocked"
                size="small"
                class="designer__cell-select"
                filterable
              >
                <el-option
                  v-for="option in nodeKeyOptions"
                  :key="option.value"
                  :label="option.label"
                  :value="option.value"
                />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="终点" min-width="128">
            <template #default="{ row }">
              <el-select
                v-model="row.to_node_key"
                :disabled="structureLocked"
                size="small"
                class="designer__cell-select"
                filterable
              >
                <el-option
                  v-for="option in nodeKeyOptions"
                  :key="option.value"
                  :label="option.label"
                  :value="option.value"
                />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="打回" width="72" align="center">
            <template #default="{ row }">
              <el-checkbox v-model="row.is_reject_path" :disabled="structureLocked" />
            </template>
          </el-table-column>
          <el-table-column label="优先级" width="116" align="center">
            <template #default="{ row }">
              <el-input-number
                v-model="row.priority"
                :disabled="structureLocked"
                size="small"
                class="designer__cell-number"
                :min="0"
                controls-position="right"
              />
            </template>
          </el-table-column>
          <el-table-column label="条件（JSON）" min-width="140">
            <template #default="{ row }">
              <el-input
                v-model="row.conditionJson"
                :disabled="structureLocked"
                size="small"
                spellcheck="false"
              />
            </template>
          </el-table-column>
          <el-table-column v-if="!structureLocked" label="操作" width="56" align="center">
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

.designer__hint--edge-guide {
  margin-bottom: 12px;
  line-height: 1.6;
}

.designer__edge-alert {
  margin-bottom: 12px;
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

.designer__panel--topology :deep(.el-card__body) {
  padding: 0;
  overflow: hidden;
}

.designer__data-table {
  width: 100%;
}

.designer__cell-select {
  width: 100%;
}

.designer__cell-number {
  width: 100%;
}

.designer__cell-number :deep(.el-input__wrapper) {
  padding-left: 8px;
  padding-right: 28px;
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

.designer__pool-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.designer__pool-row {
  display: grid;
  grid-template-columns: 1fr 1.5fr auto;
  gap: 8px;
  align-items: center;
}

@media (max-width: 960px) {
  .designer__grid {
    grid-template-columns: 1fr;
  }
}
</style>
