import { defineConfig, devices } from '@playwright/test'

if (process.env.NEXUSMATCH_REAL_E2E !== '1') {
  throw new Error(
    'Real-stack browser tests require the isolated integration runner. Run python backend/scripts/run_real_stack_e2e.py.',
  )
}

export default defineConfig({
  testDir: './tests/integration',
  fullyParallel: false,
  forbidOnly: true,
  retries: 0,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:5174',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    ...devices['Desktop Chrome'],
  },
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1 --port 5174 --strictPort',
    url: 'http://127.0.0.1:5174',
    reuseExistingServer: false,
    timeout: 30_000,
    env: {
      VITE_API_BASE_URL:
        process.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8001/api/v1',
      NEXUSMATCH_REAL_E2E: '1',
    },
  },
})
