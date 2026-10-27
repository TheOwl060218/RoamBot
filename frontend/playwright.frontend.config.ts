import { defineConfig } from '@playwright/test'
const evidence = process.env.FRONTEND_EVIDENCE_TAG ?? (process.env.FRONTEND_PRODUCTION === '1' ? 'production' : 'source')

// Frontend fixtures only: never contact or restart the live acceptance backend.
export default defineConfig({
  testDir: './e2e', testMatch: 'frontend-layers.spec.ts',
  outputDir: `../test-results/frontend-layers-${evidence}`, fullyParallel: false,
  reporter: [['line'], ['json', { outputFile: `../test-results/frontend-layers-${evidence}.json` }]],
  use: { baseURL: 'http://127.0.0.1:5186', channel: 'msedge', trace: 'retain-on-failure' },
  webServer: { command: `"${process.execPath}" node_modules/vite/bin/vite.js ${process.env.FRONTEND_PRODUCTION === '1' ? 'preview ' : ''}--host 127.0.0.1 --port 5186 --strictPort`, port: 5186, reuseExistingServer: false },
})
