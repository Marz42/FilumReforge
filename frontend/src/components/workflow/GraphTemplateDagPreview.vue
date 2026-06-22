<script setup lang="ts">
import { computed, ref } from 'vue'

import { assignForwardLayers } from '@/utils/graphTemplateTopology'

export interface DagPreviewNode {
  node_key: string
  title: string
  sort_order?: number
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

type LayoutDirection = 'horizontal' | 'vertical'

const direction = ref<LayoutDirection>('horizontal')

const NODE_WIDTH = 140
const NODE_HEIGHT = 48
const GAP_LAYER = 72
const GAP_SIBLING = 28
const PADDING = 36
const REJECT_LANE_STEP = 22

const layout = computed(() => {
  const nodeKeys = props.nodes.map((node) => node.node_key)
  const positions = new Map<string, { x: number; y: number; layer: number }>()
  if (nodeKeys.length === 0) {
    return {
      positions,
      width: 320,
      height: 160,
      forwardEdges: [] as Array<{ from: string; to: string; index: number }>,
      rejectEdges: [] as Array<{ from: string; to: string; index: number }>,
      hasForwardCycle: false,
    }
  }

  const forwardEdgesRaw = props.edges.filter((edge) => !edge.is_reject_path)
  const rejectEdgesRaw = props.edges.filter((edge) => edge.is_reject_path)

  const sortOrderByKey = new Map(
    props.nodes.map((node, index) => [node.node_key, node.sort_order ?? index + 1]),
  )
  const { layers, hasForwardCycle: forwardCycleDetected } = assignForwardLayers(
    nodeKeys,
    forwardEdgesRaw,
    sortOrderByKey,
  )

  const layerBuckets = new Map<number, string[]>()
  for (const key of nodeKeys) {
    const layer = layers.get(key) ?? 0
    const bucket = layerBuckets.get(layer) ?? []
    bucket.push(key)
    layerBuckets.set(layer, bucket)
  }

  let maxX = PADDING
  let maxY = PADDING

  if (direction.value === 'horizontal') {
    for (const [layer, keys] of layerBuckets.entries()) {
      keys.sort()
      keys.forEach((key, index) => {
        const x = PADDING + layer * (NODE_WIDTH + GAP_LAYER)
        const y = PADDING + index * (NODE_HEIGHT + GAP_SIBLING)
        positions.set(key, { x, y, layer })
        maxX = Math.max(maxX, x + NODE_WIDTH)
        maxY = Math.max(maxY, y + NODE_HEIGHT)
      })
    }
  } else {
    for (const [layer, keys] of layerBuckets.entries()) {
      keys.sort()
      keys.forEach((key, index) => {
        const x = PADDING + index * (NODE_WIDTH + GAP_SIBLING)
        const y = PADDING + layer * (NODE_HEIGHT + GAP_LAYER)
        positions.set(key, { x, y, layer })
        maxX = Math.max(maxX, x + NODE_WIDTH)
        maxY = Math.max(maxY, y + NODE_HEIGHT)
      })
    }
  }

  const rejectLaneReserve = rejectEdgesRaw.length > 0 ? REJECT_LANE_STEP * rejectEdgesRaw.length + 28 : 0
  const width = Math.max(maxX + PADDING, 320)
  const height = Math.max(maxY + PADDING + rejectLaneReserve, 160)

  const forwardEdges = forwardEdgesRaw
    .filter((edge) => positions.has(edge.from_node_key) && positions.has(edge.to_node_key))
    .map((edge, index) => ({ from: edge.from_node_key, to: edge.to_node_key, index }))

  const rejectEdges = rejectEdgesRaw
    .filter((edge) => positions.has(edge.from_node_key) && positions.has(edge.to_node_key))
    .map((edge, index) => ({ from: edge.from_node_key, to: edge.to_node_key, index }))

  return { positions, width, height, forwardEdges, rejectEdges, maxX, maxY, hasForwardCycle: forwardCycleDetected }
})

type NodeBox = {
  left: number
  top: number
  right: number
  bottom: number
  cx: number
  cy: number
}

function nodeBox(key: string): NodeBox | null {
  const pos = layout.value.positions.get(key)
  if (!pos) {
    return null
  }
  return {
    left: pos.x,
    top: pos.y,
    right: pos.x + NODE_WIDTH,
    bottom: pos.y + NODE_HEIGHT,
    cx: pos.x + NODE_WIDTH / 2,
    cy: pos.y + NODE_HEIGHT / 2,
  }
}

/** Point on a rectangle border; align is 0..1 along that edge (0.5 = center). */
function borderPoint(
  box: NodeBox,
  side: 'top' | 'right' | 'bottom' | 'left',
  align = 0.5,
): { x: number; y: number } {
  const t = Math.min(1, Math.max(0, align))
  switch (side) {
    case 'top':
      return { x: box.left + (box.right - box.left) * t, y: box.top }
    case 'right':
      return { x: box.right, y: box.top + (box.bottom - box.top) * t }
    case 'bottom':
      return { x: box.left + (box.right - box.left) * t, y: box.bottom }
    case 'left':
      return { x: box.left, y: box.top + (box.bottom - box.top) * t }
  }
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

function roundedOrthogonalPath(points: Array<{ x: number; y: number }>, radius: number): string {
  if (points.length === 0) {
    return ''
  }
  if (points.length === 1) {
    return `M ${points[0].x} ${points[0].y}`
  }

  let path = `M ${points[0].x} ${points[0].y}`

  for (let i = 1; i < points.length; i++) {
    const prev = points[i - 1]
    const curr = points[i]
    const next = points[i + 1]

    if (!next) {
      path += ` L ${curr.x} ${curr.y}`
      break
    }

    const dx1 = curr.x - prev.x
    const dy1 = curr.y - prev.y
    const dx2 = next.x - curr.x
    const dy2 = next.y - curr.y
    const len1 = Math.hypot(dx1, dy1)
    const len2 = Math.hypot(dx2, dy2)
    if (len1 === 0 || len2 === 0) {
      path += ` L ${curr.x} ${curr.y}`
      continue
    }

    const cornerR = Math.min(radius, len1 / 2, len2 / 2)
    const n1x = dx1 / len1
    const n1y = dy1 / len1
    const n2x = dx2 / len2
    const n2y = dy2 / len2

    path += [
      ` L ${curr.x - n1x * cornerR} ${curr.y - n1y * cornerR}`,
      ` Q ${curr.x} ${curr.y} ${curr.x + n2x * cornerR} ${curr.y + n2y * cornerR}`,
    ].join('')
  }

  return path
}

function forwardEdgePath(fromKey: string, toKey: string): string {
  const from = nodeBox(fromKey)
  const to = nodeBox(toKey)
  if (!from || !to) {
    return ''
  }

  if (direction.value === 'horizontal') {
    const startX = from.right
    const startY = from.cy
    const endX = to.left - 1
    const endY = to.cy
    const midX = (startX + endX) / 2
    return `M ${startX} ${startY} C ${midX} ${startY}, ${midX} ${endY}, ${endX} ${endY}`
  }

  const startX = from.cx
  const startY = from.bottom
  const endX = to.cx
  const endY = to.top - 1
  const midY = (startY + endY) / 2
  return `M ${startX} ${startY} C ${startX} ${midY}, ${endX} ${midY}, ${endX} ${endY}`
}

function rejectEdgePath(fromKey: string, toKey: string, laneIndex: number): string {
  const from = nodeBox(fromKey)
  const to = nodeBox(toKey)
  if (!from || !to) {
    return ''
  }

  const laneOffset = 16 + laneIndex * REJECT_LANE_STEP
  const cornerRadius = 6

  if (direction.value === 'horizontal') {
    const laneY = layout.value.maxY + laneOffset
    const exit = borderPoint(from, 'bottom')
    const entryAlign = clamp((exit.x - to.left) / (to.right - to.left), 0.15, 0.85)
    const entry = borderPoint(to, 'bottom', entryAlign)

    if (Math.abs(exit.x - entry.x) < 1) {
      return `M ${exit.x} ${exit.y} L ${entry.x} ${entry.y}`
    }

    return roundedOrthogonalPath(
      [
        { x: exit.x, y: exit.y },
        { x: exit.x, y: laneY },
        { x: entry.x, y: laneY },
        { x: entry.x, y: entry.y },
      ],
      cornerRadius,
    )
  }

  const laneX = layout.value.maxX + laneOffset
  const exit = borderPoint(from, 'right')
  const entryAlign = clamp((exit.y - to.top) / (to.bottom - to.top), 0.15, 0.85)
  const entry = borderPoint(to, 'right', entryAlign)

  if (Math.abs(exit.y - entry.y) < 1) {
    return `M ${exit.x} ${exit.y} L ${entry.x} ${entry.y}`
  }

  return roundedOrthogonalPath(
    [
      { x: exit.x, y: exit.y },
      { x: laneX, y: exit.y },
      { x: laneX, y: entry.y },
      { x: entry.x, y: entry.y },
    ],
    cornerRadius,
  )
}
</script>

<template>
  <div class="dag-preview" data-testid="graph-template-dag-preview">
    <header class="dag-preview__header">
      <div class="dag-preview__legend" aria-label="流程图图例">
        <span class="dag-preview__legend-title">图例</span>
        <span class="dag-preview__legend-item">
          <svg class="dag-preview__legend-swatch" width="28" height="10" aria-hidden="true">
            <line x1="0" y1="5" x2="28" y2="5" class="dag-preview__legend-line--forward" marker-end="url(#dag-legend-forward)" />
          </svg>
          正常流转
        </span>
        <span class="dag-preview__legend-item">
          <svg class="dag-preview__legend-swatch" width="28" height="10" aria-hidden="true">
            <line x1="0" y1="5" x2="28" y2="5" class="dag-preview__legend-line--reject" marker-end="url(#dag-legend-reject)" />
          </svg>
          审核 / 打回
        </span>
        <span class="dag-preview__legend-item">
          <span class="dag-preview__legend-node" aria-hidden="true" />
          流程节点（键 · 标题）
        </span>
      </div>
      <el-radio-group v-model="direction" size="small" data-testid="dag-preview-direction">
        <el-radio-button value="horizontal">横向</el-radio-button>
        <el-radio-button value="vertical">纵向</el-radio-button>
      </el-radio-group>
    </header>

    <p
      v-if="layout.hasForwardCycle"
      class="dag-preview__cycle-warn"
      role="alert"
      data-testid="dag-preview-cycle-warning"
    >
      forward 边存在环路，预览已降级为按节点顺序排列。请为反向边勾选「打回」，或删除造成环路的正常流转边。
    </p>

    <p v-if="nodes.length === 0" class="dag-preview__empty">暂无节点，保存节点或添加边后将在此显示拓扑。</p>
    <div v-else class="dag-preview__scroll">
      <div
        class="dag-preview__stage"
        :style="{ width: `${layout.width}px`, height: `${layout.height}px` }"
      >
        <svg :width="layout.width" :height="layout.height" class="dag-preview__canvas">
          <defs>
            <marker
              id="dag-forward-arrow"
              markerWidth="8"
              markerHeight="8"
              refX="8"
              refY="4"
              orient="auto"
              markerUnits="userSpaceOnUse"
            >
              <path d="M0,0 L8,4 L0,8 Z" class="dag-preview__marker--forward" />
            </marker>
            <marker
              id="dag-reject-arrow"
              markerWidth="8"
              markerHeight="8"
              refX="8"
              refY="4"
              orient="auto"
              markerUnits="userSpaceOnUse"
            >
              <path d="M0,0 L8,4 L0,8 Z" class="dag-preview__marker--reject" />
            </marker>
            <marker id="dag-legend-forward" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
              <path d="M0,0 L6,3 L0,6 Z" class="dag-preview__marker--forward" />
            </marker>
            <marker id="dag-legend-reject" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
              <path d="M0,0 L6,3 L0,6 Z" class="dag-preview__marker--reject" />
            </marker>
          </defs>

          <path
            v-for="edge in layout.forwardEdges"
            :key="`f-${edge.from}-${edge.to}-${edge.index}`"
            :d="forwardEdgePath(edge.from, edge.to)"
            class="dag-preview__edge dag-preview__edge--forward"
            marker-end="url(#dag-forward-arrow)"
          />
          <path
            v-for="edge in layout.rejectEdges"
            :key="`r-${edge.from}-${edge.to}-${edge.index}`"
            :d="rejectEdgePath(edge.from, edge.to, edge.index)"
            class="dag-preview__edge dag-preview__edge--reject"
            marker-end="url(#dag-reject-arrow)"
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
  </div>
</template>

<style scoped>
.dag-preview {
  width: 100%;
  min-height: 120px;
  overflow: hidden;
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  background: var(--el-fill-color-blank);
}

.dag-preview__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding: 10px 12px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  background: var(--el-fill-color-light);
  border-radius: 8px 8px 0 0;
}

.dag-preview__legend {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px 16px;
  font-size: 12px;
  color: var(--el-text-color-regular);
}

.dag-preview__legend-title {
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.dag-preview__legend-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.dag-preview__legend-swatch {
  flex-shrink: 0;
}

.dag-preview__legend-line--forward {
  stroke: var(--el-color-primary);
  stroke-width: 2;
}

.dag-preview__legend-line--reject {
  stroke: var(--el-color-warning);
  stroke-width: 2;
  stroke-dasharray: 5 4;
}

.dag-preview__legend-node {
  display: inline-block;
  width: 22px;
  height: 14px;
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
  background: var(--el-bg-color);
}

.dag-preview__empty {
  margin: 0;
  padding: 32px 16px;
  text-align: center;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.dag-preview__cycle-warn {
  margin: 0;
  padding: 8px 12px;
  border-bottom: 1px solid var(--el-color-warning-light-5);
  background: var(--el-color-warning-light-9);
  font-size: 12px;
  line-height: 1.5;
  color: var(--el-color-warning-dark-2);
}

.dag-preview__scroll {
  overflow-x: auto;
  overflow-y: hidden;
  max-width: 100%;
  padding: 12px;
}

.dag-preview__stage {
  position: relative;
  flex-shrink: 0;
  margin: 0 auto;
}

.dag-preview__canvas {
  position: absolute;
  top: 0;
  left: 0;
  z-index: 2;
  pointer-events: none;
  overflow: visible;
}

.dag-preview__edge {
  fill: none;
  stroke-width: 2;
}

.dag-preview__edge--forward {
  stroke: var(--el-color-primary);
}

.dag-preview__edge--reject {
  stroke: var(--el-color-warning);
  stroke-dasharray: 7 5;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.dag-preview__marker--forward {
  fill: var(--el-color-primary);
}

.dag-preview__marker--reject {
  fill: var(--el-color-warning);
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
  box-shadow: 0 1px 2px rgb(0 0 0 / 6%);
  font-size: 11px;
  z-index: 1;
}

.dag-preview__node strong {
  font-size: 12px;
  line-height: 1.2;
}

.dag-preview__node span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--el-text-color-secondary);
}
</style>
