import fs from 'node:fs'
import path from 'node:path'

export type UatRow = {
  id: string
  phase: string
  result: 'PASS' | 'FAIL' | 'SKIP'
  note: string
}

const rows: UatRow[] = []

export function uatRow(row: UatRow): void {
  rows.push(row)
}

export function getUatRows(): UatRow[] {
  return [...rows]
}

export function getUatRunDir(): string {
  return process.env.VERIFY_RUN_DIR ?? path.join(process.cwd(), 'verification-runs', 'workflow-video-uat-fallback')
}

export function getUatShotDir(): string {
  const dir = path.join(getUatRunDir(), 'screenshots')
  fs.mkdirSync(dir, { recursive: true })
  return dir
}

export function uatShot(name: string): string {
  return path.join(getUatShotDir(), name)
}

export function writeUatReport(extraSections: string[] = []): void {
  const runDir = getUatRunDir()
  const shotDir = getUatShotDir()
  const runId = process.env.VERIFY_RUN_ID ?? 'unknown'
  const lines: string[] = [
    '# 视频工作流 v1 协同 UAT 报告（Playwright）',
    '',
    '**对照**：[workflow-video-v1-collaborative-uat-guide.md](../../memory-bank/knowledge/manuals/workflow-video-v1-collaborative-uat-guide.md)',
    '',
    `- **输出目录**：\`verification-runs/workflow-video-uat-${runId}\``,
    `- **前端基址**：\`http://127.0.0.1:4173\`（Vite dev + mock API）`,
    `- **生成时间**：${new Date().toISOString()}`,
    '',
    '## 结果汇总',
    '',
    '| 步骤 ID | 阶段 | 结果 | 说明 |',
    '| --- | --- | --- | --- |',
  ]

  for (const row of rows) {
    lines.push(
      `| ${row.id} | ${row.phase} | ${row.result} | ${row.note.replace(/\|/g, '\\|').replace(/\n/g, ' ')} |`,
    )
  }

  for (const section of extraSections) {
    lines.push('', section)
  }

  lines.push('', '## 截图索引', '')
  const files = fs.existsSync(shotDir) ? fs.readdirSync(shotDir).filter((file) => file.endsWith('.png')) : []
  for (const file of files.sort()) {
    lines.push(`- ./screenshots/${file}`)
  }

  lines.push(
    '',
    '## HTML 报告',
    '',
    'Playwright 另生成 `playwright-report/index.html`（在 `frontend/` 目录下执行时）。',
    '',
    '```bash',
    'cd frontend',
    'npm run test:e2e:workflow-video-uat',
    'npx playwright show-report',
    '```',
    '',
  )

  fs.mkdirSync(runDir, { recursive: true })
  fs.writeFileSync(path.join(runDir, 'report.md'), lines.join('\n'), 'utf8')
}
