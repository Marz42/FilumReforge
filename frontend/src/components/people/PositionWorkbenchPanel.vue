<script setup lang="ts">
import { onMounted, ref } from 'vue'

import {
  getPositionWorkbenchCatalog,
  getPositionWorkbenchDetail,
  type PositionWorkbenchCatalog,
  type PositionWorkbenchDetail,
} from '@/api/position-workbench'
import { showError } from '@/utils/errors'
import { formatDate } from '@/utils/formatters'

const loading = ref(false)
const detailLoading = ref(false)
const catalog = ref<PositionWorkbenchCatalog | null>(null)
const detail = ref<PositionWorkbenchDetail | null>(null)
const selectedPositionId = ref('')

async function loadCatalog(): Promise<void> {
  loading.value = true
  try {
    catalog.value = await getPositionWorkbenchCatalog()
  } catch (error) {
    showError(error)
  } finally {
    loading.value = false
  }
}

async function selectPosition(positionId: string): Promise<void> {
  selectedPositionId.value = positionId
  detailLoading.value = true
  try {
    detail.value = await getPositionWorkbenchDetail(positionId)
  } catch (error) {
    showError(error)
  } finally {
    detailLoading.value = false
  }
}

onMounted(() => {
  void loadCatalog()
})

defineExpose({ reload: loadCatalog })
</script>

<template>
  <div class="position-workbench" v-loading="loading">
    <div v-if="catalog" class="position-workbench__summary">
      <span>岗位 {{ catalog.summary.total_positions }}</span>
      <span>启用 {{ catalog.summary.active_positions }}</span>
      <span>在职人数 {{ catalog.summary.total_assignees }}</span>
      <span>基准日 {{ catalog.as_of }}</span>
    </div>

    <el-table
      :data="catalog?.positions ?? []"
      stripe
      highlight-current-row
      @row-click="(row) => selectPosition(row.id)"
    >
      <el-table-column prop="name" label="岗位" min-width="160" />
      <el-table-column prop="code" label="编码" min-width="120" />
      <el-table-column label="任职" min-width="80">
        <template #default="{ row }">{{ row.impact.assignee_count }}</template>
      </el-table-column>
      <el-table-column label="主任职" min-width="80">
        <template #default="{ row }">{{ row.impact.primary_count }}</template>
      </el-table-column>
      <el-table-column label="兼岗" min-width="80">
        <template #default="{ row }">{{ row.impact.secondary_count }}</template>
      </el-table-column>
      <el-table-column label="部门数" min-width="80">
        <template #default="{ row }">{{ row.impact.department_count }}</template>
      </el-table-column>
      <el-table-column label="活跃汇报" min-width="90">
        <template #default="{ row }">{{ row.impact.active_reporting_line_count }}</template>
      </el-table-column>
    </el-table>

    <div v-if="selectedPositionId" class="position-workbench__detail" v-loading="detailLoading">
      <template v-if="detail">
        <h4>{{ detail.position.name }} 影响预览</h4>
        <p>
          生效区间：
          {{ formatDate(detail.effective_range.earliest_starts_at) }}
          —
          {{
            detail.effective_range.latest_ends_at
              ? formatDate(detail.effective_range.latest_ends_at)
              : '开放'
          }}
          （开放任职 {{ detail.effective_range.open_ended_assignment_count }}）
        </p>
        <el-table :data="detail.assignments" stripe>
          <el-table-column label="人员" min-width="180">
            <template #default="{ row }">
              {{ row.user.real_name ?? row.user.email }}
            </template>
          </el-table-column>
          <el-table-column prop="department_name" label="部门" min-width="120" />
          <el-table-column prop="assignment_type" label="类型" min-width="100" />
          <el-table-column label="主任职" min-width="80">
            <template #default="{ row }">{{ row.is_primary ? '是' : '否' }}</template>
          </el-table-column>
          <el-table-column label="生效" min-width="80">
            <template #default="{ row }">{{ row.is_effective ? '是' : '否' }}</template>
          </el-table-column>
        </el-table>
        <el-table :data="detail.reporting_lines" stripe class="position-workbench__reporting">
          <el-table-column label="成员" min-width="160">
            <template #default="{ row }">
              {{ row.user.real_name ?? row.user.email }}
            </template>
          </el-table-column>
          <el-table-column prop="manager_label" label="上级" min-width="180" />
          <el-table-column prop="line_type" label="线型" min-width="100" />
          <el-table-column label="生效" min-width="80">
            <template #default="{ row }">{{ row.is_effective ? '是' : '否' }}</template>
          </el-table-column>
        </el-table>
      </template>
      <el-empty v-else description="选择岗位查看影响人员与汇报链" />
    </div>
  </div>
</template>

<style scoped>
.position-workbench {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.position-workbench__summary {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  color: var(--filum-text-secondary);
  font-size: 13px;
}

.position-workbench__detail {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.position-workbench__reporting {
  margin-top: 8px;
}
</style>
