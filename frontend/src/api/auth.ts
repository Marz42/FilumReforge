import type {
  AuthSession,
  User,
  UserInvitation,
  UserInvitationPreview,
  UserRole,
} from '@/types/api'
import { http, rawHttp } from './http'

export interface LoginPayload {
  email: string
  password: string
}

export interface BootstrapAdminPayload extends LoginPayload {
  real_name: string
  employee_no: string
}

export interface CreateInvitationPayload {
  email: string
  role: UserRole
}

export interface AcceptInvitationPayload {
  token: string
  password: string
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

export async function createInvitation(payload: CreateInvitationPayload): Promise<UserInvitation> {
  const { data } = await http.post<UserInvitation>('/auth/invitations', payload)
  return data
}

export async function getInvitationPreview(token: string): Promise<UserInvitationPreview> {
  const { data } = await rawHttp.get<UserInvitationPreview>('/auth/invitations/preview', {
    params: { token },
  })
  return data
}

export async function acceptInvitation(payload: AcceptInvitationPayload): Promise<AuthSession> {
  const { data } = await rawHttp.post<AuthSession>('/auth/invitations/accept', payload)
  return data
}

export async function refreshSession(): Promise<AuthSession> {
  const { data } = await rawHttp.post<AuthSession>('/auth/refresh')
  return data
}

export async function logout(): Promise<void> {
  await rawHttp.post('/auth/logout')
}

export async function getCurrentUser(): Promise<User> {
  const { data } = await http.get<User>('/auth/me')
  return data
}

export async function getBootstrapStatus(): Promise<BootstrapStatus> {
  const { data } = await rawHttp.get<BootstrapStatus>('/auth/bootstrap-status')
  return data
}
