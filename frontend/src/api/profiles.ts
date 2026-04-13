import type { Profile } from '@/types/api'
import { http } from './http'

export interface CreateProfilePayload {
  user_id: string
  employee_no: string
  real_name: string
  department_id: string
  job_title?: string | null
  phone?: string | null
  hire_date?: string | null
  custom_fields?: Record<string, unknown>
}

export async function listProfiles(): Promise<Profile[]> {
  const { data } = await http.get<Profile[]>('/profiles')
  return data
}

export async function createProfile(payload: CreateProfilePayload): Promise<Profile> {
  const { data } = await http.post<Profile>('/profiles', payload)
  return data
}
