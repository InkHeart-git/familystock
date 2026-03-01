import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './store/authStore'
import Layout from './components/Layout'
import Home from './pages/Home'
import Dashboard from './pages/Dashboard'
import StockSearch from './pages/StockSearch'
import StockDetail from './pages/StockDetail'
import Watchlist from './pages/Watchlist'
import AIAnalysis from './pages/AIAnalysis'
import FamilyGroup from './pages/FamilyGroup'
import Login from './pages/Login'
import Register from './pages/Register'
import Profile from './pages/Profile'

// 路由守卫组件
function ProtectedRoute({ children }) {
  const { isAuthenticated } = useAuthStore()
  return isAuthenticated ? children : <Navigate to="/login" replace />
}

function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route
        path="/app/*"
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="search" element={<StockSearch />} />
        <Route path="stock/:symbol" element={<StockDetail />} />
        <Route path="watchlist" element={<Watchlist />} />
        <Route path="analysis" element={<AIAnalysis />} />
        <Route path="family" element={<FamilyGroup />} />
        <Route path="profile" element={<Profile />} />
      </Route>
    </Routes>
  )
}

export default App
