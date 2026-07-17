import { createBrowserRouter, Outlet, RouterProvider } from 'react-router-dom'

import { PlaceholderPage } from '../pages/PlaceholderPage'
import { AppShell } from './AppShell'

const router = createBrowserRouter([
  {
    element: (
      <AppShell>
        <Outlet />
      </AppShell>
    ),
    children: [
      { index: true, element: <PlaceholderPage title="推荐" /> },
      { path: 'favorites', element: <PlaceholderPage title="收藏" /> },
      { path: 'history', element: <PlaceholderPage title="历史" /> },
      { path: 'share/:token', element: <PlaceholderPage title="分享快照" /> },
    ],
  },
])

export function AppRouter() {
  return <RouterProvider router={router} />
}
