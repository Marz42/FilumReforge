import type { Task } from '@/types/api'

/**
 * Work Item action capabilities are derived from the backend `available_actions`
 * contract, never inferred from graph metadata. Iteration 3 decoupled standalone
 * Task from the graph engine, so the frontend must ask the backend what a task
 * supports instead of guessing from `workflow_graph_instance_id` etc.
 */

export function taskAvailableActions(task: Task | null | undefined): string[] {
  return (task?.available_actions ?? []).map((option) => option.action)
}

export function taskHasAction(task: Task | null | undefined, action: string): boolean {
  return taskAvailableActions(task).includes(action)
}

export function isStandaloneTask(task: Task | null | undefined): boolean {
  return task?.execution_mode === 'standalone'
}

export function canDelegateStandaloneTask(task: Task | null | undefined): boolean {
  return isStandaloneTask(task) && taskHasAction(task, 'delegate_assignment')
}
