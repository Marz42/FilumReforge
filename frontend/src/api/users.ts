import type { User, UserRole, UserStatus } from '@/types/api'
import { http } from './http'

export interface CreateUserPayload {
  email: string
  password: string
  role: UserRole
  status: UserStatus
}

export interface UpdateUserPayload {
  email?: string
  password?: string
  role?: UserRole
  status?: UserStatus
}

export async function listUsers(): Promise<User[]> {
  const { data } = await http.get<User[]>('/users')
  return data
}

export async function createUser(payload: CreateUserPayload): Promise<User> {
  const { data } = await http.post<User>('/users', payload)
  return data
}

export async function updateUser(userId: string, payload: UpdateUserPayload): Promise<User> {
  const { data } = await http.patch<User>(`/users/${userId}`, payload)
  return data
}
