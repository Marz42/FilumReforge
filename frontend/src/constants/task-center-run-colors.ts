const RUN_COLOR_PALETTE = [
  '#3b82f6',
  '#8b5cf6',
  '#06b6d4',
  '#10b981',
  '#f59e0b',
  '#ef4444',
  '#ec4899',
  '#6366f1',
] as const

function hashRunLabel(label: string): number {
  let hash = 0
  for (let index = 0; index < label.length; index += 1) {
    hash = (hash * 31 + label.charCodeAt(index)) >>> 0
  }
  return hash
}

export function resolveRunColor(runLabel: string): string {
  const normalized = runLabel.trim() || '—'
  const index = hashRunLabel(normalized) % RUN_COLOR_PALETTE.length
  return RUN_COLOR_PALETTE[index] ?? RUN_COLOR_PALETTE[0]
}
