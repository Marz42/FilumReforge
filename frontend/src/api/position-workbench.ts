import type {
  Position,
  PositionAssignmentType,
  ReportingLineType,
  UserStatus,
} from '@/types/api'
import { http } from './http'

export interface PositionImpactCounts {
  assignee_count: number
  primary_count: number
  secondary_count: number
  department_count: number
  active_reporting_line_count: number
}

export interface PositionWorkbenchCatalogItem extends Position {
  impact: PositionImpactCounts
}

export interface PositionWorkbenchCatalog {
  summary: {
    total_positions: number
    active_positions: number
    total_assignees: number
  }
  positions: PositionWorkbenchCatalogItem[]
  as_of: string
}

export interface PositionAssigneeUserSummary {
  user_id: string
  email: string
  real_name: string | null
  employee_no: string | null
  status: UserStatus
  department_id: string | null
  department_name: string | null
}

export interface PositionAssignmentDetail {
  id: string
  user: PositionAssigneeUserSummary
  department_id: string
  department_name: string | null
  assignment_type: PositionAssignmentType
  is_primary: boolean
  starts_at: string
  ends_at: string | null
  is_effective: boolean
}

export interface PositionReportingLineDetail {
  id: string
  user: PositionAssigneeUserSummary
  manager_user_id: string
  manager_label: string | null
  department_id: string | null
  department_name: string | null
  line_type: ReportingLineType
  is_primary: boolean
  starts_at: string
  ends_at: string | null
  is_effective: boolean
}

export interface PositionWorkbenchDetail {
  position: Position
  impact: PositionImpactCounts
  assignments: PositionAssignmentDetail[]
  reporting_lines: PositionReportingLineDetail[]
  effective_range: {
    earliest_starts_at: string | null
    latest_ends_at: string | null
    open_ended_assignment_count: number
  }
  as_of: string
}

export async function getPositionWorkbenchCatalog(asOf?: string): Promise<PositionWorkbenchCatalog> {
  const { data } = await http.get<PositionWorkbenchCatalog>('/positions/workbench', {
    params: asOf ? { as_of: asOf } : undefined,
  })
  return data
}

export async function getPositionWorkbenchDetail(
  positionId: string,
  asOf?: string,
): Promise<PositionWorkbenchDetail> {
  const { data } = await http.get<PositionWorkbenchDetail>(`/positions/${positionId}/workbench`, {
    params: asOf ? { as_of: asOf } : undefined,
  })
  return data
}
