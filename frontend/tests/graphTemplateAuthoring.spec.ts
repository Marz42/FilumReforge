import { describe, expect, it } from 'vitest'

import {
  buildContextSchema,
  buildLaunchSchema,
  buildRoutingRules,
  parseContextSchema,
  parseLaunchSchema,
  parseRoutingRules,
} from '@/utils/graphTemplateAuthoring'

describe('graph template structured authoring helpers', () => {
  it('round-trips common launch fields while preserving advanced top-level keys', () => {
    const raw = {
      title: '发起任务',
      fields: [{ key: 'theme', label: '主题', type: 'text', required: true }],
    }
    const parsed = parseLaunchSchema(raw)
    expect(parsed.structuredCompatible).toBe(true)
    expect(buildLaunchSchema(raw, parsed.rows)).toEqual(raw)
  })

  it('supports JSON Schema and legacy flat context shapes', () => {
    const jsonSchema = {
      type: 'object',
      properties: { amount: { type: 'number', description: '预算' } },
      required: ['amount'],
    }
    const parsedJsonSchema = parseContextSchema(jsonSchema)
    expect(parsedJsonSchema.rows[0]).toMatchObject({ key: 'amount', required: true })
    expect(buildContextSchema(parsedJsonSchema.rows, parsedJsonSchema.style)).toEqual(jsonSchema)

    const flat = { amount: { type: 'number', required: true } }
    const parsedFlat = parseContextSchema(flat)
    expect(parsedFlat.style).toBe('flat')
    expect(buildContextSchema(parsedFlat.rows, parsedFlat.style)).toEqual(flat)
  })

  it('round-trips common IF/ELSE routing rules and flags composite rules as advanced', () => {
    const rules = [
      { condition: { field: 'amount', operator: 'gt', value: 1 }, target_node_key: 'STEP_B' },
      { else: true, target_node_key: 'STEP_C' },
    ]
    const parsed = parseRoutingRules(rules)
    expect(parsed.structuredCompatible).toBe(true)
    expect(buildRoutingRules(parsed.rows)).toEqual(rules)

    expect(
      parseRoutingRules([
        {
          condition: { all: [{ field: 'amount', operator: 'gt', value: 1 }] },
          target_node_key: 'STEP_B',
        },
      ]).structuredCompatible,
    ).toBe(false)
  })
})
