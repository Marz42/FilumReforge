<script setup lang="ts">
import { onMounted } from 'vue'
import { EditPen } from '@element-plus/icons-vue'

import { useGlobalMemoPanel } from '@/composables/useGlobalMemoPanel'
import { useTaskMemos } from '@/composables/useTaskMemos'
import { formatDateTime } from '@/utils/formatters'

const { panelVisible, openPanel, closePanel, togglePanel } = useGlobalMemoPanel()
const {
  loading,
  submitting,
  form,
  pinnedMemos,
  regularMemos,
  taskOptions,
  resetForm,
  refreshMemos,
  startEdit,
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
            <span>个人备忘</span>
            <el-button text @click="closePanel">收起</el-button>
          </div>
        </template>

        <el-form label-position="top" class="global-memo-float__form">
          <el-form-item label="内容">
            <el-input
              v-model="form.content"
              type="textarea"
              :rows="4"
              placeholder="记录推进要点、跟进事项或协作提醒"
            />
          </el-form-item>
          <el-form-item label="关联任务">
            <el-select v-model="form.related_task_id" clearable placeholder="可选">
              <el-option
                v-for="task in taskOptions"
                :key="task.id"
                :label="task.label"
                :value="task.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="置顶">
            <el-switch v-model="form.is_pinned" />
          </el-form-item>
          <el-space wrap>
            <el-button type="primary" :loading="submitting" @click="submitMemo">
              {{ form.memo_id ? '保存备忘' : '创建备忘' }}
            </el-button>
            <el-button v-if="form.memo_id" text @click="resetForm">取消编辑</el-button>
          </el-space>
        </el-form>

        <el-divider />

        <el-empty
          v-if="pinnedMemos.length === 0 && regularMemos.length === 0"
          description="还没有备忘"
        />

        <div v-else class="global-memo-float__list">
          <template v-if="pinnedMemos.length > 0">
            <div class="global-memo-float__section-title">置顶备忘</div>
            <div
              v-for="memo in pinnedMemos"
              :key="memo.id"
              class="global-memo-float__item"
            >
              <div class="global-memo-float__item-actions">
                <el-tag type="warning" size="small" effect="plain">置顶</el-tag>
                <el-space>
                  <el-button text size="small" @click="startEdit(memo)">编辑</el-button>
                  <el-button text size="small" type="danger" @click="removeMemo(memo)">删除</el-button>
                </el-space>
              </div>
              <p class="global-memo-float__content">{{ memo.content }}</p>
              <div v-if="memo.related_task" class="global-memo-float__meta">
                关联任务：{{ memo.related_task.title }}
              </div>
            </div>
          </template>

          <template v-if="regularMemos.length > 0">
            <div class="global-memo-float__section-title">其他备忘</div>
            <div
              v-for="memo in regularMemos"
              :key="memo.id"
              class="global-memo-float__item"
            >
              <div class="global-memo-float__item-actions">
                <span class="global-memo-float__meta">更新于 {{ formatDateTime(memo.updated_at) }}</span>
                <el-space>
                  <el-button text size="small" @click="startEdit(memo)">编辑</el-button>
                  <el-button text size="small" type="danger" @click="removeMemo(memo)">删除</el-button>
                </el-space>
              </div>
              <p class="global-memo-float__content">{{ memo.content }}</p>
              <div v-if="memo.related_task" class="global-memo-float__meta">
                关联任务：{{ memo.related_task.title }}
              </div>
            </div>
          </template>
        </div>
      </el-card>
    </transition>
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

.global-memo-float__form {
  margin-bottom: 0;
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
  padding: 12px;
  border-radius: 10px;
  border: 1px solid var(--filum-border-strong);
  background: linear-gradient(180deg, #ffffff 0%, #f8faff 100%);
}

.global-memo-float__item-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.global-memo-float__content {
  margin: 8px 0 0;
  line-height: 1.6;
  white-space: pre-wrap;
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
