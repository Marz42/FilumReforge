<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { listDepartments } from '@/api/departments'
import { listProfiles } from '@/api/profiles'
import { listTasks } from '@/api/tasks'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'
import { formatDateTime } from '@/utils/formatters'
import { getErrorMessage } from '@/utils/errors'

const appStore = useAppStore()
const authStore = useAuthStore()
const loading = ref(false)
const departmentCount = ref(0)
const profileCount = ref(0)
const taskCount = ref(0)
const latestTaskTitles = ref<string[]>([])

const architectureHighlights = [
  '模型先行 + 服务层封装 + API 暴露 + 前端对接',
  'JWT access / refresh 会话链路',
  'Redis 异步通知总线',
  '统一附件对象存储抽象',
  '任务模板 / 审批流 / 消息中心',
]

const summaryCards = computed(() => [
  {
    label: '部门数量',
    value: departmentCount.value,
    description: '组织树与负责人绑定',
  },
  {
    label: '员工档案',
    value: profileCount.value,
    description: 'HR 档案与 JSON 动态字段',
  },
  {
    label: '任务数量',
    value: taskCount.value,
    description: '创建、指派与通知联动',
  },
])

async function loadDashboard(): Promise<void> {
  loading.value = true

  try {
    const [departments, profiles, tasks] = await Promise.all([
      listDepartments(),
      listProfiles(),
      listTasks(),
    ])

    departmentCount.value = departments.length
    profileCount.value = profiles.length
    taskCount.value = tasks.length
    latestTaskTitles.value = tasks.slice(0, 5).map((task) => task.title)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void loadDashboard()
})
</script>

<template>
  <div class="dashboard">
    <el-row :gutter="20" class="dashboard__summary">
      <el-col
        v-for="item in summaryCards"
        :key="item.label"
        :xs="24"
        :md="8"
      >
        <el-card shadow="never">
          <div class="summary-card">
            <span class="summary-card__label">{{ item.label }}</span>
            <strong class="summary-card__value">{{ item.value }}</strong>
            <span class="summary-card__description">{{ item.description }}</span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20">
      <el-col :xs="24" :lg="16">
        <el-card shadow="never" v-loading="loading">
          <template #header>
            <span>{{ appStore.headerTitle }}</span>
          </template>

          <el-descriptions :column="1" border>
            <el-descriptions-item label="当前状态">
              {{ appStore.deliveryStatus }}
            </el-descriptions-item>
            <el-descriptions-item label="当前用户">
              {{ authStore.user?.email ?? '未登录' }}
            </el-descriptions-item>
            <el-descriptions-item label="上次登录">
              {{ formatDateTime(authStore.user?.last_login_at ?? null) }}
            </el-descriptions-item>
            <el-descriptions-item label="Foundation 范围">
              用户、部门、档案、任务、模板、审批、消息与通知总线
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="8">
        <el-card shadow="never" class="dashboard__section">
          <template #header>
            <span>架构重点</span>
          </template>

          <el-space wrap>
            <el-tag
              v-for="item in architectureHighlights"
              :key="item"
              type="info"
              effect="plain"
            >
              {{ item }}
            </el-tag>
          </el-space>
        </el-card>

        <el-card shadow="never" class="dashboard__section">
          <template #header>
            <span>最新任务与工作流</span>
          </template>

          <el-empty v-if="latestTaskTitles.length === 0" description="暂无任务" />

          <el-timeline v-else>
            <el-timeline-item
              v-for="item in latestTaskTitles"
              :key="item"
              type="primary"
              hollow
            >
              {{ item }}
            </el-timeline-item>
          </el-timeline>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.dashboard__summary {
  margin-bottom: 20px;
}

.summary-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.summary-card__label {
  color: #909399;
}

.summary-card__value {
  font-size: 32px;
  color: #303133;
}

.summary-card__description {
  color: #606266;
}

.dashboard__section {
  margin-top: 20px;
}
</style>
