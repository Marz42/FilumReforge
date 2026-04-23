import type { Department, DepartmentTreeNode } from '@/types/api'
import { http } from './http'

export interface CreateDepartmentPayload {
  name: string
  code: string
  parent_id?: string | null
  manager_id?: string | null
  sort_order?: number
}

export interface UpdateDepartmentPayload {
  name?: string | null
  code?: string | null
  parent_id?: string | null
  manager_id?: string | null
  sort_order?: number | null
  is_active?: boolean | null
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

export async function updateDepartment(
  departmentId: string,
  payload: UpdateDepartmentPayload,
): Promise<Department> {
  const { data } = await http.patch<Department>(`/departments/${departmentId}`, payload)
  return data
}

export async function deleteDepartment(departmentId: string): Promise<void> {
  await http.delete(`/departments/${departmentId}`)
}
