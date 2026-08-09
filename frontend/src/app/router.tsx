import { createBrowserRouter, Outlet, RouterProvider } from 'react-router-dom'

import { SearchPage } from '../pages/SearchPage'
import { FavoritesPage } from '../pages/FavoritesPage'
import { HistoryPage } from '../pages/HistoryPage'
import { HistoryDetailPage } from '../pages/HistoryDetailPage'
import { RequireAuth } from '../features/auth/RequireAuth'
import { PublicSharePage } from '../features/shares/PublicSharePage'
import { AppShell } from './AppShell'

const router = createBrowserRouter([
  {
    element: (
      <AppShell>
        <Outlet />
      </AppShell>
    ),
    children: [
      { index: true, element: <SearchPage /> },
      { path: 'favorites', element: <RequireAuth><FavoritesPage /></RequireAuth> },
      { path: 'history', element: <RequireAuth><HistoryPage /></RequireAuth> },
      { path: 'history/:historyId', element: <RequireAuth><HistoryDetailPage /></RequireAuth> },
      { path: 'share/:token', element: <PublicSharePage /> },
    ],
  },
])

export function AppRouter() {
  return <RouterProvider router={router} />
}
