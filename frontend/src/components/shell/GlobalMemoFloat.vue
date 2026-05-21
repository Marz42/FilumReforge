<script setup lang="ts">
import { onMounted } from 'vue'
import { EditPen } from '@element-plus/icons-vue'

import MemoCreateDialog from '@/components/shell/MemoCreateDialog.vue'
import {
  memoContentExcerpt,
  memoDisplayTitle,
  useTaskMemos,
} from '@/composables/useTaskMemos'
import { useGlobalMemoPanel } from '@/composables/useGlobalMemoPanel'
import { formatDateTime } from '@/utils/formatters'

const { panelVisible, openPanel, closePanel } = useGlobalMemoPanel()
const {
  loading,
  submitting,
  createDialogVisible,
  form,
  pinnedMemos,
  regularMemos,
  taskOptions,
  refreshMemos,
  openCreateDialog,
  openEditDialog,
  closeCreateDialog,
  submitMemo,
  removeMemo,
} = useTaskMemos()

onMounted(() => {
  void refreshMemos()
})

defineExpose({
  openPanel,
})
</script>

<template>
  <div class="global-memo-float">
    <el-button
      v-if="!panelVisible"
      type="primary"
      circle
      class="global-memo-float__fab"
      data-testid="global-memo-fab"
      @click="openPanel"
    >
      <el-icon><EditPen /></el-icon>
    </el-button>

    <transition name="global-memo-float-slide">
      <el-card
        v-if="panelVisible"
        shadow="always"
        class="global-memo-float__panel"
        data-testid="global-memo-panel"
        v-loading="loading"
      >
        <template #header>
          <div class="global-memo-float__header">
            <el-button type="primary" link data-testid="global-memo-new" @click="openCreateDialog">
              新建备忘
            </el-button>
            <el-button text data-testid="global-memo-collapse" @click="closePanel">收起</el-button>
          </div>
        </template>

        <el-empty
          v-if="pinnedMemos.length === 0 && regularMemos.length === 0"
          description="还没有备忘"
        />

        <div v-else class="global-memo-float__list">
          <template v-if="pinnedMemos.length > 0">
            <div class="global-memo-float__section-title">置顶备忘</div>
            <button
              v-for="memo in pinnedMemos"
              :key="memo.id"
              type="button"
              class="global-memo-float__item"
              @click="openEditDialog(memo)"
            >
              <div class="global-memo-float__item-actions">
                <el-tag type="warning" size="small" effect="plain">置顶</el-tag>
                <el-space>
                  <el-button text size="small" @click.stop="openEditDialog(memo)">编辑</el-button>
                  <el-button text size="small" type="danger" @click.stop="removeMemo(memo)">删除</el-button>
                </el-space>
              </div>
              <div class="global-memo-float__item-meta">
                <strong>{{ memoDisplayTitle(memo) }}</strong>
              </div>
              <p class="global-memo-float__content">{{ memoContentExcerpt(memo.content) }}</p>
              <div v-if="memo.related_task" class="global-memo-float__meta">
                关联任务：{{ memo.related_task.title }}
              </div>
            </button>
          </template>

          <template v-if="regularMemos.length > 0">
            <div class="global-memo-float__section-title">其他备忘</div>
            <button
              v-for="memo in regularMemos"
              :key="memo.id"
              type="button"
              class="global-memo-float__item"
              @click="openEditDialog(memo)"
            >
              <div class="global-memo-float__item-actions">
                <span class="global-memo-float__meta">更新于 {{ formatDateTime(memo.updated_at) }}</span>
                <el-space>
                  <el-button text size="small" @click.stop="openEditDialog(memo)">编辑</el-button>
                  <el-button text size="small" type="danger" @click.stop="removeMemo(memo)">删除</el-button>
                </el-space>
              </div>
              <div class="global-memo-float__item-meta">
                <strong>{{ memoDisplayTitle(memo) }}</strong>
              </div>
              <p class="global-memo-float__content">{{ memoContentExcerpt(memo.content) }}</p>
              <div v-if="memo.related_task" class="global-memo-float__meta">
                关联任务：{{ memo.related_task.title }}
              </div>
            </button>
          </template>
        </div>
      </el-card>
    </transition>

    <MemoCreateDialog
      v-model:visible="createDialogVisible"
      :submitting="submitting"
      :memo-id="form.memo_id"
      :title="form.title"
      :content="form.content"
      :related-task-id="form.related_task_id"
      :is-pinned="form.is_pinned"
      :task-options="taskOptions"
      @update:title="form.title = $event"
      @update:content="form.content = $event"
      @update:related-task-id="form.related_task_id = $event"
      @update:is-pinned="form.is_pinned = $event"
      @submit="submitMemo"
      @cancel="closeCreateDialog"
    />
  </div>
</template>

<style scoped>
.global-memo-float {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 2000;
}

.global-memo-float__fab {
  width: 52px;
  height: 52px;
  box-shadow: 0 8px 24px rgba(37, 99, 235, 0.35);
}

.global-memo-float__panel {
  width: min(380px, calc(100vw - 48px));
  max-height: min(70vh, 640px);
  overflow: auto;
  border-radius: 14px;
}

.global-memo-float__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.global-memo-float__list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.global-memo-float__section-title {
  color: var(--filum-text-secondary);
  font-size: 12px;
}

.global-memo-float__item {
  display: block;
  width: 100%;
  padding: 12px;
  border-radius: 10px;
  border: 1px solid var(--filum-border-strong);
  background: linear-gradient(180deg, #ffffff 0%, #f8faff 100%);
  text-align: left;
  cursor: pointer;
}

.global-memo-float__item:hover {
  border-color: var(--el-color-primary-light-5);
}

.global-memo-float__item-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.global-memo-float__item-meta {
  margin-top: 6px;
}

.global-memo-float__content {
  margin: 8px 0 0;
  line-height: 1.6;
  color: var(--filum-text-secondary);
}

.global-memo-float__meta {
  color: var(--filum-text-muted);
  font-size: 12px;
}

.global-memo-float-slide-enter-active,
.global-memo-float-slide-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.global-memo-float-slide-enter-from,
.global-memo-float-slide-leave-to {
  opacity: 0;
  transform: translateY(12px);
}
</style>
