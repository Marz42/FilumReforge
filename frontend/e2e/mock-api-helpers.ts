import type { Route } from '@playwright/test'

export function getApiPath(url: string): string {
  const parsed = new URL(url)
  const apiPrefix = '/api/v1'
  const prefixIndex = parsed.pathname.indexOf(apiPrefix)
  const path = prefixIndex >= 0 ? parsed.pathname.slice(prefixIndex + apiPrefix.length) : parsed.pathname
  return `${path}${parsed.search}`
}

export async function fulfillJson(route: Route, data: unknown, status = 200): Promise<void> {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(data),
  })
}

export function isExactApiPath(apiPath: string, path: string): boolean {
  return apiPath === path || apiPath.startsWith(`${path}?`)
}

export function getApiPathname(apiPath: string): string {
  const queryIndex = apiPath.indexOf('?')
  return queryIndex >= 0 ? apiPath.slice(0, queryIndex) : apiPath
}

export function parseQueryParam(apiPath: string, key: string): string | null {
  const queryIndex = apiPath.indexOf('?')
  if (queryIndex < 0) {
    return null
  }
  return new URLSearchParams(apiPath.slice(queryIndex + 1)).get(key)
}

export const defaultTaskCenterPagination = {
  next_cursor: null,
  has_more: false,
}

type TaskLike = { id: string }

export async function fulfillTasksListGet(
  route: Route,
  apiPath: string,
  allTasks: TaskLike[],
): Promise<boolean> {
  if (!isExactApiPath(apiPath, '/tasks')) {
    return false
  }

  const idsParam = parseQueryParam(apiPath, 'ids')
  if (idsParam) {
    const ids = idsParam.split(',').map((value) => value.trim()).filter(Boolean)
    const taskById = new Map(allTasks.map((task) => [task.id, task]))
    const tasks = ids.map((id) => taskById.get(id)).filter((task): task is TaskLike => task !== undefined)
    await fulfillJson(route, tasks)
    return true
  }

  await fulfillJson(route, allTasks)
  return true
}

export async function fulfillTaskCenterListPage(
  route: Route,
  apiPath: string,
  path: '/task-center/inbox' | '/task-center/tracking' | '/task-center/history',
  items: unknown[],
): Promise<boolean> {
  if (!isExactApiPath(apiPath, path)) {
    return false
  }

  await fulfillJson(route, {
    items,
    pagination: defaultTaskCenterPagination,
  })
  return true
}
