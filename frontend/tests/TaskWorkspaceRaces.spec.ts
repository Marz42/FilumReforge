import { effectScope, ref } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Task, TaskCenterSnapshot } from '@/types/api'
import type { TaskCenterFilter } from '@/constants/task-center'
import { clearAuthSession } from '@/api/session'
vi.mock('@/api/tasks', () => ({ listTasksByIds: vi.fn() }))
vi.mock('@/composables/useTaskUserFacingProjection', () => ({
  projectTasksForWorkspace: (tasks: Task[], userId: string) => tasks.map((task) => ({ taskId: task.id, userId })),
}))
import { listTasksByIds } from '@/api/tasks'
import { useTaskCenterWorkspace } from '@/composables/useTaskCenterWorkspace'

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => { resolve = done })
  return { promise, resolve }
}
function setup() {
  const filter = ref<TaskCenterFilter>('inbox')
  const enabled = ref(true)
  const user = ref('user-a')
  const snapshot = ref({ task_inbox: [{ task_id: 'a' }], task_tracking: [{ task_id: 'b' }], publish_user_options: [] } as unknown as TaskCenterSnapshot)
  const scope = effectScope()
  const workspace = scope.run(() => useTaskCenterWorkspace({ filter, enabled, snapshot, currentUserId: user }))!
  return { filter, enabled, user, scope, workspace }
}

describe('task workspace response ownership', () => {
  beforeEach(() => { clearAuthSession(); vi.resetAllMocks() })
  it('keeps the fast new filter response when the old response arrives last', async () => {
    const old = deferred<Task[]>()
    vi.mocked(listTasksByIds).mockReturnValueOnce(old.promise).mockResolvedValueOnce([{ id: 'b' }] as Task[])
    const state = setup()
    state.filter.value = 'tracking'
    await flushPromises()
    expect(state.workspace.rows.value[0]?.taskId).toBe('b')
    old.resolve([{ id: 'a' }] as Task[])
    await flushPromises()
    expect(state.workspace.rows.value[0]?.taskId).toBe('b')
    state.scope.stop()
  })
  it.each(['disable', 'logout', 'dispose'])('invalidates a pending response on %s', async (action) => {
    const old = deferred<Task[]>()
    vi.mocked(listTasksByIds).mockReturnValue(old.promise)
    const state = setup()
    const signal = vi.mocked(listTasksByIds).mock.calls[0]?.[1]
    if (action === 'disable') state.enabled.value = false
    if (action === 'logout') clearAuthSession()
    if (action === 'dispose') state.scope.stop()
    expect(signal?.aborted).toBe(true)
    old.resolve([{ id: 'a' }] as Task[])
    await flushPromises()
    expect(state.workspace.rows.value).toEqual([])
    expect(state.workspace.loading.value).toBe(false)
    state.scope.stop()
  })
  it('captures a current failure instead of leaking a watcher rejection', async () => {
    const error = new Error('network unavailable')
    vi.mocked(listTasksByIds).mockRejectedValue(error)
    const state = setup()
    await flushPromises()
    expect(state.workspace.error.value).toBe(error)
    expect(state.workspace.loading.value).toBe(false)
    state.scope.stop()
  })
})
