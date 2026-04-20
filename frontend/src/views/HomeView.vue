<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { createAnnouncement, createBoardCard, getOverview } from '@/api/overview'
import { useAuthStore } from '@/stores/auth'
import type { OverviewSnapshot, TaskPriority } from '@/types/api'
import { formatDate, formatDateTime } from '@/utils/formatters'
import { getErrorMessage } from '@/utils/errors'

const authStore = useAuthStore()
const loading = ref(false)
const boardDialogVisible = ref(false)
const announcementDialogVisible = ref(false)
const boardSubmitting = ref(false)
const announcementSubmitting = ref(false)
const overview = ref<OverviewSnapshot | null>(null)

const boardForm = reactive({
  scope_department_id: 'company',
  title: '',
  content_md: '',
})

const announcementForm = reactive({
  publisher_department_id: '',
  title: '',
  content_md: '',
})

const summaryCards = computed(() => {
  const snapshot = overview.value
  if (!snapshot) {
    return []
  }

  return [
    {
      label: '有效看板',
      value: snapshot.board_cards.length,
      description: '组织树范围内的共享信息卡片',
    },
    {
      label: '进行中公告',
      value: snapshot.announcements.length,
      description: '全员可见的重要通知',
    },
    {
      label: '待办事项',
      value: snapshot.task_inbox.length,
      description: '当前流转到你的任务',
    },
    {
      label: '任务跟踪',
      value: snapshot.task_tracking.length,
      description: '与你相关的任务进度',
    },
  ]
})

const permissions = computed(() => overview.value?.permissions ?? null)
const boardScopeOptions = computed(() => permissions.value?.board_scope_options ?? [])
const announcementScopeOptions = computed(() => permissions.value?.announcement_scope_options ?? [])
const canPublishBoard = computed(() => permissions.value?.can_publish_board ?? false)
const canPublishAnnouncement = computed(() => permissions.value?.can_publish_announcement ?? false)

function priorityTagType(priority: TaskPriority): 'danger' | 'warning' | 'info' | 'success' {
  switch (priority) {
    case 'urgent':
      return 'danger'
    case 'high':
      return 'warning'
    case 'medium':
      return 'info'
    case 'low':
      return 'success'
  }
}

function priorityLabel(priority: TaskPriority): string {
  const labels: Record<TaskPriority, string> = {
    urgent: '紧急',
    high: '高',
    medium: '中',
    low: '低',
  }
  return labels[priority]
}

function resetBoardForm(): void {
  boardForm.scope_department_id = boardScopeOptions.value[0]?.id ?? 'company'
  boardForm.title = ''
  boardForm.content_md = ''
}

function resetAnnouncementForm(): void {
  announcementForm.publisher_department_id = announcementScopeOptions.value[0]?.id ?? ''
  announcementForm.title = ''
  announcementForm.content_md = ''
}

function openBoardDialog(): void {
  resetBoardForm()
  boardDialogVisible.value = true
}

function openAnnouncementDialog(): void {
  resetAnnouncementForm()
  announcementDialogVisible.value = true
}

async function loadOverview(): Promise<void> {
  loading.value = true

  try {
    overview.value = await getOverview()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

async function submitBoardCard(): Promise<void> {
  boardSubmitting.value = true
  try {
    await createBoardCard({
      scope_department_id: boardForm.scope_department_id === 'company' ? null : boardForm.scope_department_id,
      title: boardForm.title,
      content_md: boardForm.content_md,
    })
    ElMessage.success('看板卡片已发布')
    boardDialogVisible.value = false
    resetBoardForm()
    await loadOverview()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    boardSubmitting.value = false
  }
}

async function submitAnnouncement(): Promise<void> {
  announcementSubmitting.value = true
  try {
    await createAnnouncement({
      publisher_department_id: announcementForm.publisher_department_id,
      title: announcementForm.title,
      content_md: announcementForm.content_md,
    })
    ElMessage.success('公告已发布')
    announcementDialogVisible.value = false
    resetAnnouncementForm()
    await loadOverview()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    announcementSubmitting.value = false
  }
}

onMounted(() => {
  void loadOverview()
})
</script>

<template>
  <div class="overview">
    <el-row :gutter="20" class="overview__summary">
      <el-col
        v-for="item in summaryCards"
        :key="item.label"
        :xs="24"
        :sm="12"
        :lg="6"
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
            <div class="overview__card-header">
              <span>看板</span>
              <el-button
                v-if="canPublishBoard"
                type="primary"
                size="small"
                data-testid="create-board-card-button"
                @click="openBoardDialog"
              >
                发布看板卡片
              </el-button>
            </div>
          </template>

          <el-empty
            v-if="!overview || overview.board_cards.length === 0"
            description="当前范围暂无有效看板"
          />

          <div v-else class="overview__list">
            <el-card
              v-for="card in overview.board_cards"
              :key="card.id"
              shadow="hover"
              class="overview__item-card"
            >
              <div class="overview__item-meta">
                <el-tag effect="plain">{{ card.scope_label }}</el-tag>
                <span>{{ card.author_name }}</span>
              </div>
              <h3 class="overview__item-title">{{ card.title }}</h3>
              <p class="overview__item-content">{{ card.content_md }}</p>
              <span class="overview__item-footnote">到期：{{ formatDate(card.expires_at) }}</span>
            </el-card>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="8">
        <el-card shadow="never" class="overview__section" v-loading="loading">
          <template #header>
            <div class="overview__card-header">
              <span>公告</span>
              <el-button
                v-if="canPublishAnnouncement"
                type="primary"
                size="small"
                data-testid="create-announcement-button"
                @click="openAnnouncementDialog"
              >
                发布公告
              </el-button>
            </div>
          </template>

          <el-empty
            v-if="!overview || overview.announcements.length === 0"
            description="当前暂无进行中公告"
          />

          <div v-else class="overview__compact-list">
            <article
              v-for="announcement in overview.announcements"
              :key="announcement.id"
              class="overview__compact-item"
            >
              <div class="overview__item-meta">
                <strong>{{ announcement.publisher_department_name }}</strong>
                <span>{{ formatDateTime(announcement.published_at) }}</span>
              </div>
              <h3 class="overview__item-title">{{ announcement.title }}</h3>
              <p class="overview__item-content">{{ announcement.content_md }}</p>
              <span class="overview__item-footnote">发布人：{{ announcement.author_name }}</span>
            </article>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="overview__section-grid">
      <el-col :xs="24" :lg="12">
        <el-card shadow="never" v-loading="loading">
          <template #header>
            <span>待办事项</span>
          </template>

          <el-empty
            v-if="!overview || overview.task_inbox.length === 0"
            description="当前没有流转到你的任务"
          />

          <div v-else class="overview__compact-list">
            <article
              v-for="item in overview.task_inbox"
              :key="item.task_id"
              class="overview__compact-item"
            >
              <div class="overview__item-meta">
                <strong>{{ item.title }}</strong>
                <el-tag :type="priorityTagType(item.priority)" effect="plain">
                  {{ priorityLabel(item.priority) }}
                </el-tag>
              </div>
              <p class="overview__item-content">
                {{ item.current_stage_label }}
                <span v-if="item.current_handler_label"> · 当前处理：{{ item.current_handler_label }}</span>
              </p>
              <span class="overview__item-footnote">
                {{ item.department_name ?? '未分配部门' }} · 到期：{{ formatDateTime(item.due_date) }}
              </span>
            </article>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="12">
        <el-card shadow="never" v-loading="loading">
          <template #header>
            <span>任务跟踪</span>
          </template>

          <el-empty
            v-if="!overview || overview.task_tracking.length === 0"
            description="当前没有需要跟踪的任务"
          />

          <div v-else class="overview__compact-list">
            <article
              v-for="item in overview.task_tracking"
              :key="item.task_id"
              class="overview__compact-item"
            >
              <div class="overview__item-meta">
                <strong>{{ item.title }}</strong>
                <span>{{ item.relation_types.join(' / ') }}</span>
              </div>
              <p class="overview__item-content">
                {{ item.current_stage_label }}
                <span v-if="item.current_handler_label"> · 当前处理：{{ item.current_handler_label }}</span>
              </p>
              <span class="overview__item-footnote">
                {{ item.department_name ?? '未分配部门' }} · 到期：{{ formatDateTime(item.due_date) }}
              </span>
            </article>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="overview__section-grid">
      <el-col :xs="24">
        <el-card shadow="never">
          <template #header>
            <span>快捷入口</span>
          </template>

          <el-space wrap>
            <el-link href="/task-center" type="primary">进入任务中心</el-link>
            <el-link href="/messages" type="primary">进入消息中心</el-link>
            <el-link href="/knowledge-base" type="primary">进入知识库</el-link>
            <el-link v-if="authStore.isManagementRole" href="/people" type="primary">进入人员管理</el-link>
          </el-space>
        </el-card>
      </el-col>
    </el-row>

    <el-dialog
      v-model="boardDialogVisible"
      title="发布看板卡片"
      width="520px"
      destroy-on-close
    >
      <el-form label-position="top">
        <el-form-item label="发布范围">
          <el-select v-model="boardForm.scope_department_id" style="width: 100%">
            <el-option
              v-for="option in boardScopeOptions"
              :key="option.id"
              :label="option.label"
              :value="option.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="主题">
          <el-input v-model="boardForm.title" data-testid="board-card-title-input" maxlength="80" />
        </el-form-item>
        <el-form-item label="内容">
          <el-input
            v-model="boardForm.content_md"
            type="textarea"
            :rows="4"
            data-testid="board-card-content-input"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="boardDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="boardSubmitting"
          data-testid="submit-board-card-button"
          @click="submitBoardCard"
        >
          发布
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="announcementDialogVisible"
      title="发布公告"
      width="520px"
      destroy-on-close
    >
      <el-form label-position="top">
        <el-form-item label="发布部门">
          <el-select v-model="announcementForm.publisher_department_id" style="width: 100%">
            <el-option
              v-for="option in announcementScopeOptions"
              :key="option.id"
              :label="option.label"
              :value="option.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="标题">
          <el-input
            v-model="announcementForm.title"
            data-testid="announcement-title-input"
            maxlength="120"
          />
        </el-form-item>
        <el-form-item label="内容">
          <el-input
            v-model="announcementForm.content_md"
            type="textarea"
            :rows="4"
            data-testid="announcement-content-input"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="announcementDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="announcementSubmitting"
          data-testid="submit-announcement-button"
          @click="submitAnnouncement"
        >
          发布
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.overview__summary {
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

.overview__section,
.overview__section-grid {
  margin-top: 20px;
}

.overview__card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.overview__list {
  display: grid;
  gap: 12px;
}

.overview__compact-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.overview__item-card,
.overview__compact-item {
  border: 1px solid var(--el-border-color-light);
  border-radius: 12px;
  padding: 16px;
}

.overview__item-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: #606266;
  font-size: 13px;
}

.overview__item-title {
  margin: 12px 0 8px;
  font-size: 16px;
  color: #303133;
}

.overview__item-content {
  margin: 0;
  color: #606266;
  line-height: 1.6;
  white-space: pre-wrap;
}

.overview__item-footnote {
  display: inline-block;
  margin-top: 12px;
  color: #909399;
  font-size: 13px;
}
</style>
