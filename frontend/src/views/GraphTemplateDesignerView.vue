<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import { listDepartments, listDepartmentTree } from '@/api/departments'
import {
  archiveGraphTemplate,
  dryRunGraphTemplate,
  exportGraphTemplate,
  forkGraphTemplateVersion,
  getGraphTemplateDesigner,
  importGraphTemplateDraft,
  publishGraphTemplate,
  saveGraphTemplateDraft,
  updateGraphTemplateTags,
  validateGraphTemplate,
} from '@/api/workflow-graph'
import GraphTemplateDagPreview from '@/components/workflow/GraphTemplateDagPreview.vue'
import { useTaskCenterPermissions } from '@/composables/useTaskCenterPermissions'
import type {
  GraphTemplateDesignerDetail,
  GraphTemplateDryRunResult,
  GraphTemplateNodeDetail,
} from '@/types/workflowVideo'
import {
  KNOWN_NODE_UI_PROFILES,
  buildContextSchema,
  buildLaunchSchema,
  buildRoutingRules,
  parseContextSchema,
  parseLaunchSchema,
  parseRoutingRules,
  type ContextFieldRow,
  type ContextSchemaStyle,
  type LaunchFieldRow,
  type RoutingRuleRow,
} from '@/utils/graphTemplateAuthoring'
import {
  DEPARTMENT_TREE_SELECT_PROPS,
  mapDepartmentTreeSelectNodes,
  normalizeScopeDepartmentIds,
  resolveTemplateScopeMode,
  type DepartmentTreeSelectNode,
} from '@/utils/departmentTreeSelect'
import { analyzeEdgeTopology } from '@/utils/graphTemplateTopology'
import { getErrorMessage } from '@/utils/errors'

type DepartmentPoolRow = {
  pool_key: string
  department_id: string
}

type DesignerNodeRow = GraphTemplateNodeDetail & {
  configJson: string
  uiProfile: string
  routingRulesJson: string
  routingRuleRows: RoutingRuleRow[]
  routingEditorMode: 'structured' | 'json'
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
const archiving = ref(false)
const dryRunning = ref(false)
const dryRunVisible = ref(false)
const dryRunResult = ref<GraphTemplateDryRunResult | null>(null)
const importInputRef = ref<HTMLInputElement | null>(null)
const detail = ref<GraphTemplateDesignerDetail | null>(null)
const validationErrors = ref<string[]>([])
const tagInput = ref<string[]>([])

const form = reactive({
  name: '',
  description: '',
  aggregateMode: 'streaming' as 'batch' | 'streaming',
  launchSchemaJson: '{}',
  launchEditorMode: 'structured' as 'structured' | 'json',
  contextSchemaJson: '{}',
  contextEditorMode: 'structured' as 'structured' | 'json',
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

const departmentTree = ref<DepartmentTreeSelectNode[]>([])
const departmentOptions = ref<Array<{ value: string; label: string }>>([])
const departmentPoolRows = ref<DepartmentPoolRow[]>([])
const participantPolicyRows = ref<ParticipantPolicyRow[]>([])
const launchFieldRows = ref<LaunchFieldRow[]>([])
const contextFieldRows = ref<ContextFieldRow[]>([])
const contextSchemaStyle = ref<ContextSchemaStyle>('json_schema')

const nodeRows = ref<DesignerNodeRow[]>([])
const edgeRows = ref<DesignerEdgeRow[]>([])
const selectedNodeKey = ref<string | null>(null)

const { ensureLoaded, canAdministerTaskTemplates } = useTaskCenterPermissions()

const templateId = computed(() => String(route.params.id ?? ''))
const isDraft = computed(() => detail.value?.status === 'draft')
const isArchived = computed(() => detail.value?.status === 'archived')
const definitionLocked = computed(() => !isDraft.value)
const structureLocked = computed(() => detail.value?.structure_locked ?? false)
const graphLocked = computed(() => structureLocked.value || definitionLocked.value)
const selectedNode = computed(
  () => nodeRows.value.find((node) => node.node_key === selectedNodeKey.value) ?? null,
)
const nodeKeyOptions = computed(() =>
  nodeRows.value.map((node) => ({
    value: node.node_key,
    label: `${node.node_key} · ${node.title}`,
  })),
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
const edgeTopologyErrors = computed(() =>
  edgeTopologyIssues.value.filter((item) => item.level === 'error'),
)
const edgeTopologyWarnings = computed(() =>
  edgeTopologyIssues.value.filter((item) => item.level === 'warning'),
)

function unmanagedNodeConfig(config: Record<string, unknown> | undefined): Record<string, unknown> {
  const next = { ...config }
  delete next.ui_profile
  delete next.routing_rules
  return next
}

function applyDetail(next: GraphTemplateDesignerDetail): void {
  detail.value = next
  form.name = next.name
  form.description = next.description ?? ''
  tagInput.value = [...(next.tags ?? [])]
  form.aggregateMode = next.config?.aggregate_mode === 'streaming' ? 'streaming' : 'batch'
  form.rootAssigneeVar = (next.config?.root_assignee_var as string) ?? ''
  form.aggregateNodeKey = (next.config?.aggregate_node_key as string) ?? ''
  const launchSchema = next.config?.launch_schema
  form.launchSchemaJson = JSON.stringify(launchSchema ?? {}, null, 2)
  const parsedLaunch = parseLaunchSchema(launchSchema)
  launchFieldRows.value = parsedLaunch.rows
  form.launchEditorMode = parsedLaunch.structuredCompatible ? 'structured' : 'json'
  const contextSchema = next.context_schema ?? {}
  form.contextSchemaJson = JSON.stringify(contextSchema, null, 2)
  const parsedContext = parseContextSchema(contextSchema)
  contextFieldRows.value = parsedContext.rows
  contextSchemaStyle.value = parsedContext.style
  form.contextEditorMode = parsedContext.structuredCompatible ? 'structured' : 'json'
  const onComplete = next.config?.on_complete as
    | { next_template_code?: string; carry_inputs?: boolean }
    | undefined
  form.onCompleteEnabled = Boolean(onComplete?.next_template_code)
  form.onCompleteNextTemplateCode = onComplete?.next_template_code ?? ''
  form.onCompleteCarryInputs = onComplete?.carry_inputs !== false
  form.schedulable = next.config?.schedulable === true
  form.scopeDepartmentIds = normalizeScopeDepartmentIds(next.scope_department_ids ?? [])
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
  nodeRows.value = next.nodes.map((node) => {
    const parsedRouting = parseRoutingRules(node.config?.routing_rules)
    return {
      ...node,
      assignment_mode: node.assignment_mode ?? 'single',
      join_mode: node.join_mode ?? 'all',
      routing_mode: node.routing_mode ?? 'inclusive',
      configJson: JSON.stringify(unmanagedNodeConfig(node.config), null, 2),
      uiProfile: typeof node.config?.ui_profile === 'string' ? node.config.ui_profile : '',
      routingRulesJson: JSON.stringify((node.config?.routing_rules as unknown) ?? [], null, 2),
      routingRuleRows: parsedRouting.rows,
      routingEditorMode: parsedRouting.structuredCompatible ? 'structured' : 'json',
    }
  })
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

function parseObjectJson(value: string, label: string): Record<string, unknown> | null {
  try {
    const parsed = JSON.parse(value || '{}') as unknown
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>
    }
    ElMessage.warning(`${label} 必须是 JSON 对象`)
    return null
  } catch {
    ElMessage.warning(`${label} JSON 格式无效`)
    return null
  }
}

function parseLaunchSchemaValue(): Record<string, unknown> | null {
  const raw = parseObjectJson(form.launchSchemaJson, 'launch_schema')
  if (raw === null || form.launchEditorMode === 'json') {
    return raw
  }
  return buildLaunchSchema(raw, launchFieldRows.value)
}

function parseContextSchemaValue(): Record<string, unknown> | null {
  const raw = parseObjectJson(form.contextSchemaJson, 'context_schema')
  if (raw === null || form.contextEditorMode === 'json') {
    return raw
  }
  return buildContextSchema(contextFieldRows.value, contextSchemaStyle.value, raw)
}

function addLaunchFieldRow(): void {
  launchFieldRows.value.push({ key: '', label: '', type: 'text', required: false, policy_ref: '' })
}

function removeLaunchFieldRow(index: number): void {
  launchFieldRows.value.splice(index, 1)
}

function addContextFieldRow(): void {
  contextFieldRows.value.push({ key: '', type: 'string', required: false, description: '' })
}

function removeContextFieldRow(index: number): void {
  contextFieldRows.value.splice(index, 1)
}

function setLaunchEditorMode(mode: 'structured' | 'json'): void {
  if (mode === 'json') {
    const base = parseObjectJson(form.launchSchemaJson, 'launch_schema') ?? {}
    form.launchSchemaJson = JSON.stringify(buildLaunchSchema(base, launchFieldRows.value), null, 2)
    form.launchEditorMode = mode
    return
  }
  const raw = parseObjectJson(form.launchSchemaJson, 'launch_schema')
  if (raw === null) {
    return
  }
  const parsed = parseLaunchSchema(raw)
  if (!parsed.structuredCompatible) {
    ElMessage.warning('当前 launch_schema 含高级结构，请继续使用 JSON 模式')
    return
  }
  launchFieldRows.value = parsed.rows
  form.launchEditorMode = mode
}

function setContextEditorMode(mode: 'structured' | 'json'): void {
  if (mode === 'json') {
    const base = parseObjectJson(form.contextSchemaJson, 'context_schema') ?? {}
    form.contextSchemaJson = JSON.stringify(
      buildContextSchema(contextFieldRows.value, contextSchemaStyle.value, base),
      null,
      2,
    )
    form.contextEditorMode = mode
    return
  }
  const raw = parseObjectJson(form.contextSchemaJson, 'context_schema')
  if (raw === null) {
    return
  }
  const parsed = parseContextSchema(raw)
  if (!parsed.structuredCompatible) {
    ElMessage.warning('当前 context_schema 含高级结构，请继续使用 JSON 模式')
    return
  }
  contextFieldRows.value = parsed.rows
  contextSchemaStyle.value = parsed.style
  form.contextEditorMode = mode
}

function addRoutingRuleRow(kind: 'if' | 'else' = 'if'): void {
  selectedNode.value?.routingRuleRows.push({
    kind,
    field: '',
    operator: 'eq',
    valueText: '',
    target_node_key: '',
  })
}

function removeRoutingRuleRow(index: number): void {
  selectedNode.value?.routingRuleRows.splice(index, 1)
}

function setRoutingEditorMode(node: DesignerNodeRow, mode: 'structured' | 'json'): void {
  if (mode === 'json') {
    node.routingRulesJson = JSON.stringify(buildRoutingRules(node.routingRuleRows), null, 2)
    node.routingEditorMode = mode
    return
  }
  try {
    const parsed = parseRoutingRules(JSON.parse(node.routingRulesJson || '[]') as unknown)
    if (!parsed.structuredCompatible) {
      ElMessage.warning('当前 routing_rules 含复合条件，请继续使用 JSON 模式')
      return
    }
    node.routingRuleRows = parsed.rows
    node.routingEditorMode = mode
  } catch {
    ElMessage.warning('routing_rules JSON 格式无效')
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
    departmentTree.value = mapDepartmentTreeSelectNodes(await listDepartmentTree())
  } catch {
    departmentTree.value = []
  }
}

function buildTemplateConfig(): Record<string, unknown> | null {
  const launchSchema = parseLaunchSchemaValue()
  if (launchSchema === null) {
    return null
  }
  const existingConfig = detail.value?.config
  const config: Record<string, unknown> = {
    ...existingConfig,
    launch_schema: launchSchema,
    aggregate_mode: form.aggregateMode,
  }
  if (typeof existingConfig?.seed_version === 'number') {
    config.seed_version = existingConfig.seed_version
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
  const contextSchema = parseContextSchemaValue()
  if (contextSchema === null) {
    return null
  }
  const nodes = nodeRows.value.map((node, index) => {
    let nodeConfig: Record<string, unknown>
    try {
      nodeConfig = JSON.parse(node.configJson || '{}') as Record<string, unknown>
    } catch {
      throw new Error(`节点 ${node.node_key} 的 config JSON 无效`)
    }
    if (node.uiProfile.trim()) {
      nodeConfig.ui_profile = node.uiProfile.trim()
    } else {
      delete nodeConfig.ui_profile
    }
    let routingRules: unknown
    if (node.routingEditorMode === 'structured') {
      routingRules = buildRoutingRules(node.routingRuleRows)
    } else {
      try {
        routingRules = JSON.parse(node.routingRulesJson || '[]') as unknown
      } catch {
        throw new Error(`节点 ${node.node_key} 的 routing_rules JSON 无效`)
      }
    }
    if (!Array.isArray(routingRules)) {
      throw new Error(`节点 ${node.node_key} 的 routing_rules 必须是数组`)
    }
    if (routingRules.length > 0) {
      nodeConfig.routing_rules = routingRules
    } else {
      delete nodeConfig.routing_rules
    }
    const assignmentMode = node.assignment_mode === 'fan_out' ? 'fan_out' : 'single'
    return {
      node_key: node.node_key,
      title: node.title.trim(),
      sort_order: node.sort_order || index + 1,
      assignment_mode: assignmentMode,
      join_mode: assignmentMode === 'single' ? 'all' : node.join_mode === 'any' ? 'any' : 'all',
      routing_mode: node.routing_mode ?? 'inclusive',
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
  const scopeDepartmentIds = normalizeScopeDepartmentIds(form.scopeDepartmentIds)
  return {
    name: form.name.trim(),
    description: form.description.trim() || null,
    config,
    context_schema: contextSchema,
    scope_mode: resolveTemplateScopeMode(scopeDepartmentIds),
    scope_department_ids: scopeDepartmentIds,
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

async function handleSaveTags(): Promise<void> {
  if (!templateId.value) {
    return
  }
  saving.value = true
  try {
    await updateGraphTemplateTags(templateId.value, tagInput.value)
    applyDetail(await getGraphTemplateDesigner(templateId.value))
    ElMessage.success('标签已保存')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    saving.value = false
  }
}

async function handleArchive(): Promise<void> {
  if (!templateId.value || detail.value?.status !== 'active') {
    return
  }
  try {
    await ElMessageBox.confirm(
      `确认归档「${detail.value.name}」？归档后不可原地编辑。`,
      '归档模板',
      { type: 'warning', confirmButtonText: '归档', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  archiving.value = true
  try {
    await archiveGraphTemplate(templateId.value)
    ElMessage.success('模板已归档')
    void router.push({ name: 'task-templates', query: { status: 'archived' } })
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    archiving.value = false
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
  <div v-loading="loading" class="designer page" data-testid="graph-template-designer">
    <header class="designer__header">
      <div>
        <el-button link type="primary" data-testid="designer-back" @click="goBack"
          >← 返回模板列表</el-button
        >
        <h1 class="designer__title">
          {{ detail?.name || '模板设计器' }}
        </h1>
        <p v-if="detail" class="designer__meta">
          {{ detail.code }} · v{{ detail.version }} ·
          <el-tag size="small" effect="plain">{{ detail.status }}</el-tag>
          <el-tag v-if="structureLocked" size="small" type="warning" effect="plain"
            >结构已锁定</el-tag
          >
        </p>
      </div>
      <div class="designer__actions">
        <el-button :loading="validating" data-testid="designer-validate" @click="handleValidate"
          >校验</el-button
        >
        <el-button :loading="dryRunning" data-testid="designer-dry-run" @click="handleDryRun"
          >试跑</el-button
        >
        <el-button data-testid="designer-export" @click="handleExportJson">导出 JSON</el-button>
        <el-button
          v-if="isDraft && !graphLocked"
          data-testid="designer-import"
          @click="openImportPicker"
        >
          导入 JSON
        </el-button>
        <input
          ref="importInputRef"
          type="file"
          accept="application/json,.json"
          hidden
          @change="handleImportFile"
        />
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
          :loading="forking"
          :type="definitionLocked ? 'primary' : 'default'"
          data-testid="designer-fork"
          @click="handleForkVersion"
        >
          另存新版本
        </el-button>
        <el-button
          v-if="detail?.status === 'active'"
          type="warning"
          plain
          :loading="archiving"
          data-testid="designer-archive"
          @click="handleArchive"
        >
          归档
        </el-button>
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
      v-if="detail && definitionLocked"
      type="info"
      :closable="false"
      show-icon
      class="designer__alert"
      title="已发布模板不可原地修改。请使用另存新版本或派生草稿。"
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
          <el-form-item label="名称" required>
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
          <el-form-item label="标签">
            <el-select
              v-model="tagInput"
              multiple
              filterable
              allow-create
              default-first-option
              :disabled="isArchived"
              placeholder="输入后回车添加"
              data-testid="designer-tags"
              style="width: 100%"
            />
            <el-button
              class="designer__tag-save"
              size="small"
              :loading="saving"
              :disabled="isArchived"
              data-testid="designer-tags-save"
              @click="handleSaveTags"
            >
              保存标签
            </el-button>
          </el-form-item>
          <el-form-item v-if="detail?.capabilities" label="派生能力（只读）">
            <div data-testid="designer-capabilities">
              <el-tag
                v-for="hint in detail.capabilities.derived_hints"
                :key="hint"
                size="small"
                effect="plain"
              >
                {{ hint }}
              </el-tag>
              <span v-if="!detail.capabilities.derived_hints.length">—</span>
            </div>
          </el-form-item>
          <el-form-item label="汇总模式">
            <el-radio-group v-model="form.aggregateMode" :disabled="graphLocked">
              <el-radio value="batch">batch（结束采集后汇总）</el-radio>
              <el-radio value="streaming">streaming（增量派发）</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="发起表单（launch_schema）">
            <div class="designer__authoring" data-testid="designer-launch-schema">
              <el-radio-group
                :model-value="form.launchEditorMode"
                :disabled="definitionLocked"
                size="small"
                @change="setLaunchEditorMode($event as 'structured' | 'json')"
              >
                <el-radio-button value="structured">结构化</el-radio-button>
                <el-radio-button value="json">高级 JSON</el-radio-button>
              </el-radio-group>
              <template v-if="form.launchEditorMode === 'structured'">
                <div
                  v-for="(field, index) in launchFieldRows"
                  :key="`${field.key}-${index}`"
                  class="designer__authoring-row designer__authoring-row--launch"
                >
                  <el-input v-model="field.key" :disabled="definitionLocked" placeholder="字段键" />
                  <el-input
                    v-model="field.label"
                    :disabled="definitionLocked"
                    placeholder="显示名称"
                  />
                  <el-select v-model="field.type" :disabled="definitionLocked" placeholder="类型">
                    <el-option label="单行文本" value="text" />
                    <el-option label="多行文本" value="textarea" />
                    <el-option label="日期时间" value="datetime" />
                    <el-option label="用户" value="user" />
                    <el-option label="多用户" value="user_multi" />
                    <el-option label="部门" value="department" />
                  </el-select>
                  <el-input
                    v-model="field.policy_ref"
                    :disabled="definitionLocked"
                    placeholder="策略引用（可选）"
                  />
                  <el-checkbox v-model="field.required" :disabled="definitionLocked"
                    >必填</el-checkbox
                  >
                  <el-button
                    link
                    type="danger"
                    :disabled="definitionLocked"
                    @click="removeLaunchFieldRow(index)"
                    >删除</el-button
                  >
                </div>
                <el-button
                  size="small"
                  :disabled="definitionLocked"
                  data-testid="designer-add-launch-field"
                  @click="addLaunchFieldRow"
                >
                  添加发起字段
                </el-button>
              </template>
              <el-input
                v-else
                v-model="form.launchSchemaJson"
                :disabled="definitionLocked"
                type="textarea"
                :rows="10"
                class="designer__json"
                spellcheck="false"
              />
              <p class="designer__hint">常用字段使用结构化表单；复杂扩展可切换到高级 JSON。</p>
            </div>
          </el-form-item>
          <el-form-item label="运行上下文（context_schema）">
            <div class="designer__authoring" data-testid="designer-context-schema">
              <el-radio-group
                :model-value="form.contextEditorMode"
                :disabled="definitionLocked"
                size="small"
                @change="setContextEditorMode($event as 'structured' | 'json')"
              >
                <el-radio-button value="structured">结构化</el-radio-button>
                <el-radio-button value="json">高级 JSON</el-radio-button>
              </el-radio-group>
              <template v-if="form.contextEditorMode === 'structured'">
                <div
                  v-for="(field, index) in contextFieldRows"
                  :key="`${field.key}-${index}`"
                  class="designer__authoring-row designer__authoring-row--context"
                >
                  <el-input
                    v-model="field.key"
                    :disabled="definitionLocked"
                    placeholder="上下文键"
                  />
                  <el-select v-model="field.type" :disabled="definitionLocked" placeholder="类型">
                    <el-option label="文本" value="string" />
                    <el-option label="数字" value="number" />
                    <el-option label="整数" value="integer" />
                    <el-option label="布尔" value="boolean" />
                    <el-option label="对象" value="object" />
                    <el-option label="数组" value="array" />
                  </el-select>
                  <el-input
                    v-model="field.description"
                    :disabled="definitionLocked"
                    placeholder="说明（可选）"
                  />
                  <el-checkbox v-model="field.required" :disabled="definitionLocked"
                    >必填</el-checkbox
                  >
                  <el-button
                    link
                    type="danger"
                    :disabled="definitionLocked"
                    @click="removeContextFieldRow(index)"
                    >删除</el-button
                  >
                </div>
                <el-button
                  size="small"
                  :disabled="definitionLocked"
                  data-testid="designer-add-context-field"
                  @click="addContextFieldRow"
                >
                  添加上下文字段
                </el-button>
              </template>
              <el-input
                v-else
                v-model="form.contextSchemaJson"
                :disabled="definitionLocked"
                type="textarea"
                :rows="10"
                class="designer__json"
                spellcheck="false"
              />
              <p class="designer__hint">
                用于声明 Run Context 的键与类型；高级 JSON 保留完整 schema 表达能力。
              </p>
            </div>
          </el-form-item>
          <el-form-item label="根任务执行人变量">
            <el-input
              v-model="form.rootAssigneeVar"
              :disabled="definitionLocked"
              maxlength="64"
              placeholder="例如 manager_user_id"
            />
            <p class="designer__hint">
              实例化时从 launch inputs 中读取此键的值作为根任务（ROOT）执行人。空则使用当前用户。
            </p>
          </el-form-item>
          <el-form-item label="汇总节点键">
            <el-input
              v-model="form.aggregateNodeKey"
              :disabled="definitionLocked"
              maxlength="64"
              placeholder="例如 N2_AGGREGATE"
            />
            <p class="designer__hint">
              streaming 模式下分配菜单的控制节点。与对应节点的 node_key 一致。
            </p>
          </el-form-item>
          <el-form-item label="允许周期定时（F-24 schedulable）">
            <el-switch
              v-model="form.schedulable"
              :disabled="definitionLocked"
              data-testid="designer-schedulable"
            />
            <p class="designer__hint">
              开启后模板可被「建立任务 → 定时派发」选用；须为 batch 采集类模板。
            </p>
          </el-form-item>
          <el-form-item label="完成后触发下一模板（F-23）">
            <el-switch v-model="form.onCompleteEnabled" :disabled="definitionLocked" />
          </el-form-item>
          <el-form-item v-if="form.onCompleteEnabled" label="下一模板 code">
            <el-input
              v-model="form.onCompleteNextTemplateCode"
              :disabled="definitionLocked"
              maxlength="64"
              placeholder="例如 video_production_per_topic_v1"
              data-testid="designer-on-complete-code"
            />
          </el-form-item>
          <el-form-item v-if="form.onCompleteEnabled" label="继承 inputs">
            <el-switch v-model="form.onCompleteCarryInputs" :disabled="definitionLocked" />
          </el-form-item>
          <el-form-item label="作用范围（部门可见与可发起）">
            <el-tree-select
              v-model="form.scopeDepartmentIds"
              :data="departmentTree"
              :props="DEPARTMENT_TREE_SELECT_PROPS"
              node-key="id"
              :disabled="definitionLocked"
              multiple
              filterable
              show-checkbox
              check-strictly
              clearable
              placeholder="留空表示对所有部门可见"
              class="designer__tree-select"
              data-testid="designer-scope-departments"
            />
            <p class="designer__hint">
              选择对此模板可见的部门。留空则所有部门可见。影响模板列表过滤与实例化部门下拉。
            </p>
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
                  :disabled="definitionLocked"
                  placeholder="策略名（如 copywriters）"
                  data-testid="designer-policy-ref"
                />
                <el-select
                  v-model="row.department_id"
                  :disabled="definitionLocked"
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
                <el-button
                  link
                  type="danger"
                  :disabled="definitionLocked"
                  @click="removeParticipantPolicyRow(index)"
                  >删除</el-button
                >
              </div>
              <el-button
                size="small"
                :disabled="definitionLocked"
                data-testid="designer-add-policy"
                @click="addParticipantPolicyRow"
              >
                添加策略
              </el-button>
            </div>
            <p class="designer__hint">
              定义实例化时可选的参与者分组。策略名与节点 config.expand_from
              对应。留空则实例化时不可选参与者子集。
            </p>
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
                  :disabled="definitionLocked"
                  placeholder="pool_key"
                  data-testid="designer-pool-key"
                />
                <el-select
                  v-model="row.department_id"
                  :disabled="definitionLocked"
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
                <el-button
                  link
                  type="danger"
                  :disabled="definitionLocked"
                  @click="removeDepartmentPoolRow(index)"
                  >删除</el-button
                >
              </div>
              <el-button
                size="small"
                :disabled="definitionLocked"
                data-testid="designer-add-pool"
                @click="addDepartmentPoolRow"
              >
                添加 pool
              </el-button>
            </div>
          </el-form-item>
        </el-form>
      </el-card>

      <el-card
        shadow="never"
        class="designer__panel designer__panel--wide designer__panel--topology"
      >
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
              <el-input v-model="row.title" :disabled="graphLocked" size="small" />
            </template>
          </el-table-column>
          <el-table-column label="派发" width="112">
            <template #default="{ row }">
              <el-select
                v-model="row.assignment_mode"
                :disabled="graphLocked"
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
                :disabled="graphLocked || row.assignment_mode === 'single'"
                size="small"
                class="designer__cell-select"
              >
                <el-option label="all" value="all" />
                <el-option label="any" value="any" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="路由" width="126">
            <template #default="{ row }">
              <el-select
                v-model="row.routing_mode"
                :disabled="graphLocked"
                size="small"
                class="designer__cell-select"
              >
                <el-option label="exclusive" value="exclusive" />
                <el-option label="inclusive" value="inclusive" />
                <el-option label="parallel" value="parallel" />
                <el-option label="first_match" value="first_match" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="顺序" width="128" align="center">
            <template #default="{ row }">
              <el-input-number
                v-model="row.sort_order"
                :disabled="graphLocked"
                size="small"
                class="designer__cell-number"
                :min="0"
                controls-position="right"
              />
            </template>
          </el-table-column>
        </el-table>

        <div v-if="selectedNode" class="designer__node-config">
          <h3>节点运行时配置：{{ selectedNode.node_key }}</h3>
          <div class="designer__node-field" data-testid="designer-node-ui-profile">
            <label>运行时外观（ui_profile）</label>
            <el-select
              v-model="selectedNode.uiProfile"
              :disabled="graphLocked"
              filterable
              allow-create
              clearable
              placeholder="选择常用 profile 或输入自定义值"
            >
              <el-option
                v-for="profile in KNOWN_NODE_UI_PROFILES"
                :key="profile.value"
                :label="`${profile.label} · ${profile.value}`"
                :value="profile.value"
              />
            </el-select>
            <p class="designer__hint">
              这是节点运行时 Action
              Profile，不是模板类型；自定义值会原样保存，运行端不识别时回退通用视图。
            </p>
          </div>
          <h3 class="designer__subheading">高级节点 config（JSON）</h3>
          <el-input
            v-model="selectedNode.configJson"
            type="textarea"
            :rows="12"
            class="designer__json"
            :disabled="graphLocked"
            spellcheck="false"
          />
          <div class="designer__routing" data-testid="designer-routing-rules">
            <h3 class="designer__subheading">路由规则（routing_rules）</h3>
            <el-radio-group
              :model-value="selectedNode.routingEditorMode"
              :disabled="graphLocked"
              size="small"
              @change="setRoutingEditorMode(selectedNode, $event as 'structured' | 'json')"
            >
              <el-radio-button value="structured">结构化</el-radio-button>
              <el-radio-button value="json">高级 JSON</el-radio-button>
            </el-radio-group>
            <template v-if="selectedNode.routingEditorMode === 'structured'">
              <div
                v-for="(rule, index) in selectedNode.routingRuleRows"
                :key="`${rule.kind}-${index}`"
                class="designer__authoring-row designer__authoring-row--routing"
              >
                <el-select v-model="rule.kind" :disabled="graphLocked">
                  <el-option label="IF" value="if" />
                  <el-option label="ELSE" value="else" />
                </el-select>
                <el-input
                  v-if="rule.kind === 'if'"
                  v-model="rule.field"
                  :disabled="graphLocked"
                  placeholder="上下文字段"
                />
                <el-select
                  v-if="rule.kind === 'if'"
                  v-model="rule.operator"
                  :disabled="graphLocked"
                >
                  <el-option
                    v-for="operator in [
                      'eq',
                      'neq',
                      'gt',
                      'gte',
                      'lt',
                      'lte',
                      'in',
                      'not_in',
                      'contains',
                      'exists',
                    ]"
                    :key="operator"
                    :label="operator"
                    :value="operator"
                  />
                </el-select>
                <el-input
                  v-if="rule.kind === 'if' && rule.operator !== 'exists'"
                  v-model="rule.valueText"
                  :disabled="graphLocked"
                  placeholder="比较值（支持 JSON）"
                />
                <el-select
                  v-model="rule.target_node_key"
                  :disabled="graphLocked"
                  filterable
                  placeholder="目标节点"
                >
                  <el-option
                    v-for="option in nodeKeyOptions"
                    :key="option.value"
                    :label="option.label"
                    :value="option.value"
                  />
                </el-select>
                <el-button
                  link
                  type="danger"
                  :disabled="graphLocked"
                  @click="removeRoutingRuleRow(index)"
                  >删除</el-button
                >
              </div>
              <div class="designer__authoring-actions">
                <el-button
                  size="small"
                  :disabled="graphLocked"
                  data-testid="designer-add-routing-if"
                  @click="addRoutingRuleRow('if')"
                  >添加 IF</el-button
                >
                <el-button
                  size="small"
                  :disabled="graphLocked"
                  data-testid="designer-add-routing-else"
                  @click="addRoutingRuleRow('else')"
                  >添加 ELSE</el-button
                >
              </div>
            </template>
            <template v-else>
              <p class="designer__hint">
                高级模式支持嵌套 all/any 条件；保存时仍执行服务端拓扑校验。
              </p>
              <el-input
                v-model="selectedNode.routingRulesJson"
                type="textarea"
                :rows="8"
                class="designer__json"
                :disabled="graphLocked"
                spellcheck="false"
              />
            </template>
          </div>
        </div>
      </el-card>

      <el-card shadow="never" class="designer__panel designer__panel--full">
        <template #header>
          <div class="designer__card-header">
            <strong>边与路由</strong>
            <el-button
              v-if="!graphLocked"
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
          <strong>审核 / 打回</strong
          >（勾选打回）：允许指向上游节点，不参与主流程分层，在预览中以虚线显示。
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
                :disabled="graphLocked"
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
                :disabled="graphLocked"
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
              <el-checkbox v-model="row.is_reject_path" :disabled="graphLocked" />
            </template>
          </el-table-column>
          <el-table-column label="优先级" width="116" align="center">
            <template #default="{ row }">
              <el-input-number
                v-model="row.priority"
                :disabled="graphLocked"
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
                :disabled="graphLocked"
                size="small"
                spellcheck="false"
              />
            </template>
          </el-table-column>
          <el-table-column v-if="!graphLocked" label="操作" width="56" align="center">
            <template #default="{ $index }">
              <el-button link type="danger" @click="removeEdgeRow($index)">删</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>

    <el-dialog
      v-model="dryRunVisible"
      title="试跑结果"
      width="720px"
      data-testid="designer-dry-run-dialog"
    >
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
          <pre class="designer__json-preview">{{
            JSON.stringify(dryRunResult.schema_snapshot, null, 2)
          }}</pre>
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

.designer__node-field,
.designer__routing,
.designer__authoring {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
}

.designer__node-field {
  margin-bottom: 16px;
}

.designer__node-field > label {
  font-size: 13px;
  font-weight: 600;
}

.designer__authoring-row {
  display: grid;
  gap: 8px;
  align-items: center;
}

.designer__authoring-row--launch {
  grid-template-columns: 1fr 1fr;
}

.designer__authoring-row--context {
  grid-template-columns: 1fr 1fr;
}

.designer__authoring-row--routing {
  grid-template-columns: 88px 1fr 112px 1fr 1.2fr auto;
}

.designer__authoring-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.designer__tag-save {
  margin-top: 8px;
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

  .designer__authoring-row--launch,
  .designer__authoring-row--context,
  .designer__authoring-row--routing {
    grid-template-columns: 1fr;
  }
}
</style>
