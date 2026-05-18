import type { ReportCenterSnapshot, ReportRecord, ReportDirection } from '@/types/api'

import { http } from './http'

export interface CreateReportPayload {
  direction: ReportDirection
  target_user_id: string
  title: string
  content_md: string
  workflow_definition_id?: string | null
  attachment_ids?: string[] | null
}

export interface ReportActionPayload {
  action: string
  note?: string | null
}

export async function getReportCenterSnapshot(): Promise<ReportCenterSnapshot> {
  const { data } = await http.get<ReportCenterSnapshot>('/report-center')
  return data
}

export async function createReport(payload: CreateReportPayload): Promise<ReportRecord> {
  const { data } = await http.post<ReportRecord>('/report-center/reports', payload)
  return data
}

export async function actReport(reportId: string, payload: ReportActionPayload): Promise<ReportRecord> {
  const { data } = await http.post<ReportRecord>(`/report-center/reports/${reportId}/actions`, payload)
  return data
}
