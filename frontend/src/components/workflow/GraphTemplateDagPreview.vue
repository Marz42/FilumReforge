<script setup lang="ts">
import { computed } from 'vue'

export interface DagPreviewNode {
  node_key: string
  title: string
}

export interface DagPreviewEdge {
  from_node_key: string
  to_node_key: string
  is_reject_path?: boolean
}

const props = defineProps<{
  nodes: DagPreviewNode[]
  edges: DagPreviewEdge[]
}>()

const NODE_WIDTH = 132
const NODE_HEIGHT = 44
const GAP_X = 28
const GAP_Y = 56
const PADDING = 24

const layout = computed(() => {
  const nodeKeys = props.nodes.map((node) => node.node_key)
  const positions = new Map<string, { x: number; y: number; layer: number }>()
  if (nodeKeys.length === 0) {
    return { positions, width: 320, height: 120, edges: [] as Array<{ from: string; to: string; reject: boolean }> }
  }

  const forwardEdges = props.edges.filter((edge) => !edge.is_reject_path)
  const incoming = new Map<string, number>(nodeKeys.map((key) => [key, 0]))
  const outgoing = new Map<string, string[]>(nodeKeys.map((key) => [key, []]))
  for (const edge of forwardEdges) {
    if (!incoming.has(edge.from_node_key) || !incoming.has(edge.to_node_key)) {
      continue
    }
    incoming.set(edge.to_node_key, (incoming.get(edge.to_node_key) ?? 0) + 1)
    outgoing.get(edge.from_node_key)?.push(edge.to_node_key)
  }

  const entryKeys = nodeKeys.filter((key) => (incoming.get(key) ?? 0) === 0)
  const layers = new Map<string, number>()
  const queue = [...entryKeys]
  for (const key of queue) {
    layers.set(key, 0)
  }
  while (queue.length > 0) {
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

  let fallbackLayer = Math.max(0, ...layers.values()) + 1
  for (const key of nodeKeys) {
    if (!layers.has(key)) {
      layers.set(key, fallbackLayer)
      fallbackLayer += 1
    }
  }

  const layerBuckets = new Map<number, string[]>()
  for (const key of nodeKeys) {
    const layer = layers.get(key) ?? 0
    const bucket = layerBuckets.get(layer) ?? []
    bucket.push(key)
    layerBuckets.set(layer, bucket)
  }

  let maxWidth = 0
  for (const [layer, keys] of layerBuckets.entries()) {
    keys.sort()
    keys.forEach((key, index) => {
      const x = PADDING + index * (NODE_WIDTH + GAP_X)
      const y = PADDING + layer * (NODE_HEIGHT + GAP_Y)
      positions.set(key, { x, y, layer })
      maxWidth = Math.max(maxWidth, x + NODE_WIDTH)
    })
  }

  const maxLayer = Math.max(...layers.values())
  const height = PADDING * 2 + (maxLayer + 1) * NODE_HEIGHT + maxLayer * GAP_Y
  const edges = props.edges
    .filter(
      (edge) => positions.has(edge.from_node_key) && positions.has(edge.to_node_key),
    )
    .map((edge) => ({
      from: edge.from_node_key,
      to: edge.to_node_key,
      reject: Boolean(edge.is_reject_path),
    }))

  return {
    positions,
    width: Math.max(maxWidth + PADDING, 320),
    height,
    edges,
  }
})

function nodeCenter(key: string, edge: 'start' | 'end'): { x: number; y: number } | null {
  const pos = layout.value.positions.get(key)
  if (!pos) {
    return null
  }
  const x = pos.x + NODE_WIDTH / 2
  const y = edge === 'start' ? pos.y + NODE_HEIGHT : pos.y
  return { x, y }
}

function edgePath(fromKey: string, toKey: string): string {
  const start = nodeCenter(fromKey, 'start')
  const end = nodeCenter(toKey, 'end')
  if (!start || !end) {
    return ''
  }
  const midY = (start.y + end.y) / 2
  return `M ${start.x} ${start.y} C ${start.x} ${midY}, ${end.x} ${midY}, ${end.x} ${end.y}`
}
</script>

<template>
  <div class="dag-preview" data-testid="graph-template-dag-preview">
    <p v-if="nodes.length === 0" class="dag-preview__empty">暂无节点，保存节点或添加边后将在此显示拓扑。</p>
    <div
      v-else
      class="dag-preview__stage"
      :style="{ width: `${layout.width}px`, height: `${layout.height}px` }"
    >
      <svg :width="layout.width" :height="layout.height" class="dag-preview__canvas">
        <path
          v-for="(edge, index) in layout.edges"
          :key="`${edge.from}-${edge.to}-${index}`"
          :d="edgePath(edge.from, edge.to)"
          class="dag-preview__edge"
          :class="{ 'dag-preview__edge--reject': edge.reject }"
        />
      </svg>
      <div
        v-for="node in nodes"
        :key="node.node_key"
        class="dag-preview__node"
        :style="{
          left: `${layout.positions.get(node.node_key)?.x ?? 0}px`,
          top: `${layout.positions.get(node.node_key)?.y ?? 0}px`,
          width: `${NODE_WIDTH}px`,
          height: `${NODE_HEIGHT}px`,
        }"
      >
        <strong>{{ node.node_key }}</strong>
        <span>{{ node.title }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dag-preview {
  overflow: auto;
  width: 100%;
  min-height: 120px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  background: var(--el-fill-color-blank);
}

.dag-preview__empty {
  margin: 0;
  padding: 32px 16px;
  text-align: center;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.dag-preview__stage {
  position: relative;
  flex-shrink: 0;
}

.dag-preview__canvas {
  position: absolute;
  top: 0;
  left: 0;
  pointer-events: none;
}

.dag-preview__edge {
  fill: none;
  stroke: var(--el-color-primary);
  stroke-width: 1.5;
}

.dag-preview__edge--reject {
  stroke: var(--el-color-danger);
  stroke-dasharray: 6 4;
}

.dag-preview__node {
  position: absolute;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 2px;
  padding: 6px 8px;
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  background: var(--el-bg-color);
  font-size: 11px;
}

.dag-preview__node strong {
  font-size: 12px;
}
</style>
