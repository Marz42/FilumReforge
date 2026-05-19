<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { getOverview } from '@/api/overview'
import { getReportCenterSnapshot } from '@/api/report-center'
import OverviewAnnouncementBoard from '@/components/overview/OverviewAnnouncementBoard.vue'
import OverviewMessageWidget from '@/components/overview/OverviewMessageWidget.vue'
import OverviewTodoWidget from '@/components/overview/OverviewTodoWidget.vue'
import { useAuthStore } from '@/stores/auth'
import type { OverviewSnapshot, ReportRecord } from '@/types/api'
import { getErrorMessage } from '@/utils/errors'

const router = useRouter()
const authStore = useAuthStore()
const loading = ref(false)
const overview = ref<OverviewSnapshot | null>(null)
const pendingReports = ref<ReportRecord[]>([])

const quickActions = computed(() => {
  const items = [
    { label: '任务中心', path: '/task-center' },
    { label: '汇报中心', path: '/reports' },
    { label: '消息中心', path: '/messages' },
    { label: '知识库', path: '/knowledge-base' },
  ]

  if (authStore.isManagementRole) {
    items.push({ label: '人员管理', path: '/people' })
  }

  return items
})

function navigateToPath(path: string): void {
  void router.push(path)
}

async function loadOverview(): Promise<void> {
  loading.value = true
  try {
    const [overviewSnapshot, reportSnapshot] = await Promise.all([
      getOverview(),
      getReportCenterSnapshot(),
    ])
    overview.value = overviewSnapshot
    pendingReports.value = reportSnapshot.pending_reports
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void loadOverview()
})
</script>

<template>
  <div class="overview filum-page">
    <div class="overview__grid">
      <OverviewMessageWidget class="overview__grid-item overview__grid-item--messages" />
      <OverviewAnnouncementBoard
        class="overview__grid-item overview__grid-item--announcement"
        :overview="overview"
        :loading="loading"
        @refresh="loadOverview"
      />
      <OverviewTodoWidget
        class="overview__grid-item overview__grid-item--todos"
        :inbox-tasks="overview?.task_inbox ?? []"
        :pending-reports="pendingReports"
        :loading="loading"
      />
    </div>

    <el-card shadow="never" class="overview__quick-links filum-panel-card">
      <template #header>
        <span>快捷入口</span>
      </template>
      <div class="overview__quick-links-row">
        <button
          v-for="item in quickActions"
          :key="item.path"
          type="button"
          class="overview__quick-link"
          @click="navigateToPath(item.path)"
        >
          {{ item.label }}
        </button>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.overview__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
}

.overview__grid-item--messages {
  grid-column: 1;
  grid-row: 1;
}

.overview__grid-item--announcement {
  grid-column: 2;
  grid-row: 1 / span 2;
}

.overview__grid-item--todos {
  grid-column: 1;
  grid-row: 2;
}

.overview__quick-links {
  margin-top: 20px;
}

.overview__quick-links-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.overview__quick-link {
  padding: 8px 14px;
  border: 1px solid var(--filum-border-strong);
  border-radius: 999px;
  background: var(--filum-surface);
  color: var(--el-color-primary);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease;
}

.overview__quick-link:hover {
  border-color: var(--el-color-primary-light-5);
  box-shadow: 0 6px 16px rgba(91, 110, 245, 0.1);
}

@media (max-width: 1080px) {
  .overview__grid {
    grid-template-columns: 1fr;
  }

  .overview__grid-item--announcement,
  .overview__grid-item--messages,
  .overview__grid-item--todos {
    grid-column: auto;
    grid-row: auto;
  }
}
</style>
