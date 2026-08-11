import { ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('element-plus', () => ({
  ElMessage: {
    error: vi.fn(),
    success: vi.fn(),
    warning: vi.fn(),
  },
}))

vi.mock('@/api/attachments', () => ({
  uploadAttachment: vi.fn(),
}))

vi.mock('@/api/tasks', () => ({
  createTaskComment: vi.fn(),
}))

import { ElMessage } from 'element-plus'
import { uploadAttachment } from '@/api/attachments'
import { createTaskComment } from '@/api/tasks'
import { useTaskDetailCollaboration } from '@/composables/useTaskDetailCollaboration'
import type { Task } from '@/types/api'

function taskFixture(): Task {
  return {
    id: 'task-1',
    title: '资料与评论协调任务',
    description: null,
    creator_id: 'creator-1',
    assignee_id: 'assignee-1',
    department_id: 'department-1',
    status: 'doing',
    priority: 'medium',
    due_date: null,
    started_at: null,
    completed_at: null,
    parent_task_id: null,
    source_type: 'manual',
    extra_metadata: {},
    created_at: '2026-08-11T00:00:00Z',
    updated_at: '2026-08-11T00:00:00Z',
  }
}

function setup(selectedTask: Task | null = taskFixture()) {
  const task = ref<Task | null>(selectedTask)
  const reloadTask = vi.fn().mockResolvedValue(true)
  const collaboration = useTaskDetailCollaboration({ task, reloadTask })
  return { collaboration, reloadTask, task }
}

describe('useTaskDetailCollaboration', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(uploadAttachment).mockResolvedValue({ id: 'attachment-1' } as never)
    vi.mocked(createTaskComment).mockResolvedValue({ id: 'comment-1' } as never)
  })

  it('uploads every selected task file, clears selection and reloads once', async () => {
    const { collaboration, reloadTask } = setup()
    const first = new File(['first'], 'first.txt', { type: 'text/plain' })
    const second = new File(['second'], 'second.pdf', { type: 'application/pdf' })
    collaboration.selectedTaskFiles.value = [first, second]

    await collaboration.handleTaskAttachmentUpload()

    expect(uploadAttachment).toHaveBeenNthCalledWith(1, {
      file: first,
      target_type: 'task',
      target_id: 'task-1',
      visibility: 'private',
    })
    expect(uploadAttachment).toHaveBeenNthCalledWith(2, {
      file: second,
      target_type: 'task',
      target_id: 'task-1',
      visibility: 'private',
    })
    expect(ElMessage.success).toHaveBeenCalledWith('已上传 2 个任务资料附件')
    expect(collaboration.selectedTaskFiles.value).toEqual([])
    expect(collaboration.taskAttachmentResetKey.value).toBe(1)
    expect(reloadTask).toHaveBeenCalledExactlyOnceWith('task-1')
    expect(collaboration.taskAttachmentUploading.value).toBe(false)
  })

  it('does not upload without both a selected task and files', async () => {
    const { collaboration } = setup(null)

    await collaboration.handleTaskAttachmentUpload()

    expect(ElMessage.warning).toHaveBeenCalledWith('请选择任务并上传文件')
    expect(uploadAttachment).not.toHaveBeenCalled()
  })

  it('keeps task files available for retry when upload fails', async () => {
    vi.mocked(uploadAttachment).mockRejectedValue(new Error('upload failed'))
    const { collaboration, reloadTask } = setup()
    const file = new File(['retry'], 'retry.txt', { type: 'text/plain' })
    collaboration.selectedTaskFiles.value = [file]

    await collaboration.handleTaskAttachmentUpload()

    expect(collaboration.selectedTaskFiles.value).toEqual([file])
    expect(collaboration.taskAttachmentResetKey.value).toBe(0)
    expect(collaboration.taskAttachmentUploading.value).toBe(false)
    expect(reloadTask).not.toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('upload failed')
  })

  it('submits a trimmed comment, resets its form and reloads once', async () => {
    const { collaboration, reloadTask } = setup()
    const file = new File(['note'], 'note.txt', { type: 'text/plain' })
    collaboration.commentForm.content = '  请补充评审结论。  '
    collaboration.commentForm.is_internal = true
    collaboration.commentFiles.value = [file]

    await collaboration.handleCommentSubmit()

    expect(createTaskComment).toHaveBeenCalledWith('task-1', {
      content: '请补充评审结论。',
      is_internal: true,
      files: [file],
    })
    expect(collaboration.commentForm).toMatchObject({ content: '', is_internal: false })
    expect(collaboration.commentFiles.value).toEqual([])
    expect(collaboration.commentAttachmentResetKey.value).toBe(1)
    expect(reloadTask).toHaveBeenCalledExactlyOnceWith('task-1')
    expect(collaboration.commentSubmitting.value).toBe(false)
  })

  it('rejects a blank comment before calling the API', async () => {
    const { collaboration, reloadTask } = setup()
    collaboration.commentForm.content = '   '

    await collaboration.handleCommentSubmit()

    expect(ElMessage.warning).toHaveBeenCalledWith('请输入评论内容')
    expect(createTaskComment).not.toHaveBeenCalled()
    expect(reloadTask).not.toHaveBeenCalled()
  })

  it('keeps comment input and attachments available when submission fails', async () => {
    vi.mocked(createTaskComment).mockRejectedValue(new Error('comment failed'))
    const { collaboration, reloadTask } = setup()
    const file = new File(['retry'], 'retry.txt', { type: 'text/plain' })
    collaboration.commentForm.content = '请稍后重试'
    collaboration.commentForm.is_internal = true
    collaboration.commentFiles.value = [file]

    await collaboration.handleCommentSubmit()

    expect(collaboration.commentForm).toMatchObject({
      content: '请稍后重试',
      is_internal: true,
    })
    expect(collaboration.commentFiles.value).toEqual([file])
    expect(collaboration.commentAttachmentResetKey.value).toBe(0)
    expect(collaboration.commentSubmitting.value).toBe(false)
    expect(reloadTask).not.toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('comment failed')
  })
})
