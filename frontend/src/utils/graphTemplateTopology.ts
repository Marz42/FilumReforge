export interface GraphTemplateEdgeInput {
  from_node_key: string
  to_node_key: string
  is_reject_path?: boolean
}

export interface GraphTemplateNodeInput {
  node_key: string
  sort_order?: number
}

export type EdgeTopologyIssueLevel = 'error' | 'warning'

export interface EdgeTopologyIssue {
  level: EdgeTopologyIssueLevel
  message: string
  edgeIndex?: number
}

export function buildForwardAdjacency(
  nodeKeys: string[],
  edges: GraphTemplateEdgeInput[],
): Map<string, string[]> {
  const outgoing = new Map<string, string[]>(nodeKeys.map((key) => [key, []]))
  for (const edge of edges) {
    if (edge.is_reject_path) {
      continue
    }
    if (!outgoing.has(edge.from_node_key) || !outgoing.has(edge.to_node_key)) {
      continue
    }
    if (edge.from_node_key === edge.to_node_key) {
      continue
    }
    outgoing.get(edge.from_node_key)?.push(edge.to_node_key)
  }
  return outgoing
}

export function hasForwardCycle(nodeKeys: string[], edges: GraphTemplateEdgeInput[]): boolean {
  const outgoing = buildForwardAdjacency(nodeKeys, edges)
  const visiting = new Set<string>()
  const visited = new Set<string>()

  function dfs(nodeKey: string): boolean {
    if (visiting.has(nodeKey)) {
      return true
    }
    if (visited.has(nodeKey)) {
      return false
    }
    visiting.add(nodeKey)
    for (const downstream of outgoing.get(nodeKey) ?? []) {
      if (dfs(downstream)) {
        return true
      }
    }
    visiting.delete(nodeKey)
    visited.add(nodeKey)
    return false
  }

  for (const nodeKey of nodeKeys) {
    if (dfs(nodeKey)) {
      return true
    }
  }
  return false
}

export function assignForwardLayers(
  nodeKeys: string[],
  edges: GraphTemplateEdgeInput[],
  sortOrderByKey: Map<string, number>,
): { layers: Map<string, number>; hasForwardCycle: boolean } {
  const layers = new Map<string, number>()
  if (nodeKeys.length === 0) {
    return { layers, hasForwardCycle: false }
  }

  if (hasForwardCycle(nodeKeys, edges)) {
    const sorted = [...nodeKeys].sort((left, right) => {
      const leftOrder = sortOrderByKey.get(left) ?? 0
      const rightOrder = sortOrderByKey.get(right) ?? 0
      if (leftOrder !== rightOrder) {
        return leftOrder - rightOrder
      }
      return left.localeCompare(right)
    })
    sorted.forEach((key, index) => layers.set(key, index))
    return { layers, hasForwardCycle: true }
  }

  const incoming = new Map<string, number>(nodeKeys.map((key) => [key, 0]))
  const outgoing = buildForwardAdjacency(nodeKeys, edges)
  for (const targets of outgoing.values()) {
    for (const target of targets) {
      incoming.set(target, (incoming.get(target) ?? 0) + 1)
    }
  }

  const queue = nodeKeys.filter((key) => (incoming.get(key) ?? 0) === 0)
  for (const key of queue) {
    layers.set(key, 0)
  }

  const maxIterations = nodeKeys.length * Math.max(nodeKeys.length, 1) + nodeKeys.length
  let iterations = 0
  while (queue.length > 0 && iterations < maxIterations) {
    iterations += 1
    const current = queue.shift()!
    const layer = layers.get(current) ?? 0
    for (const downstream of outgoing.get(current) ?? []) {
      const nextLayer = layer + 1
      if ((layers.get(downstream) ?? -1) < nextLayer) {
        layers.set(downstream, nextLayer)
        queue.push(downstream)
      }
    }
  }

  let fallbackLayer = Math.max(0, ...Array.from(layers.values())) + 1
  for (const key of nodeKeys) {
    if (!layers.has(key)) {
      layers.set(key, fallbackLayer)
      fallbackLayer += 1
    }
  }

  return { layers, hasForwardCycle: false }
}

export function analyzeEdgeTopology(
  nodes: GraphTemplateNodeInput[],
  edges: GraphTemplateEdgeInput[],
): EdgeTopologyIssue[] {
  const issues: EdgeTopologyIssue[] = []
  const nodeKeys = nodes.map((node) => node.node_key)
  const nodeKeySet = new Set(nodeKeys)
  const sortOrderByKey = new Map(nodes.map((node) => [node.node_key, node.sort_order ?? 0]))

  edges.forEach((edge, index) => {
    if (edge.is_reject_path) {
      return
    }
    const fromOrder = sortOrderByKey.get(edge.from_node_key)
    const toOrder = sortOrderByKey.get(edge.to_node_key)
    if (fromOrder === undefined || toOrder === undefined) {
      return
    }
    if (fromOrder > toOrder) {
      issues.push({
        level: 'warning',
        message: `边 ${edge.from_node_key} → ${edge.to_node_key}：反向流转未勾选「打回」，请勾选或删除该边。`,
        edgeIndex: index,
      })
    }
  })

  const forwardEdges = edges.filter((edge) => {
    if (edge.is_reject_path) {
      return false
    }
    return nodeKeySet.has(edge.from_node_key) && nodeKeySet.has(edge.to_node_key)
  })

  if (nodeKeys.length > 0 && hasForwardCycle(nodeKeys, forwardEdges)) {
    issues.push({
      level: 'error',
      message: 'forward 边存在环路：正常流转须构成无环 DAG，请为反向边勾选「打回」或删除造成环路的边。',
    })
  }

  return issues
}
