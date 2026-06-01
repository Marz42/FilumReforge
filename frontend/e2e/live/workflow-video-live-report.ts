import fs from 'node:fs'
import path from 'node:path'

export type LiveRow = {
  id: string
  phase: string
  actor: string
  result: 'PASS' | 'FAIL' | 'SKIP'
  note: string
}

const rows: LiveRow[] = []

export function liveRow(row: LiveRow): void {
  rows.push(row)
}

export function getLiveRunDir(): string {
  return (
    process.env.VERIFY_RUN_DIR ??
    path.join(process.cwd(), 'verification-runs', 'workflow-video-live-fallback')
  )
}

export function liveShot(name: string): string {
  const dir = path.join(getLiveRunDir(), 'screenshots')
  fs.mkdirSync(dir, { recursive: true })
  return path.join(dir, name)
}

export function writeLiveReport(meta: {
  runTag: string
  baseURL: string
  password: string
  mode?: 'live' | 'mock'
}): void {
  const runDir = getLiveRunDir()
  const shotDir = path.join(runDir, 'screenshots')
  const runId = process.env.VERIFY_RUN_ID ?? 'unknown'
  const mode = meta.mode ?? 'live'
  const modeLabel = mode === 'mock' ? 'Mock（API 路由模拟，无 Docker）' : 'Live（真实 Docker 栈 + 种子）'
  const lines: string[] = [
    '# 视频制作全流程 · 多账号 E2E 报告',
    '',
    '**指南**：[workflow-video-v1-multi-account-e2e-guide.md](../../memory-bank/handbooks/workflow-video-v1-multi-account-e2e-guide.md)',
    '',
    `- **执行模式**：${modeLabel}`,
    `- **Run 标记**：\`${meta.runTag}\``,
    `- **基址**：${meta.baseURL}`,
    `- **Demo 密码**：\`${meta.password}\``,
    `- **输出目录**：\`verification-runs/workflow-video-live-${runId}\``,
    `- **生成时间**：${new Date().toISOString()}`,
    '',
    '## 结果汇总',
    '',
    '| 步骤 | 阶段 | 账号 | 结果 | 说明 |',
    '| --- | --- | --- | --- | --- |',
  ]

  for (const row of rows) {
    lines.push(
      `| ${row.id} | ${row.phase} | ${row.actor} | ${row.result} | ${row.note.replace(/\|/g, '\\|').replace(/\n/g, ' ')} |`,
    )
  }

  const pass = rows.filter((row) => row.result === 'PASS').length
  const fail = rows.filter((row) => row.result === 'FAIL').length
  lines.push('', `**合计**：${rows.length} 步，PASS ${pass}，FAIL ${fail}。`, '', '## 截图索引', '')
  const files = fs.existsSync(shotDir) ? fs.readdirSync(shotDir).filter((f) => f.endsWith('.png')) : []
  for (const file of files.sort()) {
    lines.push(`- ./screenshots/${file}`)
  }

  fs.mkdirSync(runDir, { recursive: true })
  fs.writeFileSync(path.join(runDir, 'report.md'), lines.join('\n'), 'utf8')
}
