import '@testing-library/jest-dom/vitest'

import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

afterEach(() => {
  cleanup()
  localStorage.clear()
  sessionStorage.clear()
  // Native history is persistent session state, independent of MemoryRouter.
  // Give each test a fresh page while leaving its Back/Forward assertions intact.
  window.history.replaceState({}, '', window.location.href)
})
