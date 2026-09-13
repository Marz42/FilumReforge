<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { getIteration4UatPreflight } from '@/api/workflow-graph'
import type {
  Iteration4UatCheck,
  Iteration4UatPreflight,
  Iteration4UatTemplateCandidate,
} from '@/types/workflowVideo'
import { showError } from '@/utils/errors'

const visible = defineModel<boolean>({ required: true })

const emit = defineEmits<{
  openTemplate: [templateId: string]
}>()

const loading = ref(false)
const report = ref<Iteration4UatPreflight | null>(null)

const summaryType = computed((): 'error' | 'warning' | 'success' => {
  if ((report.value?.blocking_count ?? 0) > 0) return 'error'
  if ((report.value?.warning_count ?? 0) > 0) return 'warning'
  return 'success'
})

function checkStatusLabel(status: Iteration4UatCheck['status']): string {
  if (status === 'pass') return '已准备'
  if (status === 'warning') return '建议补充'
  if (status === 'blocked') return '暂不可测'
  return '人工验收'
}

function checkStatusType(
  status: Iteration4UatCheck['status'],
): 'success' | 'warning' | 'danger' | 'info' {
  if (status === 'pass') return 'success'
  if (status === 'warning') return 'warning'
  if (status === 'blocked') return 'danger'
  return 'info'
}

function candidateKindLabel(kind: Iteration4UatTemplateCandidate['kind']): string {
  if (kind === 'domain_neutral') return '通用黄金路径'
  if (kind === 'video_batch') return '视频批次兼容'
  if (kind === 'video_child') return '视频子流程兼容'
  return '设计器草稿'
}

async function loadReport(): Promise<void> {
  loading.value = true
  try {
    report.value = await getIteration4UatPreflight()
  } catch (error) {
    report.value = null
    showError(error)
  } finally {
    loading.value = false
  }
}

function openTemplate(templateId: string): void {
  visible.value = false
  emit('openTemplate', templateId)
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
    title="Iteration 4 验收准备"
    width="940px"
    data-testid="iteration4-uat-preflight-dialog"
  >
    <div v-loading="loading" class="uat-preflight">
      <template v-if="report">
        <el-alert
          :type="summaryType"
          :closable="false"
          show-icon
          class="uat-preflight__summary"
        >
          <template #title>
            <span v-if="report.preflight_ready">环境已具备人工验收前置条件</span>
            <span v-else>仍有 {{ report.blocking_count }} 项前置条件未满足</span>
            <span v-if="report.warning_count">，另有 {{ report.warning_count }} 项建议补充</span>
          </template>
          本检查只确认环境和样本是否可测，不代表业务验收已经通过。
        </el-alert>

        <el-table :data="report.checks" data-testid="iteration4-uat-preflight-checks">
          <el-table-column prop="check_id" label="编号" width="72" />
          <el-table-column label="状态" width="104">
            <template #default="{ row }: { row: Iteration4UatCheck }">
              <el-tag size="small" effect="plain" :type="checkStatusType(row.status)">
                {{ checkStatusLabel(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="title" label="检查项" min-width="150" />
          <el-table-column label="结果与下一步" min-width="360">
            <template #default="{ row }: { row: Iteration4UatCheck }">
              <div>{{ row.detail }}</div>
              <div v-if="row.action" class="uat-preflight__muted">{{ row.action }}</div>
            </template>
          </el-table-column>
        </el-table>

        <div class="uat-preflight__grid">
          <el-card shadow="never">
            <template #header><strong>模板候选</strong></template>
            <el-empty v-if="!report.template_candidates.length" description="暂无候选模板" />
            <div
              v-for="candidate in report.template_candidates"
              :key="candidate.kind"
              class="uat-preflight__candidate"
            >
              <div>
                <el-tag size="small" effect="plain">{{ candidateKindLabel(candidate.kind) }}</el-tag>
                <strong>{{ candidate.name }}</strong>
                <div class="uat-preflight__muted">{{ candidate.code }} · {{ candidate.status }}</div>
              </div>
              <el-button type="primary" link @click="openTemplate(candidate.template_id)">
                打开模板
              </el-button>
            </div>
          </el-card>

          <el-card shadow="never">
            <template #header><strong>账号与统计样本</strong></template>
            <p>
              协同候选部门：
              <strong>{{ report.department_candidates.length }}</strong>
            </p>
            <div
              v-for="department in report.department_candidates"
              :key="department.department_id"
              class="uat-preflight__department"
            >
              {{ department.department_name }} · {{ department.active_member_count }} 名活跃成员
            </div>
            <el-divider />
            <p class="uat-preflight__muted">
              统计样本周期：{{ report.stats_sample.start_date }} ～ {{ report.stats_sample.end_date }}
            </p>
            <div class="uat-preflight__stats">
              <span>新增 {{ report.stats_sample.created_count }}</span>
              <span>完成 {{ report.stats_sample.completed_count }}</span>
              <span>到期 {{ report.stats_sample.due_count }}</span>
              <span>未完成 {{ report.stats_sample.current_open_count }}</span>
            </div>
          </el-card>
        </div>
      </template>
    </div>

    <template #footer>
      <el-button @click="visible = false">关闭</el-button>
      <el-button :loading="loading" @click="loadReport">重新检查</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.uat-preflight {
  min-height: 220px;
}

.uat-preflight__summary {
  margin-bottom: 16px;
}

.uat-preflight__grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 16px;
  margin-top: 16px;
}

.uat-preflight__candidate {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.uat-preflight__candidate strong {
  margin-left: 8px;
}

.uat-preflight__department {
  margin: 6px 0;
}

.uat-preflight__stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.uat-preflight__muted {
  margin-top: 4px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

@media (max-width: 760px) {
  .uat-preflight__grid {
    grid-template-columns: 1fr;
  }
}
</style>
