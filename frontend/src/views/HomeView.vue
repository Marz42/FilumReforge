<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'

import {
  archiveBoardCard,
  createAnnouncement,
  createBoardCard,
  getOverview,
  withdrawAnnouncement,
} from '@/api/overview'
import { useAuthStore } from '@/stores/auth'
import type { OverviewSnapshot, TaskPriority } from '@/types/api'
import { formatDate, formatDateTime } from '@/utils/formatters'
import { getErrorMessage } from '@/utils/errors'

const route = useRoute()
const router = useRouter()
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
      label: '待办事项',
      value: snapshot.task_inbox.length,
      description: '当前流转到你的任务',
      actionLabel: '进入待办',
      tab: 'inbox' as const,
    },
    {
      label: '任务跟踪',
      value: snapshot.task_tracking.length,
      description: '与你相关的任务进度',
      actionLabel: '查看跟踪',
      tab: 'tracking' as const,
    },
  ]
})

const quickActions = computed(() => {
  const items = [
    {
      label: '任务中心',
      description: '查看待办、跟踪进度和个人备忘',
      path: '/task-center',
    },
    {
      label: '消息中心',
      description: '处理站内消息与业务通知',
      path: '/messages',
    },
    {
      label: '知识库',
      description: '浏览制度、文档与经验沉淀',
      path: '/knowledge-base',
    },
  ]

  if (authStore.isManagementRole) {
    items.push({
      label: '人员管理',
      description: '管理员工、岗位与组织信息',
      path: '/people',
    })
  }

  return items
})

const permissions = computed(() => overview.value?.permissions ?? null)
const boardScopeOptions = computed(() => permissions.value?.board_scope_options ?? [])
const announcementScopeOptions = computed(() => permissions.value?.announcement_scope_options ?? [])
const canPublishBoard = computed(() => permissions.value?.can_publish_board ?? false)
const canPublishAnnouncement = computed(() => permissions.value?.can_publish_announcement ?? false)
const canArchiveOverviewItems = computed(() => authStore.user?.role === 'admin')
const highlightedAnnouncementId = computed(() =>
  typeof route.query.announcement === 'string' ? route.query.announcement : '',
)

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

function navigateToTaskCenter(tab: 'inbox' | 'tracking'): void {
  void router.push({
    name: 'task-center',
    query: tab === 'inbox' ? {} : { tab },
  })
}

function navigateToPath(path: string): void {
  void router.push(path)
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

async function handleArchiveBoardCard(cardId: string): Promise<void> {
  try {
    await archiveBoardCard(cardId)
    ElMessage.success('看板卡片已归档')
    await loadOverview()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  }
}

async function handleWithdrawAnnouncement(announcementId: string): Promise<void> {
  try {
    await withdrawAnnouncement(announcementId)
    ElMessage.success('公告已归档')
    await loadOverview()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  }
}

onMounted(() => {
  void loadOverview()
})
</script>

<template>
  <div class="overview">
    <el-row :gutter="20">
      <el-col :xs="24" :lg="16">
        <el-card shadow="never" class="overview__content-card" v-loading="loading">
          <template #header>
            <div class="overview__card-header">
              <div class="overview__card-heading">
                <span>看板</span>
                <small>共享提醒与时效信息</small>
              </div>
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
                <div class="overview__item-actions">
                  <span>{{ card.author_name }}</span>
                  <el-button
                    v-if="canArchiveOverviewItems"
                    link
                    type="primary"
                    data-testid="archive-board-card-button"
                    @click="handleArchiveBoardCard(card.id)"
                  >
                    归档
                  </el-button>
                </div>
              </div>
              <h3 class="overview__item-title">{{ card.title }}</h3>
              <p class="overview__item-content">{{ card.content_md }}</p>
              <span class="overview__item-footnote">到期：{{ formatDate(card.expires_at) }}</span>
            </el-card>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="8">
        <el-card shadow="never" class="overview__content-card overview__section" v-loading="loading">
          <template #header>
            <div class="overview__card-header">
              <div class="overview__card-heading">
                <span>公告</span>
                <small>当前正在生效的正式通知</small>
              </div>
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
              :class="{ 'overview__compact-item--highlighted': announcement.id === highlightedAnnouncementId }"
            >
              <div class="overview__item-meta">
                <strong>{{ announcement.publisher_department_name }}</strong>
                <div class="overview__item-actions">
                  <span>{{ formatDateTime(announcement.published_at) }}</span>
                  <el-button
                    v-if="canArchiveOverviewItems"
                    link
                    type="primary"
                    data-testid="withdraw-announcement-button"
                    @click="handleWithdrawAnnouncement(announcement.id)"
                  >
                    归档
                  </el-button>
                </div>
              </div>
              <h3 class="overview__item-title">{{ announcement.title }}</h3>
              <p class="overview__item-content">{{ announcement.content_md }}</p>
              <span class="overview__item-footnote">发布人：{{ announcement.author_name }}</span>
            </article>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="overview__summary overview__section-grid">
      <el-col
        v-for="item in summaryCards"
        :key="item.label"
        :xs="24"
        :md="12"
      >
        <el-card shadow="never" class="summary-card summary-card--interactive">
          <div class="summary-card__content">
            <span class="summary-card__label">{{ item.label }}</span>
            <strong class="summary-card__value">{{ item.value }}</strong>
            <span class="summary-card__description">{{ item.description }}</span>
          </div>

          <el-button link type="primary" @click="navigateToTaskCenter(item.tab)">
            {{ item.actionLabel }}
          </el-button>
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
            <div class="overview__card-heading">
              <span>快捷入口</span>
              <small>按工作流快速跳转到常用模块</small>
            </div>
          </template>

          <div class="overview__quick-actions">
            <button
              v-for="item in quickActions"
              :key="item.path"
              type="button"
              class="overview__quick-action"
              @click="navigateToPath(item.path)"
            >
              <strong>{{ item.label }}</strong>
              <span>{{ item.description }}</span>
            </button>
          </div>
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
  height: 100%;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.summary-card--interactive {
  min-height: 180px;
}

.summary-card__content {
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

.overview__card-heading {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.overview__card-heading small {
  color: #909399;
  font-size: 12px;
}

.overview__content-card {
  height: 100%;
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

.overview__compact-item--highlighted {
  border-color: var(--el-color-primary);
}

.overview__item-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: #606266;
  font-size: 13px;
}

.overview__item-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
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

.overview__quick-actions {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
}

.overview__quick-action {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
  width: 100%;
  padding: 16px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 12px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  text-align: left;
  color: #303133;
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    transform 0.2s ease,
    box-shadow 0.2s ease;
}

.overview__quick-action strong {
  font-size: 15px;
}

.overview__quick-action span {
  color: #606266;
  line-height: 1.5;
}

.overview__quick-action:hover {
  border-color: var(--el-color-primary-light-5);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
  transform: translateY(-1px);
}
</style>
