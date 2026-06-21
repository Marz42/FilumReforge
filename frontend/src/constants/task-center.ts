/** Task center v2 UI is always enabled; legacy TasksView embedding was removed in TCE Phase 5. */
export const TASK_CENTER_V2_UI_ENABLED = true

export type TaskCenterFilter = 'inbox' | 'tracking' | 'history' | 'stats'

export type TaskCenterViewMode = 'list' | 'board' | 'gantt'

export const TASK_USER_FACING_STATE_ORDER = [
  'pending',
  'in_progress',
  'awaiting_confirm',
  'completed',
  'returned',
] as const
