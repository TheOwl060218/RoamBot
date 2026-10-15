import { defineConfig } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const frontend = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(frontend, '..')
const python = path.resolve(root, '../../.venv/Scripts/python.exe')
export default defineConfig({
  testDir: './e2e', testMatch: 'business-commands.spec.ts', fullyParallel: false, workers: 1,
  outputDir: '../test-results/commands-browser',
  reporter: [['line'], ['json', { outputFile: '../test-results/commands-browser.json' }]],
  use: { baseURL: 'http://127.0.0.1:5191', channel: 'msedge', trace: 'retain-on-failure' },
  webServer: [
    { command: JSON.stringify(python) + ' scripts/command_mock_server.py', cwd: root, port: 8031,
      reuseExistingServer: false, env: { ...process.env, COMMAND_TEST_PORT: '8031',
        ROAMBOT_PROVIDER_MODE: 'mock', ROAMBOT_DATA_DIR: path.join(root, '.playwright-data/commands-' + process.pid) } },
    { command: JSON.stringify(process.execPath) + ' node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5191 --strictPort',
      cwd: frontend, port: 5191, reuseExistingServer: false,
      env: { ...process.env, ROAMBOT_E2E_API_TARGET: 'http://127.0.0.1:8031' } },
  ],
  projects: [
    { name: 'desktop', use: { viewport: { width: 1440, height: 900 } } },
    { name: 'mobile', use: { viewport: { width: 390, height: 844 } } },
    { name: 'reduced-motion', use: { viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' } },
  ],
})
