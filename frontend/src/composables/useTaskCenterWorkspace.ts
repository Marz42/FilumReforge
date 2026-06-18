import { ref, watch, type Ref } from 'vue'

import { listTasks } from '@/api/tasks'
import type { Task, TaskCenterSnapshot } from '@/types/api'
import type { TaskCenterFilter } from '@/constants/task-center'

import {
  projectTasksForWorkspace,
  type TaskCenterWorkspaceRow,
} from './useTaskUserFacingProjection'

export function extractTaskIdsFromSnapshot(
  snapshot: TaskCenterSnapshot | null,
  filter: TaskCenterFilter,
): string[] {
  if (!snapshot || filter === 'stats') {
    return []
  }
  if (filter === 'inbox') {
    return snapshot.task_inbox.map((item) => item.task_id)
  }
  if (filter === 'history') {
    return snapshot.task_history.map((item) => item.task_id)
  }
  return snapshot.task_tracking.map((item) => item.task_id)
}

function enrichRowsFromSnapshot(
  rows: TaskCenterWorkspaceRow[],
  snapshot: TaskCenterSnapshot | null,
  filter: TaskCenterFilter,
): TaskCenterWorkspaceRow[] {
  if (!snapshot || filter === 'stats') {
    return rows
  }

  const snapshotById = new Map<string, { relationTypes: string[] }>()
  const source =
    filter === 'inbox'
      ? snapshot.task_inbox
      : filter === 'history'
        ? snapshot.task_history
        : snapshot.task_tracking

  for (const item of source) {
    snapshotById.set(item.task_id, {
      relationTypes: 'relation_types' in item ? item.relation_types : [],
    })
  }

  return rows.map((row) => {
    const meta = snapshotById.get(row.taskId)
    if (!meta) {
      return row
    }
    return {
      ...row,
      relationTypes: meta.relationTypes,
    }
  })
}

export function useTaskCenterWorkspace(options: {
  filter: Ref<TaskCenterFilter>
  snapshot: Ref<TaskCenterSnapshot | null>
  currentUserId: Ref<string | null | undefined>
  enabled: Ref<boolean>
}) {
  const loading = ref(false)
  const rows = ref<TaskCenterWorkspaceRow[]>([])

  async function refresh(): Promise<void> {
    if (!options.enabled.value) {
      rows.value = []
      return
    }

    const filter = options.filter.value
    if (filter === 'stats') {
      rows.value = []
      return
    }

    const ids = extractTaskIdsFromSnapshot(options.snapshot.value, filter)
    if (ids.length === 0) {
      rows.value = []
      return
    }

    loading.value = true
    try {
      const allTasks = await listTasks()
      const taskById = new Map(allTasks.map((task) => [task.id, task]))
      const orderedTasks = ids
        .map((id) => taskById.get(id))
        .filter((task): task is Task => task !== undefined)
      const projected = projectTasksForWorkspace(orderedTasks, options.currentUserId.value)
      rows.value = enrichRowsFromSnapshot(projected, options.snapshot.value, filter)
    } finally {
      loading.value = false
    }
  }

  watch(
    [options.filter, options.snapshot, options.enabled, options.currentUserId],
    () => {
      void refresh()
    },
    { deep: true, immediate: true },
  )

  return {
    rows,
    loading,
    refresh,
  }
}
