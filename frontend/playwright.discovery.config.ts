import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e', testMatch: 'discovery.spec.ts', workers: 1, retries: 0,
  outputDir: '../test-results/discovery-browser',
  reporter: [['line'], ['json', { outputFile: '../test-results/discovery-browser.json' }]],
  use: { baseURL: 'http://127.0.0.1:5192', channel: 'msedge', trace: 'retain-on-failure' },
  webServer: { command: JSON.stringify(process.execPath) + ' node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5192 --strictPort', port: 5192, reuseExistingServer: false },
  projects: [
    { name: 'wide', use: { viewport: { width: 1920, height: 1080 } } },
    { name: 'desktop', use: { viewport: { width: 1440, height: 900 } } },
    { name: 'mobile', use: { viewport: { width: 390, height: 844 } } },
    { name: 'reduced-motion', use: { viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' } },
  ],
})
