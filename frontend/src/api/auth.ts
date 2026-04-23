import type { AuthSession, User } from '@/types/api'
import { http, rawHttp } from './http'

export interface LoginPayload {
  email: string
  password: string
}

export interface BootstrapAdminPayload extends LoginPayload {
  real_name: string
  employee_no: string
}

export interface BootstrapStatus {
  bootstrap_required: boolean
}

export async function bootstrapAdmin(payload: BootstrapAdminPayload): Promise<User> {
  const { data } = await rawHttp.post<User>('/auth/bootstrap-admin', payload)
  return data
}

export async function login(payload: LoginPayload): Promise<AuthSession> {
  const { data } = await rawHttp.post<AuthSession>('/auth/login', payload)
  return data
}

export async function getCurrentUser(): Promise<User> {
  const { data } = await http.get<User>('/auth/me')
  return data
}

export async function getBootstrapStatus(): Promise<BootstrapStatus> {
  const { data } = await rawHttp.get<BootstrapStatus>('/auth/bootstrap-status')
  return data
}
