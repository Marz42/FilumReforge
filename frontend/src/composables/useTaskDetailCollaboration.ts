import { reactive, ref, toValue, type MaybeRefOrGetter } from 'vue'
import { ElMessage } from 'element-plus'

import { uploadAttachment } from '@/api/attachments'
import { createTaskComment } from '@/api/tasks'
import type { Task } from '@/types/api'
import { showError } from '@/utils/errors'

type TaskDetailCollaborationOptions = {
  task: MaybeRefOrGetter<Task | null>
  reloadTask: (taskId: string) => Promise<unknown>
}

export function useTaskDetailCollaboration(options: TaskDetailCollaborationOptions) {
  const taskAttachmentUploading = ref(false)
  const commentSubmitting = ref(false)
  const selectedTaskFiles = ref<File[]>([])
  const commentFiles = ref<File[]>([])
  const taskAttachmentResetKey = ref(0)
  const commentAttachmentResetKey = ref(0)

  const commentForm = reactive({
    content: '',
    is_internal: false,
  })

  function resetCommentForm(): void {
    commentForm.content = ''
    commentForm.is_internal = false
    commentFiles.value = []
    commentAttachmentResetKey.value += 1
  }

  async function handleTaskAttachmentUpload(): Promise<void> {
    const task = toValue(options.task)
    const files = [...selectedTaskFiles.value]
    if (!task || files.length === 0) {
      ElMessage.warning('请选择任务并上传文件')
      return
    }

    taskAttachmentUploading.value = true
    try {
      for (const file of files) {
        await uploadAttachment({
          file,
          target_type: 'task',
          target_id: task.id,
          visibility: 'private',
        })
      }

      ElMessage.success(
        files.length > 1
          ? `已上传 ${files.length} 个任务资料附件`
          : '任务资料附件已上传',
      )
      selectedTaskFiles.value = []
      taskAttachmentResetKey.value += 1
      await options.reloadTask(task.id)
    } catch (error) {
      showError(error)
    } finally {
      taskAttachmentUploading.value = false
    }
  }

  async function handleCommentSubmit(): Promise<void> {
    const task = toValue(options.task)
    if (!task) {
      ElMessage.warning('请先选择任务')
      return
    }

    const content = commentForm.content.trim()
    if (!content) {
      ElMessage.warning('请输入评论内容')
      return
    }

    commentSubmitting.value = true
    try {
      await createTaskComment(task.id, {
        content,
        is_internal: commentForm.is_internal,
        files: commentFiles.value,
      })
      ElMessage.success('评论已提交')
      resetCommentForm()
      await options.reloadTask(task.id)
    } catch (error) {
      showError(error)
    } finally {
      commentSubmitting.value = false
    }
  }

  return {
    commentAttachmentResetKey,
    commentFiles,
    commentForm,
    commentSubmitting,
    handleCommentSubmit,
    handleTaskAttachmentUpload,
    selectedTaskFiles,
    taskAttachmentResetKey,
    taskAttachmentUploading,
  }
}
