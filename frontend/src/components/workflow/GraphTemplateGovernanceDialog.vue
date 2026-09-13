<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { auditGraphTemplateGovernance } from '@/api/workflow-graph'
import type {
  GraphTemplateGovernanceAudit,
  GraphTemplateGovernanceIssue,
} from '@/types/workflowVideo'
import { showError } from '@/utils/errors'

const visible = defineModel<boolean>({ required: true })

const emit = defineEmits<{
  repair: [issue: GraphTemplateGovernanceIssue]
}>()

const loading = ref(false)
const report = ref<GraphTemplateGovernanceAudit | null>(null)

const summaryType = computed((): 'error' | 'warning' | 'success' => {
  if ((report.value?.error_count ?? 0) > 0) return 'error'
  if ((report.value?.warning_count ?? 0) > 0 || (report.value?.review_count ?? 0) > 0) {
    return 'warning'
  }
  return 'success'
})

function severityLabel(severity: GraphTemplateGovernanceIssue['severity']): string {
  if (severity === 'error') return '需修复'
  if (severity === 'warning') return '需清理'
  return '需确认'
}

function severityType(severity: GraphTemplateGovernanceIssue['severity']): 'danger' | 'warning' | 'info' {
  if (severity === 'error') return 'danger'
  if (severity === 'warning') return 'warning'
  return 'info'
}

function categoryLabel(category: GraphTemplateGovernanceIssue['category']): string {
  return category === 'availability_scope' ? '可用范围' : '模板依赖'
}

function actionLabel(action: GraphTemplateGovernanceIssue['repair_action']): string {
  if (action === 'edit_draft') return '打开草稿'
  if (action === 'create_new_version') return '新建修正版'
  return '仅需确认'
}

async function loadReport(): Promise<void> {
  loading.value = true
  try {
    report.value = await auditGraphTemplateGovernance()
  } catch (error) {
    report.value = null
    showError(error)
  } finally {
    loading.value = false
  }
}

function handleRepair(issue: GraphTemplateGovernanceIssue): void {
  if (issue.repair_action === 'review_configuration') {
    return
  }
  emit('repair', issue)
}

watch(visible, (next) => {
  if (next) {
    void loadReport()
  }
}, { immediate: true })
</script>

<template>
  <el-dialog
    v-model="visible"
    title="模板数据检查"
    width="900px"
    data-testid="template-governance-dialog"
  >
    <div v-loading="loading" class="template-governance">
      <template v-if="report">
        <el-alert
          :type="summaryType"
          :closable="false"
          show-icon
          class="template-governance__summary"
        >
          <template #title>
            已检查 {{ report.template_count }} 个可管理模板：
            {{ report.error_count }} 项需修复，
            {{ report.warning_count }} 项需清理，
            {{ report.review_count }} 项需人工确认
          </template>
        </el-alert>

        <el-table
          v-if="report.issues.length"
          :data="report.issues"
          max-height="560"
          data-testid="template-governance-issues"
        >
          <el-table-column label="级别" width="82">
            <template #default="{ row }: { row: GraphTemplateGovernanceIssue }">
              <el-tag size="small" effect="plain" :type="severityType(row.severity)">
                {{ severityLabel(row.severity) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="模板" min-width="180">
            <template #default="{ row }: { row: GraphTemplateGovernanceIssue }">
              <strong>{{ row.template_name }}</strong>
              <div class="template-governance__muted">
                {{ row.template_code }} · {{ row.template_status }}
              </div>
            </template>
          </el-table-column>
          <el-table-column label="检查项" width="96">
            <template #default="{ row }: { row: GraphTemplateGovernanceIssue }">
              {{ categoryLabel(row.category) }}
            </template>
          </el-table-column>
          <el-table-column label="发现与建议" min-width="310">
            <template #default="{ row }: { row: GraphTemplateGovernanceIssue }">
              <div>{{ row.message }}</div>
              <div class="template-governance__recommendation">{{ row.recommendation }}</div>
              <div v-if="row.suggested_template_code" class="template-governance__muted">
                建议编码：{{ row.suggested_template_code }}
              </div>
            </template>
          </el-table-column>
          <el-table-column label="处理" width="112" fixed="right">
            <template #default="{ row }: { row: GraphTemplateGovernanceIssue }">
              <el-button
                v-if="row.repair_action !== 'review_configuration'"
                type="primary"
                link
                data-testid="template-governance-repair"
                @click="handleRepair(row)"
              >
                {{ actionLabel(row.repair_action) }}
              </el-button>
              <span v-else class="template-governance__muted">
                {{ actionLabel(row.repair_action) }}
              </span>
            </template>
          </el-table-column>
        </el-table>

        <el-empty v-else description="未发现范围或模板依赖问题" />
      </template>
    </div>

    <template #footer>
      <el-button @click="visible = false">关闭</el-button>
      <el-button :loading="loading" @click="loadReport">重新检查</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.template-governance {
  min-height: 180px;
}

.template-governance__summary {
  margin-bottom: 16px;
}

.template-governance__recommendation {
  margin-top: 6px;
  color: var(--el-text-color-secondary);
}

.template-governance__muted {
  margin-top: 3px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
</style>
