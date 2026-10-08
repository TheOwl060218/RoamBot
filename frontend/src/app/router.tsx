import { createBrowserRouter, Outlet, RouterProvider } from 'react-router-dom'

import { SearchPage } from '../pages/SearchPage'
import { HomePage } from '../pages/HomePage'
import { FavoritesPage } from '../pages/FavoritesPage'
import { HistoryPage } from '../pages/HistoryPage'
import { HistoryDetailPage } from '../pages/HistoryDetailPage'
import { RequireAuth } from '../features/auth/RequireAuth'
import { PublicSharePage } from '../features/shares/PublicSharePage'
import { AppShell } from './AppShell'
import { PlansPage, PlanDetailPage, JoinPlanPage } from '../features/plans/PlanPages'

const router = createBrowserRouter([
  { path: '/', element: <HomePage /> },
  {
    element: (
      <AppShell>
        <Outlet />
      </AppShell>
    ),
    children: [
      { path: 'recommend', element: <SearchPage /> },
      { path: 'favorites', element: <RequireAuth><FavoritesPage /></RequireAuth> },
      { path: 'history', element: <RequireAuth><HistoryPage /></RequireAuth> },
      { path: 'history/:historyId', element: <RequireAuth><HistoryDetailPage /></RequireAuth> },
      { path: 'share/:token', element: <PublicSharePage /> },
      { path: 'plans', element: <RequireAuth><PlansPage /></RequireAuth> },
      { path: 'plans/:planId', element: <RequireAuth><PlanDetailPage /></RequireAuth> },
      { path: 'join/:inviteToken', element: <JoinPlanPage /> },
    ],
  },
])

export function AppRouter() {
  return <RouterProvider router={router} />
}
