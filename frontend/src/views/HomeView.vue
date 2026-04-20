<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { listDocuments } from '@/api/documents'
import { listDepartments } from '@/api/departments'
import { listMessages } from '@/api/messages'
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
const documentCount = ref(0)
const messageCount = ref(0)
const latestTaskTitles = ref<string[]>([])

const architectureHighlights = [
  '模型先行 + 服务层封装 + API 暴露 + 前端对接',
  'JWT access / refresh 会话链路',
  'Redis 异步通知总线',
  '统一附件对象存储抽象',
  '知识库 + RAG 检索基座',
  'AI Router 与浏览器推送 / PWA',
]

const summaryCards = computed(() => {
  const cards = [
    {
      label: '知识文档',
      value: documentCount.value,
      description: '制度、SOP、公告与 FAQ',
    },
    {
      label: '消息数量',
      value: messageCount.value,
      description: '消息中心与回执链路',
    },
    {
      label: '任务数量',
      value: taskCount.value,
      description: '创建、指派与通知联动',
    },
  ]

  if (authStore.isManagementRole) {
    cards.unshift(
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
    )
  }

  return cards
})

async function loadDashboard(): Promise<void> {
  loading.value = true

  try {
    const [tasks, documents, messages] = await Promise.all([
      listTasks(),
      listDocuments(),
      listMessages(),
    ])

    taskCount.value = tasks.length
    documentCount.value = documents.length
    messageCount.value = messages.length
    latestTaskTitles.value = tasks.slice(0, 5).map((task) => task.title)

    if (authStore.isManagementRole) {
      const [departments, profiles] = await Promise.all([listDepartments(), listProfiles()])
      departmentCount.value = departments.length
      profileCount.value = profiles.length
    }
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
              用户、部门、档案、任务、模板、审批、消息、知识库、AI Router 与浏览器推送
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
