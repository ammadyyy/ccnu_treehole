import { createBrowserRouter } from 'react-router-dom'
import App from './App'
import Home from './pages/Home'
import PostDetail from './pages/PostDetail'
import Login from './pages/Login'
import Register from './pages/Register'
import NewPost from './pages/NewPost'
import Masks from './pages/Masks'
import Me from './pages/Me'
import Settings from './pages/Settings'
import Notifications from './pages/Notifications'
import Privacy from './pages/Privacy'
import AdminHome from './pages/admin/AdminHome'
import AdminReports from './pages/admin/AdminReports'
import AdminReportDetail from './pages/admin/AdminReportDetail'
import AdminAdmins from './pages/admin/AdminAdmins'
import AdminAudit from './pages/admin/AdminAudit'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <App />,
    children: [
      { path: '/', element: <Home /> },
      { path: '/post/:id', element: <PostDetail /> },
      { path: '/login', element: <Login /> },
      { path: '/register', element: <Register /> },
      { path: '/new', element: <NewPost /> },
      { path: '/me', element: <Me /> },
      { path: '/me/masks', element: <Masks /> },
      { path: '/me/settings', element: <Settings /> },
      { path: '/me/notifications', element: <Notifications /> },
      { path: '/privacy', element: <Privacy /> },
      { path: '/admin', element: <AdminHome /> },
      { path: '/admin/reports', element: <AdminReports /> },
      { path: '/admin/reports/:id', element: <AdminReportDetail /> },
      { path: '/admin/admins', element: <AdminAdmins /> },
      { path: '/admin/audit', element: <AdminAudit /> },
    ],
  },
])
