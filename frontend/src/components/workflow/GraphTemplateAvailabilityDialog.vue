<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import { listDepartments } from '@/api/departments'
import {
  expandGraphTemplateAvailabilityScope,
  listGraphTemplateAvailabilityScopeEvents,
} from '@/api/workflow-graph'
import type { Department } from '@/types/api'
import type { GraphTemplateScopeEvent, GraphTemplateSummary } from '@/types/workflowVideo'
import { getErrorMessage } from '@/utils/errors'

const props = defineProps<{
  modelValue: boolean
  template: GraphTemplateSummary | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  updated: []
}>()

const loading = ref(false)
const submitting = ref(false)
const departments = ref<Department[]>([])
const events = ref<GraphTemplateScopeEvent[]>([])
const selectedDepartmentIds = ref<string[]>([])
const expandToGlobal = ref(false)
const reason = ref('')

const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})
const currentDepartmentIds = computed(() => props.template?.scope_department_ids ?? [])
const isAlreadyGlobal = computed(() => props.template?.scope_mode === 'global')
const departmentNameById = computed(
  () => new Map(departments.value.map((department) => [department.id, department.name])),
)
const activeDepartments = computed(() => departments.value.filter((department) => department.is_active))
const hasExpansion = computed(() => {
  if (isAlreadyGlobal.value) {
    return false
  }
  if (expandToGlobal.value) {
    return true
  }
  const current = new Set(currentDepartmentIds.value)
  return selectedDepartmentIds.value.some((departmentId) => !current.has(departmentId))
})

function departmentLabel(departmentId: string): string {
  return departmentNameById.value.get(departmentId) ?? departmentId
}

function formatEventScope(event: GraphTemplateScopeEvent): string {
  if (event.after_scope_mode === 'global') {
    return '扩大为全公司可用'
  }
  const names = event.added_department_ids.map(departmentLabel)
  return names.length ? `新增：${names.join('、')}` : '部门范围已更新'
}

function formatDateTime(value: string): string {
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString('zh-CN', { hour12: false })
}

async function loadContext(): Promise<void> {
  const template = props.template
  if (!template) {
    return
  }
  loading.value = true
  selectedDepartmentIds.value = [...(template.scope_department_ids ?? [])]
  expandToGlobal.value = false
  reason.value = ''
  try {
    const [departmentList, history] = await Promise.all([
      listDepartments(),
      listGraphTemplateAvailabilityScopeEvents(template.id),
    ])
    departments.value = departmentList
    events.value = history
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

async function submit(): Promise<void> {
  const template = props.template
  if (!template || isAlreadyGlobal.value) {
    return
  }
  const current = new Set(currentDepartmentIds.value)
  if (!expandToGlobal.value && [...current].some((departmentId) => !selectedDepartmentIds.value.includes(departmentId))) {
    selectedDepartmentIds.value = [...current]
    ElMessage.warning('已发布模板不可移除已有部门；如需缩小范围，请发布新版本。')
    return
  }
  if (!hasExpansion.value) {
    ElMessage.warning('请至少新增一个部门，或选择扩大为全公司可用。')
    return
  }
  if (reason.value.trim().length < 2) {
    ElMessage.warning('请填写授权原因。')
    return
  }

  submitting.value = true
  try {
    await expandGraphTemplateAvailabilityScope(template.id, {
      scope_mode: expandToGlobal.value ? 'global' : 'departments',
      scope_department_ids: expandToGlobal.value ? [] : selectedDepartmentIds.value,
      reason: reason.value.trim(),
    })
    ElMessage.success('模板可用部门已更新')
    emit('updated')
    visible.value = false
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    submitting.value = false
  }
}

watch(
  () => props.modelValue,
  (next) => {
    if (next) {
      void loadContext()
    }
  },
  { immediate: true },
)
</script>

<template>
  <el-dialog v-model="visible" title="可用部门管理" width="620px" data-testid="template-availability-dialog">
    <div v-loading="loading" class="availability-dialog">
      <el-alert
        v-if="isAlreadyGlobal"
        type="success"
        :closable="false"
        show-icon
        title="当前模板已对所有部门可用"
      />
      <template v-else>
        <el-alert
          type="info"
          :closable="false"
          title="已发布模板只允许扩大可用范围。现有部门不会被移除，已有运行实例不受影响。"
        />
        <el-form label-position="top" class="availability-dialog__form">
          <el-form-item label="可用部门">
            <el-select
              v-model="selectedDepartmentIds"
              multiple
              filterable
              :disabled="expandToGlobal"
              placeholder="选择要新增的部门"
              style="width: 100%"
              data-testid="template-availability-departments"
            >
              <el-option
                v-for="department in activeDepartments"
                :key="department.id"
                :label="department.name"
                :value="department.id"
                :disabled="currentDepartmentIds.includes(department.id)"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="全公司可用">
            <el-switch v-model="expandToGlobal" data-testid="template-availability-global" />
          </el-form-item>
          <el-form-item label="授权原因（写入审计记录）" required>
            <el-input
              v-model="reason"
              type="textarea"
              :rows="3"
              maxlength="500"
              show-word-limit
              placeholder="例如：新增市场二部参与试用"
              data-testid="template-availability-reason"
            />
          </el-form-item>
        </el-form>
      </template>

      <section class="availability-dialog__history">
        <h3>变更记录</h3>
        <el-empty v-if="events.length === 0" description="暂无变更记录" :image-size="64" />
        <el-timeline v-else>
          <el-timeline-item
            v-for="event in events"
            :key="event.id"
            :timestamp="formatDateTime(event.created_at)"
          >
            <strong>{{ formatEventScope(event) }}</strong>
            <p>{{ event.reason }}</p>
            <p>操作人：{{ event.actor_display_name || event.actor_email || event.actor_user_id }}</p>
          </el-timeline-item>
        </el-timeline>
      </section>
    </div>

    <template #footer>
      <el-button @click="visible = false">关闭</el-button>
      <el-button
        v-if="!isAlreadyGlobal"
        type="primary"
        :loading="submitting"
        :disabled="!hasExpansion"
        data-testid="template-availability-submit"
        @click="submit"
      >
        确认扩大范围
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.availability-dialog__form {
  margin-top: 18px;
}

.availability-dialog__history {
  margin-top: 22px;
  border-top: 1px solid var(--el-border-color-lighter);
  padding-top: 14px;
}

.availability-dialog__history h3 {
  margin: 0 0 12px;
  font-size: 14px;
}

.availability-dialog__history p {
  margin: 4px 0 0;
  color: var(--el-text-color-secondary);
}
</style>
