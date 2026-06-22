import { describe, expect, it } from 'vitest'

import {
  analyzeEdgeTopology,
  assignForwardLayers,
  hasForwardCycle,
} from '@/utils/graphTemplateTopology'

describe('graphTemplateTopology', () => {
  it('detects forward cycle when reverse edge is not marked reject', () => {
    const nodes = [
      { node_key: 'N3', sort_order: 3 },
      { node_key: 'N4', sort_order: 4 },
    ]
    const edges = [
      { from_node_key: 'N3', to_node_key: 'N4', is_reject_path: false },
      { from_node_key: 'N4', to_node_key: 'N3', is_reject_path: false },
    ]

    expect(hasForwardCycle(['N3', 'N4'], edges)).toBe(true)
    const issues = analyzeEdgeTopology(nodes, edges)
    expect(issues.some((item) => item.level === 'error' && item.message.includes('环路'))).toBe(true)
    expect(issues.some((item) => item.level === 'warning')).toBe(true)
  })

  it('does not treat reject edges as forward cycle', () => {
    const edges = [
      { from_node_key: 'N3', to_node_key: 'N4', is_reject_path: false },
      { from_node_key: 'N4', to_node_key: 'N3', is_reject_path: true },
    ]

    expect(hasForwardCycle(['N3', 'N4'], edges)).toBe(false)
  })

  it('assignForwardLayers falls back without infinite loop on cycle', () => {
    const edges = [
      { from_node_key: 'A', to_node_key: 'B', is_reject_path: false },
      { from_node_key: 'B', to_node_key: 'A', is_reject_path: false },
    ]
    const sortOrder = new Map([
      ['A', 1],
      ['B', 2],
    ])

    const { layers, hasForwardCycle: cycleDetected } = assignForwardLayers(['A', 'B'], edges, sortOrder)
    expect(cycleDetected).toBe(true)
    expect(layers.get('A')).toBe(0)
    expect(layers.get('B')).toBe(1)
  })
})
