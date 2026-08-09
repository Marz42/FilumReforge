import { computed, ref, toValue, type MaybeRefOrGetter } from 'vue'

import { listAttachments } from '@/api/attachments'
import { listDepartments } from '@/api/departments'
import { getTask, listTaskActivity, listTaskWatchers } from '@/api/tasks'
import { listUsers } from '@/api/users'
import { getWorkflowGraphInstance, listInstanceEvents } from '@/api/workflow-graph'
import type {
  Attachment,
  Department,
  Task,
  TaskActivityEntry,
  TaskWatcher,
  User,
  WorkflowGraphInstanceDetail,
} from '@/types/api'
import type { WorkflowRunEventItem } from '@/types/workflowVideo'

type TaskDetailDataOptions = {
  isManagementRole: MaybeRefOrGetter<boolean>
  currentUser: MaybeRefOrGetter<User | null | undefined>
  onActivityLoadFailure?: () => void
  onLoadFailure?: (error: unknown) => void
}

type GraphSnapshot = {
  instance: WorkflowGraphInstanceDetail | null
  events: WorkflowRunEventItem[]
}

export function useTaskDetailData(options: TaskDetailDataOptions) {
  const detailLoading = ref(false)
  const referenceLoading = ref(false)
  const task = ref<Task | null>(null)
  const taskAttachments = ref<Attachment[]>([])
  const taskActivity = ref<TaskActivityEntry[]>([])
  const taskWatchers = ref<TaskWatcher[]>([])
  const graphInstance = ref<WorkflowGraphInstanceDetail | null>(null)
  const workflowRunEvents = ref<WorkflowRunEventItem[]>([])
  const departments = ref<Department[]>([])
  const users = ref<User[]>([])

  const loading = computed(() => detailLoading.value || referenceLoading.value)
  let detailRequestVersion = 0

  function resetTaskState(): void {
    task.value = null
    taskAttachments.value = []
    taskActivity.value = []
    taskWatchers.value = []
    graphInstance.value = null
    workflowRunEvents.value = []
  }

  function clearTaskDetails(): void {
    detailRequestVersion += 1
    detailLoading.value = false
    resetTaskState()
  }

  async function loadGraphSnapshot(loadedTask: Task): Promise<GraphSnapshot> {
    const metadata = (loadedTask.extra_metadata ?? {}) as Record<string, unknown>
    const instanceId = typeof metadata.workflow_graph_instance_id === 'string'
      ? metadata.workflow_graph_instance_id
      : null
    if (!instanceId) {
      return { instance: null, events: [] }
    }

    try {
      const [instance, eventsPage] = await Promise.all([
        getWorkflowGraphInstance(instanceId),
        listInstanceEvents(instanceId, { limit: 50 }),
      ])
      return { instance, events: eventsPage.items }
    } catch {
      return { instance: null, events: [] }
    }
  }

  async function loadSelectedTaskDetails(taskId: string): Promise<boolean> {
    const requestVersion = ++detailRequestVersion
    detailLoading.value = true

    try {
      const loadedTask = await getTask(taskId)
      if (requestVersion !== detailRequestVersion) {
        return false
      }

      // Render the new primary record as soon as it is available. Related
      // collections are cleared first so data from the previous selection is
      // never displayed under the new task while optional requests finish.
      task.value = loadedTask
      taskAttachments.value = []
      taskActivity.value = []
      taskWatchers.value = []
      graphInstance.value = null
      workflowRunEvents.value = []

      const [attachmentsResult, activityResult, watchersResult, graphSnapshot] = await Promise.all([
        listAttachments({ target_type: 'task', target_id: taskId })
          .then((value) => ({ ok: true as const, value }))
          .catch(() => ({ ok: false as const, value: [] as Attachment[] })),
        listTaskActivity(taskId)
          .then((value) => ({ ok: true as const, value }))
          .catch(() => ({ ok: false as const, value: [] as TaskActivityEntry[] })),
        listTaskWatchers(taskId)
          .then((value) => ({ ok: true as const, value }))
          .catch(() => ({ ok: false as const, value: [] as TaskWatcher[] })),
        loadGraphSnapshot(loadedTask),
      ])
      if (requestVersion !== detailRequestVersion) {
        return false
      }

      taskAttachments.value = attachmentsResult.value
      taskActivity.value = activityResult.value
      taskWatchers.value = watchersResult.value
      graphInstance.value = graphSnapshot.instance
      workflowRunEvents.value = graphSnapshot.events
      if (!activityResult.ok) {
        options.onActivityLoadFailure?.()
      }
      return true
    } catch (error) {
      if (requestVersion === detailRequestVersion) {
        resetTaskState()
        options.onLoadFailure?.(error)
      }
      return false
    } finally {
      if (requestVersion === detailRequestVersion) {
        detailLoading.value = false
      }
    }
  }

  async function loadReferenceData(): Promise<void> {
    referenceLoading.value = true
    try {
      const currentUser = toValue(options.currentUser)
      const [loadedUsers, loadedDepartments] = await Promise.all([
        toValue(options.isManagementRole)
          ? listUsers()
          : Promise.resolve(currentUser ? [currentUser] : []),
        listDepartments().catch(() => [] as Department[]),
      ])
      users.value = loadedUsers
      departments.value = loadedDepartments
    } catch (error) {
      users.value = []
      options.onLoadFailure?.(error)
    } finally {
      referenceLoading.value = false
    }
  }

  return {
    loading,
    task,
    taskAttachments,
    taskActivity,
    taskWatchers,
    graphInstance,
    workflowRunEvents,
    departments,
    users,
    clearTaskDetails,
    loadReferenceData,
    loadSelectedTaskDetails,
  }
}
