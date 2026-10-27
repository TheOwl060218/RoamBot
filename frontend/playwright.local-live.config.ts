import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e', testMatch: 'keyboard-live.spec.ts', workers: 1, retries: 0,
  outputDir: '../test-results/keyboard-live',
  reporter: [['line'], ['json', { outputFile: '../test-results/keyboard-live.json' }]],
  use: { baseURL: process.env.ROAMBOT_LIVE_BASE_URL ?? 'http://localhost:8033',
    channel: 'msedge', viewport: { width: 1440, height: 900 }, trace: 'off' },
})
