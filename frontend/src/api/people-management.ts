import type {
  PeopleManagementDetail,
  PeopleManagementSnapshot,
} from '@/types/api'
import { http } from './http'

export async function getPeopleManagement(): Promise<PeopleManagementSnapshot> {
  const { data } = await http.get<PeopleManagementSnapshot>('/people-management')
  return data
}

export async function getPeopleManagementDetail(userId: string): Promise<PeopleManagementDetail> {
  const { data } = await http.get<PeopleManagementDetail>(`/people-management/${userId}`)
  return data
}
