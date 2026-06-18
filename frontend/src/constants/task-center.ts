/** Task center v2 UI (P2 views, stats tab). Set to `false` to fall back to legacy TasksView board/gantt. */
export const TASK_CENTER_V2_UI_ENABLED =
  import.meta.env.VITE_TASK_CENTER_V2_UI_ENABLED !== 'false'

export type TaskCenterFilter = 'inbox' | 'tracking' | 'history' | 'stats'

export type TaskCenterViewMode = 'list' | 'board' | 'gantt'

export const TASK_USER_FACING_STATE_ORDER = [
  'pending',
  'in_progress',
  'awaiting_confirm',
  'completed',
  'returned',
] as const
