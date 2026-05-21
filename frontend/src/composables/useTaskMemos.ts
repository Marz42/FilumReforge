import { computed, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { createTaskMemo, deleteTaskMemo, getTaskCenterSnapshot, updateTaskMemo } from '@/api/task-center'
import type { TaskCenterSnapshot, TaskMemo } from '@/types/api'
import { getErrorMessage } from '@/utils/errors'

export function memoDisplayTitle(memo: Pick<TaskMemo, 'title'>): string {
  const trimmed = memo.title?.trim()
  return trimmed ? trimmed : '无标题'
}

export function memoContentExcerpt(content: string, maxLength = 80): string {
  const normalized = content.replace(/\s+/g, ' ').trim()
  if (normalized.length <= maxLength) {
    return normalized
  }
  return `${normalized.slice(0, maxLength)}…`
}

export function useTaskMemos() {
  const loading = ref(false)
  const submitting = ref(false)
  const createDialogVisible = ref(false)
  const snapshot = ref<TaskCenterSnapshot | null>(null)

  const form = reactive({
    memo_id: '',
    title: '',
    content: '',
    related_task_id: '',
    is_pinned: false,
  })

  const pinnedMemos = computed(() => (snapshot.value?.task_memos ?? []).filter((memo) => memo.is_pinned))
  const regularMemos = computed(() => (snapshot.value?.task_memos ?? []).filter((memo) => !memo.is_pinned))

  const taskOptions = computed(() => {
    const options = new Map<string, { id: string; label: string }>()

    const addOption = (id: string, title: string): void => {
      if (!options.has(id)) {
        options.set(id, { id, label: title })
      }
    }

    for (const item of snapshot.value?.task_inbox ?? []) {
      addOption(item.task_id, item.title)
    }
    for (const item of snapshot.value?.task_tracking ?? []) {
      addOption(item.task_id, item.title)
    }
    for (const item of snapshot.value?.task_history ?? []) {
      addOption(item.task_id, item.title)
    }

    return Array.from(options.values())
  })

  function resetForm(): void {
    form.memo_id = ''
    form.title = ''
    form.content = ''
    form.related_task_id = ''
    form.is_pinned = false
  }

  function openCreateDialog(): void {
    resetForm()
    createDialogVisible.value = true
  }

  function openEditDialog(memo: TaskMemo): void {
    form.memo_id = memo.id
    form.title = memo.title ?? ''
    form.content = memo.content
    form.related_task_id = memo.related_task_id ?? ''
    form.is_pinned = memo.is_pinned
    createDialogVisible.value = true
  }

  function closeCreateDialog(): void {
    createDialogVisible.value = false
    resetForm()
  }

  async function refreshMemos(): Promise<void> {
    loading.value = true
    try {
      snapshot.value = await getTaskCenterSnapshot()
    } catch (error) {
      ElMessage.error(getErrorMessage(error))
    } finally {
      loading.value = false
    }
  }

  async function submitMemo(): Promise<void> {
    if (!form.content.trim()) {
      ElMessage.warning('请输入备忘内容')
      return
    }

    const title = form.title.trim() || null

    submitting.value = true
    try {
      if (form.memo_id) {
        await updateTaskMemo(form.memo_id, {
          title,
          content: form.content.trim(),
          related_task_id: form.related_task_id || null,
          is_pinned: form.is_pinned,
        })
        ElMessage.success('备忘已更新')
      } else {
        await createTaskMemo({
          title,
          content: form.content.trim(),
          related_task_id: form.related_task_id || null,
          is_pinned: form.is_pinned,
        })
        ElMessage.success('备忘已创建')
      }
      closeCreateDialog()
      await refreshMemos()
    } catch (error) {
      ElMessage.error(getErrorMessage(error))
    } finally {
      submitting.value = false
    }
  }

  async function removeMemo(memo: TaskMemo): Promise<void> {
    try {
      await ElMessageBox.confirm('删除后无法恢复，是否继续？', '删除备忘', {
        type: 'warning',
      })
      await deleteTaskMemo(memo.id)
      if (form.memo_id === memo.id) {
        closeCreateDialog()
      }
      ElMessage.success('备忘已删除')
      await refreshMemos()
    } catch (error) {
      if (error === 'cancel' || error === 'close') {
        return
      }
      if (error instanceof Error && (error.message === 'cancel' || error.message === 'close')) {
        return
      }
      ElMessage.error(getErrorMessage(error))
    }
  }

  return {
    loading,
    submitting,
    createDialogVisible,
    form,
    pinnedMemos,
    regularMemos,
    taskOptions,
    resetForm,
    refreshMemos,
    openCreateDialog,
    openEditDialog,
    closeCreateDialog,
    submitMemo,
    removeMemo,
  }
}
