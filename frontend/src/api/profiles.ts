import type {
  Delegation,
  DelegationScopeType,
  DelegationStatus,
  EmploymentEvent,
  EmploymentEventType,
  Position,
  PositionAssignmentType,
  Profile,
  ProfileFieldDefinition,
  ProfileFieldPermission,
  ProfilePosition,
  ReportingLine,
  ReportingLineType,
} from '@/types/api'
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

export interface UpdateProfilePayload {
  employee_no?: string | null
  real_name?: string | null
  department_id?: string | null
  job_title?: string | null
  phone?: string | null
  hire_date?: string | null
  custom_fields?: Record<string, unknown> | null
}

export interface CreatePositionPayload {
  code: string
  name: string
  level?: string | null
  extra_metadata?: Record<string, unknown>
  is_active?: boolean
}

export interface CreateProfilePositionPayload {
  position_id: string
  department_id: string
  assignment_type: PositionAssignmentType
  is_primary: boolean
  starts_at: string
  ends_at?: string | null
}

export interface CreateReportingLinePayload {
  manager_user_id: string
  department_id?: string | null
  line_type: ReportingLineType
  is_primary: boolean
  starts_at: string
  ends_at?: string | null
}

export interface CreateEmploymentEventPayload {
  event_type: EmploymentEventType
  effective_date: string
  title: string
  summary?: string | null
  payload?: Record<string, unknown>
}

export interface CreateDelegationPayload {
  delegator_user_id: string
  delegate_user_id: string
  scope_type: DelegationScopeType
  scope_department_id?: string | null
  scope_filters?: Record<string, unknown>
  starts_at: string
  ends_at: string
}

export interface UpdateDelegationPayload {
  status?: DelegationStatus
  starts_at?: string | null
  ends_at?: string | null
  scope_department_id?: string | null
  scope_filters?: Record<string, unknown> | null
}

export interface CreateProfileFieldDefinitionPayload {
  field_key: string
  label: string
  field_type: string
  storage_target: string
  is_sensitive?: boolean
  config?: Record<string, unknown>
  is_active?: boolean
}

export interface UpdateProfileFieldDefinitionPayload {
  label?: string
  field_type?: string
  storage_target?: string
  is_sensitive?: boolean
  config?: Record<string, unknown>
  is_active?: boolean
}

export interface CreateProfileFieldPermissionPayload {
  field_definition_id: string
  subject_type: string
  subject_value?: string | null
  can_view?: boolean
  can_edit?: boolean
  scope_filters?: Record<string, unknown>
  priority?: number
}

export interface UpdateProfileFieldPermissionPayload {
  subject_type?: string
  subject_value?: string | null
  can_view?: boolean
  can_edit?: boolean
  scope_filters?: Record<string, unknown>
  priority?: number
}

export async function listProfiles(): Promise<Profile[]> {
  const { data } = await http.get<Profile[]>('/profiles')
  return data
}

export async function getProfile(userId: string): Promise<Profile> {
  const { data } = await http.get<Profile>(`/profiles/${userId}`)
  return data
}

export async function createProfile(payload: CreateProfilePayload): Promise<Profile> {
  const { data } = await http.post<Profile>('/profiles', payload)
  return data
}

export async function updateProfile(userId: string, payload: UpdateProfilePayload): Promise<Profile> {
  const { data } = await http.patch<Profile>(`/profiles/${userId}`, payload)
  return data
}

export async function listPositions(): Promise<Position[]> {
  const { data } = await http.get<Position[]>('/positions')
  return data
}

export async function createPosition(payload: CreatePositionPayload): Promise<Position> {
  const { data } = await http.post<Position>('/positions', payload)
  return data
}

export async function createProfilePosition(
  userId: string,
  payload: CreateProfilePositionPayload,
): Promise<ProfilePosition> {
  const { data } = await http.post<ProfilePosition>(`/profiles/${userId}/positions`, payload)
  return data
}

export async function createProfileReportingLine(
  userId: string,
  payload: CreateReportingLinePayload,
): Promise<ReportingLine> {
  const { data } = await http.post<ReportingLine>(`/profiles/${userId}/reporting-lines`, payload)
  return data
}

export async function createProfileEvent(
  userId: string,
  payload: CreateEmploymentEventPayload,
): Promise<EmploymentEvent> {
  const { data } = await http.post<EmploymentEvent>(`/profiles/${userId}/events`, payload)
  return data
}

export async function createDelegation(payload: CreateDelegationPayload): Promise<Delegation> {
  const { data } = await http.post<Delegation>('/delegations', payload)
  return data
}

export async function updateDelegation(
  delegationId: string,
  payload: UpdateDelegationPayload,
): Promise<Delegation> {
  const { data } = await http.patch<Delegation>(`/delegations/${delegationId}`, payload)
  return data
}

export async function listProfileFieldDefinitions(): Promise<ProfileFieldDefinition[]> {
  const { data } = await http.get<ProfileFieldDefinition[]>('/profile-field-definitions')
  return data
}

export async function createProfileFieldDefinition(
  payload: CreateProfileFieldDefinitionPayload,
): Promise<ProfileFieldDefinition> {
  const { data } = await http.post<ProfileFieldDefinition>('/profile-field-definitions', payload)
  return data
}

export async function updateProfileFieldDefinition(
  definitionId: string,
  payload: UpdateProfileFieldDefinitionPayload,
): Promise<ProfileFieldDefinition> {
  const { data } = await http.patch<ProfileFieldDefinition>(
    `/profile-field-definitions/${definitionId}`,
    payload,
  )
  return data
}

export async function listProfileFieldPermissions(
  definitionId: string,
): Promise<ProfileFieldPermission[]> {
  const { data } = await http.get<ProfileFieldPermission[]>(
    `/profile-field-definitions/${definitionId}/permissions`,
  )
  return data
}

export async function createProfileFieldPermission(
  payload: CreateProfileFieldPermissionPayload,
): Promise<ProfileFieldPermission> {
  const { data } = await http.post<ProfileFieldPermission>('/profile-field-permissions', payload)
  return data
}

export async function updateProfileFieldPermission(
  permissionId: string,
  payload: UpdateProfileFieldPermissionPayload,
): Promise<ProfileFieldPermission> {
  const { data } = await http.patch<ProfileFieldPermission>(
    `/profile-field-permissions/${permissionId}`,
    payload,
  )
  return data
}
