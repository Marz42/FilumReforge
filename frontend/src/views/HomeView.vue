<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { getOverview } from '@/api/overview'
import { getReportCenterSnapshot } from '@/api/report-center'
import OverviewAnnouncementBoard from '@/components/overview/OverviewAnnouncementBoard.vue'
import OverviewMessageWidget from '@/components/overview/OverviewMessageWidget.vue'
import OverviewTodoWidget from '@/components/overview/OverviewTodoWidget.vue'
import type { OverviewSnapshot, ReportRecord } from '@/types/api'
import { getErrorMessage } from '@/utils/errors'

const loadingOverview = ref(false)
const loadingReports = ref(false)
const overview = ref<OverviewSnapshot | null>(null)
const pendingReports = ref<ReportRecord[]>([])

const todoLoading = computed(() => loadingOverview.value || loadingReports.value)

async function loadOverviewSnapshot(): Promise<void> {
  loadingOverview.value = true
  try {
    overview.value = await getOverview()
  } catch (error) {
    ElMessage.error(`总览数据加载失败：${getErrorMessage(error)}`)
  } finally {
    loadingOverview.value = false
  }
}

async function loadPendingReports(): Promise<void> {
  loadingReports.value = true
  try {
    const reportSnapshot = await getReportCenterSnapshot()
    pendingReports.value = reportSnapshot.pending_reports
  } catch (error) {
    ElMessage.error(`待审汇报加载失败：${getErrorMessage(error)}`)
  } finally {
    loadingReports.value = false
  }
}

async function loadOverview(): Promise<void> {
  await Promise.all([loadOverviewSnapshot(), loadPendingReports()])
}

onMounted(() => {
  void loadOverview()
})
</script>

<template>
  <div class="overview filum-page">
    <div class="overview__grid">
      <OverviewTodoWidget
        class="overview__grid-item overview__grid-item--todos"
        :inbox-tasks="overview?.task_inbox ?? []"
        :pending-reports="pendingReports"
        :loading="todoLoading"
      />
      <OverviewAnnouncementBoard
        class="overview__grid-item overview__grid-item--announcement"
        :overview="overview"
        :loading="loadingOverview"
        @refresh="loadOverviewSnapshot"
      />
      <OverviewMessageWidget class="overview__grid-item overview__grid-item--messages" />
    </div>
  </div>
</template>

<style scoped>
.overview__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
}

.overview__grid-item--todos {
  grid-column: 1;
  grid-row: 1;
}

.overview__grid-item--announcement {
  grid-column: 2;
  grid-row: 1 / span 2;
}

.overview__grid-item--messages {
  grid-column: 1;
  grid-row: 2;
}

@media (max-width: 960px) {
  .overview__grid {
    grid-template-columns: 1fr;
  }

  .overview__grid-item--todos,
  .overview__grid-item--announcement,
  .overview__grid-item--messages {
    grid-column: 1;
    grid-row: auto;
  }
}
</style>
