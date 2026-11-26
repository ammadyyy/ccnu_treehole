import { Routes, Route } from 'react-router-dom'
import Navbar from './components/Navbar'
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

export default function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <main className="mx-auto max-w-2xl px-4 py-6">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/post/:id" element={<PostDetail />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/new" element={<NewPost />} />
          <Route path="/me" element={<Me />} />
          <Route path="/me/masks" element={<Masks />} />
          <Route path="/me/settings" element={<Settings />} />
          <Route path="/me/notifications" element={<Notifications />} />
          <Route path="/privacy" element={<Privacy />} />
          <Route path="/admin" element={<AdminHome />} />
          <Route path="/admin/reports" element={<AdminReports />} />
          <Route path="/admin/reports/:id" element={<AdminReportDetail />} />
          <Route path="/admin/admins" element={<AdminAdmins />} />
          <Route path="/admin/audit" element={<AdminAudit />} />
        </Routes>
      </main>
    </div>
  )
}
