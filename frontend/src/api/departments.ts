import type { Department, DepartmentTreeNode } from '@/types/api'
import { http } from './http'

export interface CreateDepartmentPayload {
  name: string
  code: string
  parent_id?: string | null
  manager_id?: string | null
  sort_order?: number
}

export async function listDepartments(): Promise<Department[]> {
  const { data } = await http.get<Department[]>('/departments')
  return data
}

export async function listDepartmentTree(): Promise<DepartmentTreeNode[]> {
  const { data } = await http.get<DepartmentTreeNode[]>('/departments/tree')
  return data
}

export async function createDepartment(payload: CreateDepartmentPayload): Promise<Department> {
  const { data } = await http.post<Department>('/departments', payload)
  return data
}
