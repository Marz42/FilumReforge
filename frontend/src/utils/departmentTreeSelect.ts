import type { DepartmentTreeNode } from '@/types/api'

export type DepartmentTreeSelectNode = {
  id: string
  label: string
  children?: DepartmentTreeSelectNode[]
}

/** Element Plus tree-select defaults to `value`; our nodes use `id`. */
export const DEPARTMENT_TREE_SELECT_PROPS = {
  value: 'id',
  label: 'label',
  children: 'children',
} as const

export function mapDepartmentTreeSelectNodes(
  nodes: DepartmentTreeNode[],
): DepartmentTreeSelectNode[] {
  return nodes.map((node) => {
    const children = node.children?.length
      ? mapDepartmentTreeSelectNodes(node.children)
      : undefined
    return {
      id: node.id,
      label: node.name,
      ...(children ? { children } : {}),
    }
  })
}

export function resolveTemplateScopeMode(
  departmentIds: readonly string[],
): 'global' | 'departments' {
  return departmentIds.some((id) => Boolean(id?.trim())) ? 'departments' : 'global'
}

export function normalizeScopeDepartmentIds(departmentIds: readonly string[]): string[] {
  const unique = new Set<string>()
  for (const raw of departmentIds) {
    const id = raw?.trim()
    if (id) {
      unique.add(id)
    }
  }
  return [...unique]
}
