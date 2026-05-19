<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'

import {
  archiveBoardCard,
  createAnnouncement,
  createBoardCard,
  withdrawAnnouncement,
} from '@/api/overview'
import { useAuthStore } from '@/stores/auth'
import type { OverviewSnapshot } from '@/types/api'
import { formatDate, formatDateTime } from '@/utils/formatters'
import { getErrorMessage } from '@/utils/errors'

const props = defineProps<{
  overview: OverviewSnapshot | null
  loading?: boolean
}>()

const emit = defineEmits<{
  refresh: []
}>()

const route = useRoute()
const authStore = useAuthStore()
const activePane = ref<'announcement' | 'board'>('announcement')
const boardDialogVisible = ref(false)
const announcementDialogVisible = ref(false)
const boardSubmitting = ref(false)
const announcementSubmitting = ref(false)

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

const permissions = computed(() => props.overview?.permissions ?? null)
const boardScopeOptions = computed(() => permissions.value?.board_scope_options ?? [])
const announcementScopeOptions = computed(() => permissions.value?.announcement_scope_options ?? [])
const canPublishBoard = computed(() => permissions.value?.can_publish_board ?? false)
const canPublishAnnouncement = computed(() => permissions.value?.can_publish_announcement ?? false)
const canArchiveOverviewItems = computed(() => authStore.user?.role === 'admin')
const highlightedAnnouncementId = computed(() =>
  typeof route.query.announcement === 'string' ? route.query.announcement : '',
)

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
    emit('refresh')
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
    emit('refresh')
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
    emit('refresh')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  }
}

async function handleWithdrawAnnouncement(announcementId: string): Promise<void> {
  try {
    await withdrawAnnouncement(announcementId)
    ElMessage.success('公告已归档')
    emit('refresh')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  }
}
</script>

<template>
  <el-card
    shadow="never"
    class="overview-widget overview-announcement-board filum-panel-card"
    data-testid="overview-widget-announcement-board"
    v-loading="loading"
  >
    <template #header>
      <div class="overview-announcement-board__header">
        <div class="overview-widget__heading">
          <span>公告 / 白板</span>
          <small>组织通知与共享提醒</small>
        </div>
        <div class="overview-announcement-board__actions">
          <el-radio-group v-model="activePane" size="small">
            <el-radio-button value="announcement">公告</el-radio-button>
            <el-radio-button value="board">白板</el-radio-button>
          </el-radio-group>
          <el-button
            v-if="activePane === 'board' && canPublishBoard"
            type="primary"
            size="small"
            data-testid="create-board-card-button"
            @click="openBoardDialog"
          >
            发布看板卡片
          </el-button>
          <el-button
            v-if="activePane === 'announcement' && canPublishAnnouncement"
            type="primary"
            size="small"
            data-testid="create-announcement-button"
            @click="openAnnouncementDialog"
          >
            发布公告
          </el-button>
        </div>
      </div>
    </template>

    <template v-if="activePane === 'announcement'">
      <el-empty
        v-if="!overview || overview.announcements.length === 0"
        class="overview-widget__empty"
        description="当前暂无进行中公告"
      />

      <div v-else class="overview-widget__list">
        <article
          v-for="announcement in overview.announcements"
          :key="announcement.id"
          class="overview-widget__article"
          :class="{ 'overview-widget__article--highlighted': announcement.id === highlightedAnnouncementId }"
        >
          <div class="overview-widget__item-meta">
            <strong>{{ announcement.publisher_department_name }}</strong>
            <div class="overview-widget__inline-actions">
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
          <h3 class="overview-widget__title">{{ announcement.title }}</h3>
          <p class="overview-widget__body">{{ announcement.content_md }}</p>
          <span class="overview-widget__footnote">发布人：{{ announcement.author_name }}</span>
        </article>
      </div>
    </template>

    <template v-else>
      <el-empty
        v-if="!overview || overview.board_cards.length === 0"
        class="overview-widget__empty"
        description="当前范围暂无有效看板"
      />

      <div v-else class="overview-widget__list">
        <article v-for="card in overview.board_cards" :key="card.id" class="overview-widget__article">
          <div class="overview-widget__item-meta">
            <el-tag effect="plain">{{ card.scope_label }}</el-tag>
            <div class="overview-widget__inline-actions">
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
          <h3 class="overview-widget__title">{{ card.title }}</h3>
          <p class="overview-widget__body">{{ card.content_md }}</p>
          <span class="overview-widget__footnote">到期：{{ formatDate(card.expires_at) }}</span>
        </article>
      </div>
    </template>

    <el-dialog v-model="boardDialogVisible" title="发布看板卡片" width="520px" destroy-on-close>
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

    <el-dialog v-model="announcementDialogVisible" title="发布公告" width="520px" destroy-on-close>
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
          <el-input v-model="announcementForm.title" data-testid="announcement-title-input" maxlength="120" />
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
  </el-card>
</template>

<style scoped>
.overview-announcement-board__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.overview-announcement-board__actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.overview-widget__heading {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.overview-widget__heading small {
  color: var(--filum-text-secondary);
  font-size: 12px;
}

.overview-widget__empty {
  padding: 4px 0;
}

.overview-widget__list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.overview-widget__article {
  border: 1px solid var(--filum-border-strong);
  border-radius: 12px;
  padding: 16px;
  background: linear-gradient(180deg, #ffffff 0%, #f8faff 100%);
}

.overview-widget__article--highlighted {
  border-color: var(--el-color-primary);
}

.overview-widget__item-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: var(--filum-text-secondary);
  font-size: 13px;
}

.overview-widget__inline-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.overview-widget__title {
  margin: 12px 0 8px;
  font-size: 16px;
  color: var(--filum-text);
}

.overview-widget__body {
  margin: 0;
  color: var(--filum-text-secondary);
  line-height: 1.6;
  white-space: pre-wrap;
}

.overview-widget__footnote {
  display: inline-block;
  margin-top: 12px;
  color: var(--filum-text-muted);
  font-size: 13px;
}
</style>
