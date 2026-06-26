import { describe, expect, it } from 'vitest'

import { resolveUserPoolKey } from '@/utils/workflowVideoSchema'

describe('resolveUserPoolKey', () => {
  it('uses pool_key from schema snapshot when present', () => {
    const context = {
      schema_snapshot: {
        nodes: {
          N7_EDIT_ASSIGN: {
            capture_schema: {
              columns: [
                { key: 'edit_assignee_id', type: 'user', pool_key: 'post_production' },
              ],
            },
          },
        },
      },
    }
    expect(resolveUserPoolKey(context, 'N7_EDIT_ASSIGN')).toBe('post_production')
  })

  it('defaults N7 edit_assignee_id to post_production when snapshot lacks pool_key', () => {
    const context = {
      schema_snapshot: {
        nodes: {
          N7_EDIT_ASSIGN: {
            capture_schema: {
              columns: [{ key: 'edit_assignee_id', type: 'user', required: true }],
            },
          },
        },
      },
    }
    expect(resolveUserPoolKey(context, 'N7_EDIT_ASSIGN')).toBe('post_production')
  })

  it('returns empty string when no user column and no node default', () => {
    expect(resolveUserPoolKey(undefined, 'N1_PROPOSE')).toBe('')
  })
})
