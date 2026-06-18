export function resolveTaskRunLabel(
  title: string,
  metadata: Record<string, unknown> = {},
  graphRunLabel?: string | null,
): string {
  if (typeof metadata.run_label === 'string' && metadata.run_label.trim()) {
    return metadata.run_label.trim()
  }
  if (graphRunLabel?.trim()) {
    return graphRunLabel.trim()
  }
  const separatorIndex = title.lastIndexOf(' / ')
  if (separatorIndex >= 0) {
    const suffix = title.slice(separatorIndex + 3).trim()
    if (suffix) {
      return suffix
    }
  }
  return '—'
}
