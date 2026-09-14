import { readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs'
import { gzipSync } from 'node:zlib'
import { join } from 'node:path'

const distAssets = join(process.cwd(), 'dist', 'assets')
const ENTRY_GZIP_BUDGET_KB = Number(process.env.ENTRY_GZIP_BUDGET_KB || '220')

const files = readdirSync(distAssets).filter((name) => name.endsWith('.js'))
const rows = files.map((name) => {
  const path = join(distAssets, name)
  const raw = readFileSync(path)
  const gzip = gzipSync(raw)
  return {
    name,
    rawKb: +(raw.length / 1024).toFixed(2),
    gzipKb: +(gzip.length / 1024).toFixed(2),
  }
})

rows.sort((a, b) => b.gzipKb - a.gzipKb)
const report = {
  measured_at: new Date().toISOString(),
  entry_gzip_budget_kb: ENTRY_GZIP_BUDGET_KB,
  chunks: rows,
}
writeFileSync(join(process.cwd(), 'dist', 'bundle-budget.json'), JSON.stringify(report, null, 2))

const entry = rows.find((row) => row.name.startsWith('index-'))
console.table(rows.slice(0, 12))
if (!entry) {
  console.error('No index-*.js chunk found in dist/assets')
  process.exit(1)
}
console.log(`Entry ${entry.name}: gzip ${entry.gzipKb} kB (budget ${ENTRY_GZIP_BUDGET_KB} kB)`)
if (entry.gzipKb > ENTRY_GZIP_BUDGET_KB) {
  console.error('Bundle budget exceeded')
  process.exit(1)
}
console.log('Bundle budget OK')
