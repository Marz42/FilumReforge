import { describe, expect, it } from 'vitest'

import type { DepartmentTreeNode } from '@/types/api'
import {
  DEPARTMENT_TREE_SELECT_PROPS,
  mapDepartmentTreeSelectNodes,
  normalizeScopeDepartmentIds,
  resolveTemplateScopeMode,
} from '@/utils/departmentTreeSelect'

function dept(
  id: string,
  name: string,
  children: DepartmentTreeNode[] = [],
): DepartmentTreeNode {
  return {
    id,
    name,
    code: id,
    parent_id: null,
    manager_id: null,
    sort_order: 0,
    is_active: true,
    children,
  }
}

describe('departmentTreeSelect', () => {
  it('maps nested department trees onto id/label nodes for el-tree-select', () => {
    const mapped = mapDepartmentTreeSelectNodes([
      dept('root', '总部', [dept('child', '一部', [dept('leaf', '一组')])]),
    ])

    expect(mapped).toEqual([
      {
        id: 'root',
        label: '总部',
        children: [
          {
            id: 'child',
            label: '一部',
            children: [{ id: 'leaf', label: '一组' }],
          },
        ],
      },
    ])
    expect(DEPARTMENT_TREE_SELECT_PROPS.value).toBe('id')
  })

  it('resolves departments mode only when at least one department id is present', () => {
    expect(resolveTemplateScopeMode([])).toBe('global')
    expect(resolveTemplateScopeMode(['', '  '])).toBe('global')
    expect(resolveTemplateScopeMode(['dept-a'])).toBe('departments')
    expect(normalizeScopeDepartmentIds(['dept-a', '', 'dept-a', ' dept-b '])).toEqual([
      'dept-a',
      'dept-b',
    ])
  })
})
