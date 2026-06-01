import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { setTimeout as delay } from 'node:timers/promises'

const currentFilePath = fileURLToPath(import.meta.url)
const currentDirectory = path.dirname(currentFilePath)
const repoRoot = path.resolve(currentDirectory, '../../..')
const composeFile = path.join(repoRoot, 'infra', 'docker', 'docker-compose.yml')
const composeOverrideFile = path.join(currentDirectory, 'docker-compose.playwright-live.yml')
const composeProjectName = 'filum-playwright-live'

const livePorts = {
  postgres: '35432',
  redis: '36379',
  backend: '38000',
  frontend: '35173',
  http: '38080',
}

const liveEnv = {
  ...process.env,
  POSTGRES_PORT: livePorts.postgres,
  REDIS_PORT: livePorts.redis,
  BACKEND_PORT: livePorts.backend,
  FRONTEND_PORT: livePorts.frontend,
  HTTP_PORT: livePorts.http,
  VITE_API_BASE_URL: `http://127.0.0.1:${livePorts.http}/api/v1`,
  JWT_SECRET_KEY:
    process.env.JWT_SECRET_KEY || 'playwright-live-jwt-secret-for-e2e-automation-2026',
}

export const liveConfig = {
  composeFile,
  composeOverrideFile,
  composeProjectName,
  env: liveEnv,
  baseURL: process.env.PLAYWRIGHT_LIVE_BASE_URL || `http://127.0.0.1:${livePorts.http}`,
  apiURL: `http://127.0.0.1:${livePorts.backend}`,
  adminEmail: 'admin@example.com',
  password: 'FilumPlaywright123!',
}

function runCommand(command, args, options = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd: options.cwd,
      env: options.env,
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true,
    })

    let stdout = ''
    let stderr = ''

    child.stdout.on('data', (chunk) => {
      stdout += chunk.toString()
    })

    child.stderr.on('data', (chunk) => {
      stderr += chunk.toString()
    })

    child.on('error', reject)
    child.on('close', (code) => {
      if (code === 0) {
        resolve({ stdout, stderr })
        return
      }

      reject(
        new Error(
          `${command} ${args.join(' ')} exited with code ${code}\n${stdout}\n${stderr}`,
        ),
      )
    })
  })
}

function composeArgs(...args) {
  return [
    'compose',
    '-p',
    liveConfig.composeProjectName,
    '-f',
    liveConfig.composeFile,
    '-f',
    liveConfig.composeOverrideFile,
    ...args,
  ]
}

export async function runCompose(...args) {
  return runCommand('docker', composeArgs(...args), {
    cwd: repoRoot,
    env: liveConfig.env,
  })
}

export async function waitForURL(url, description, timeoutMs = 240_000) {
  const deadline = Date.now() + timeoutMs
  let lastError = null

  while (Date.now() < deadline) {
    try {
      const response = await fetch(url)
      if (response.ok) {
        return
      }
      lastError = new Error(`${description} returned status ${response.status}`)
    } catch (error) {
      lastError = error
    }
    await delay(2_000)
  }

  throw new Error(`Timed out waiting for ${description}: ${lastError instanceof Error ? lastError.message : String(lastError)}`)
}

export async function startLiveStack() {
  await runCompose('down', '-v', '--remove-orphans')
  await runCompose('up', '--build', '-d', 'postgres', 'redis', 'backend')

  await waitForURL(`${liveConfig.apiURL}/healthz`, 'backend health endpoint')
  await runCompose(
    'exec',
    '-T',
    'backend',
    'python',
    '-m',
    'app.scripts.seed_sample_data',
    '--password',
    liveConfig.password,
  )
  await runCompose(
    'exec',
    '-T',
    'backend',
    'python',
    '-m',
    'app.scripts.seed_workflow_video_templates',
  )
  await runCompose('up', '--build', '-d', 'frontend', 'nginx', 'worker')
  await waitForURL(`${liveConfig.baseURL}/login`, 'frontend login page')
}

export async function stopLiveStack() {
  await runCompose('down', '-v', '--remove-orphans')
}