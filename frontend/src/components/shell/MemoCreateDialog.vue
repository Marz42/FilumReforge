<script setup lang="ts">
import { computed } from 'vue'

const visible = defineModel<boolean>('visible', { default: false })

const props = defineProps<{
  submitting?: boolean
  memoId?: string
  title: string
  content: string
  relatedTaskId: string
  isPinned: boolean
  taskOptions: Array<{ id: string; label: string }>
}>()

const emit = defineEmits<{
  'update:title': [value: string]
  'update:content': [value: string]
  'update:relatedTaskId': [value: string]
  'update:isPinned': [value: boolean]
  submit: []
  cancel: []
}>()

const dialogTitle = computed(() => (props.memoId ? '编辑备忘' : '新建备忘'))
const submitLabel = computed(() => (props.memoId ? '保存备忘' : '创建备忘'))
</script>

<template>
  <el-dialog
    v-model="visible"
    :title="dialogTitle"
    width="520px"
    align-center
    append-to-body
    modal
    destroy-on-close
    data-testid="memo-create-dialog"
    @close="emit('cancel')"
  >
    <el-form label-position="top">
      <el-form-item label="标题">
        <el-input
          :model-value="title"
          placeholder="无标题"
          maxlength="200"
          show-word-limit
          data-testid="memo-create-title"
          @update:model-value="emit('update:title', $event)"
        />
      </el-form-item>
      <el-form-item label="内容" required>
        <el-input
          :model-value="content"
          type="textarea"
          :rows="5"
          placeholder="记录推进要点、跟进事项或协作提醒"
          data-testid="memo-create-content"
          @update:model-value="emit('update:content', $event)"
        />
      </el-form-item>
      <el-form-item label="关联任务">
        <el-select
          :model-value="relatedTaskId"
          clearable
          placeholder="可选"
          data-testid="memo-create-related-task"
          @update:model-value="emit('update:relatedTaskId', $event ?? '')"
        >
          <el-option
            v-for="task in taskOptions"
            :key="task.id"
            :label="task.label"
            :value="task.id"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="置顶">
        <el-switch
          :model-value="isPinned"
          data-testid="memo-create-pinned"
          @update:model-value="emit('update:isPinned', $event)"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button data-testid="memo-create-cancel" @click="emit('cancel')">取消</el-button>
      <el-button
        type="primary"
        :loading="submitting"
        data-testid="memo-create-submit"
        @click="emit('submit')"
      >
        {{ submitLabel }}
      </el-button>
    </template>
  </el-dialog>
</template>
