import type { OverviewAnnouncement, OverviewBoardCard, OverviewSnapshot } from '@/types/api'
import { http } from './http'

export interface CreateBoardCardPayload {
  scope_department_id: string | null
  title: string
  content_md: string
}

export interface CreateAnnouncementPayload {
  publisher_department_id: string
  title: string
  content_md: string
}

export async function getOverview(): Promise<OverviewSnapshot> {
  const { data } = await http.get<OverviewSnapshot>('/overview')
  return data
}

export async function createBoardCard(payload: CreateBoardCardPayload): Promise<OverviewBoardCard> {
  const { data } = await http.post<OverviewBoardCard>('/board-cards', payload)
  return data
}

export async function archiveBoardCard(boardCardId: string): Promise<void> {
  await http.post(`/board-cards/${boardCardId}/archive`)
}

export async function createAnnouncement(
  payload: CreateAnnouncementPayload,
): Promise<OverviewAnnouncement> {
  const { data } = await http.post<OverviewAnnouncement>('/announcements', payload)
  return data
}

export async function withdrawAnnouncement(announcementId: string): Promise<void> {
  await http.post(`/announcements/${announcementId}/withdraw`)
}
