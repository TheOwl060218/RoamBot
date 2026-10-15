import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { AppRouter } from './app/router'
import { AuthProvider } from './features/auth/AuthProvider'
import './styles/tokens.css'
import './styles/app.css'
import './styles/forms.css'
import './styles/results.css'
import './styles/location-map.css'
import './styles/auth.css'
import './styles/personal.css'
import './styles/plans.css'
import './styles/home.css'
import './styles/commands.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AuthProvider>
      <AppRouter />
    </AuthProvider>
  </StrictMode>,
)
