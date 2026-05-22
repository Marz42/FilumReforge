/**
 * Video workflow v1 template codes and run kinds (W0 baseline).
 * Authoritative plan: memory-bank/plans/workflow-video-v1-implementation-plan.md
 */

export const VIDEO_V1_TEMPLATE_CODES = {
  topicMeetingBatch: 'topic_meeting_batch_v1',
  videoProductionPerTopic: 'video_production_per_topic_v1',
} as const

export const VIDEO_V1_RUN_KINDS = {
  batch: 'batch',
  production: 'production',
} as const

export type VideoV1TemplateCode =
  (typeof VIDEO_V1_TEMPLATE_CODES)[keyof typeof VIDEO_V1_TEMPLATE_CODES]

export type VideoV1RunKind = (typeof VIDEO_V1_RUN_KINDS)[keyof typeof VIDEO_V1_RUN_KINDS]
