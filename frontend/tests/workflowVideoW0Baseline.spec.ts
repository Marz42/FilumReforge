import { describe, expect, it } from 'vitest'

import {
  VIDEO_V1_RUN_KINDS,
  VIDEO_V1_TEMPLATE_CODES,
} from '@/constants/workflowVideoV1'

describe('workflow video v1 W0 baseline constants', () => {
  it('defines batch and production template codes from the v2 plan', () => {
    expect(VIDEO_V1_TEMPLATE_CODES.topicMeetingBatch).toBe('topic_meeting_batch_v1')
    expect(VIDEO_V1_TEMPLATE_CODES.videoProductionPerTopic).toBe('video_production_per_topic_v1')
  })

  it('defines run kinds for batch vs per-topic production', () => {
    expect(VIDEO_V1_RUN_KINDS.batch).toBe('batch')
    expect(VIDEO_V1_RUN_KINDS.production).toBe('production')
  })
})
