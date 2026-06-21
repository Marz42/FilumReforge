import type { Page } from '@playwright/test'

import { fulfillJson, getApiPath, isExactApiPath } from './mock-api-helpers'

export const designerTemplateId = 'tpl-designer-1'

const designerDetail = {
  id: designerTemplateId,
  code: 'topic_meeting_batch_v1',
  base_code: 'topic_meeting_batch_v1',
  name: '选题会（批次）',
  description: 'Playwright 设计器 mock',
  status: 'draft',
  version: 2,
  run_kind: 'batch',
  config: {
    aggregate_mode: 'batch',
    launch_schema: {
      fields: [{ key: 'theme', label: '征集主题', type: 'text', required: true }],
    },
    participant_policies: { copywriters: { type: 'department_members' } },
  },
  has_instances: false,
  structure_locked: false,
  nodes: [
    {
      id: 'node-n1',
      node_key: 'N1_PROPOSE',
      title: '征集',
      sort_order: 1,
      assignment_mode: 'single',
      join_mode: 'all',
      config: { kind: 'multi_instance', expand_from: 'copywriters' },
    },
    {
      id: 'node-n2',
      node_key: 'N2_AGGREGATE',
      title: '汇总',
      sort_order: 2,
      assignment_mode: 'single',
      join_mode: 'all',
      config: { kind: 'aggregate' },
    },
  ],
  edges: [
    {
      from_node_key: 'N1_PROPOSE',
      to_node_key: 'N2_AGGREGATE',
      is_reject_path: false,
      condition: {},
      priority: 0,
    },
  ],
}

export async function installGraphTemplateDesignerMock(page: Page): Promise<void> {
  await page.route('**/api/v1/workflow-graph/templates/**', async (route) => {
    const request = route.request()
    const apiPath = getApiPath(request.url())
    const base = `/workflow-graph/templates/${designerTemplateId}`

    if (request.method() === 'GET' && isExactApiPath(apiPath, `${base}/designer`)) {
      await fulfillJson(route, designerDetail)
      return
    }

    if (request.method() === 'PUT' && isExactApiPath(apiPath, `${base}/draft`)) {
      const body = request.postDataJSON() as { name?: string }
      if (body.name) {
        designerDetail.name = body.name
      }
      await fulfillJson(route, designerDetail)
      return
    }

    if (request.method() === 'GET' && isExactApiPath(apiPath, `${base}/validate`)) {
      await fulfillJson(route, { valid: true, errors: [] })
      return
    }

    if (request.method() === 'POST' && isExactApiPath(apiPath, `${base}/dry-run`)) {
      await fulfillJson(route, {
        valid: true,
        errors: [],
        schema_snapshot: { aggregate_mode: 'batch', nodes: {} },
        normalized_inputs: { theme: 'E2E' },
        entry_node_keys: ['N1_PROPOSE'],
        participant_previews: [{ policy_ref: 'copywriters', mode: 'subset', user_count: 3, user_ids: [] }],
      })
      return
    }

    if (request.method() === 'GET' && isExactApiPath(apiPath, `${base}/export`)) {
      await fulfillJson(route, {
        template: designerDetail,
        exported_at: '2026-06-21T00:00:00Z',
      })
      return
    }

    if (request.method() === 'POST' && isExactApiPath(apiPath, `${base}/versions`)) {
      designerDetail.version += 1
      await fulfillJson(route, designerDetail)
      return
    }

    if (request.method() === 'PATCH' && isExactApiPath(apiPath, `${base}/status`)) {
      designerDetail.status = 'active'
      await fulfillJson(route, designerDetail)
      return
    }

    await route.fallback()
  })
}
