import { defineConfig } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const frontendDir = path.dirname(fileURLToPath(import.meta.url))
const rootDir = path.resolve(frontendDir, '..')
const python = process.platform === 'win32'
  ? '.venv\\Scripts\\python.exe'
  : '.venv/bin/python'
const node = JSON.stringify(process.execPath)
const runId = process.env.ROAMBOT_E2E_RUN_ID ?? String(process.pid)
const reuseExistingServer = process.env.PW_REUSE_SERVERS === '1'

export default defineConfig({
  testDir: './e2e',
  outputDir: '../test-results/playwright',
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: [['line']],
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'retain-on-failure',
  },
  webServer: [
    {
      command: `${python} -m uvicorn roambot.main:app --app-dir backend/src --host 127.0.0.1 --port 8000`,
      cwd: rootDir,
      port: 8000,
      reuseExistingServer,
      env: {
        ...process.env,
        ROAMBOT_PROVIDER_MODE: 'mock',
        ROAMBOT_DEMO_MODE: 'true',
        ROAMBOT_SECURE_COOKIES: 'false',
        ROAMBOT_DATA_DIR: path.join(rootDir, '.playwright-data', runId),
      },
    },
    {
      command: `${node} node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5173`,
      cwd: frontendDir,
      port: 5173,
      reuseExistingServer,
    },
  ],
  projects: [
    {
      name: 'desktop-chromium',
      use: { browserName: 'chromium', viewport: { width: 1440, height: 900 } },
    },
    {
      name: 'mobile-chromium',
      use: { browserName: 'chromium', viewport: { width: 390, height: 844 } },
    },
  ],
})
