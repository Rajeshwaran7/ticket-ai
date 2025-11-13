import { Routes, Route, Navigate } from 'react-router-dom'
import { isAuthenticated, isAdmin, isCustomer } from './services/auth'
import Login from './pages/Login'
import Register from './pages/Register'
import Dashboard from './pages/Dashboard'
import CustomerChat from './pages/CustomerChat'
import CreateTicket from './pages/CreateTicket'
import './App.css'

// Protected Route Component
function ProtectedRoute({ children, requireAdmin = false }) {
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />
  }

  if (requireAdmin && !isAdmin()) {
    return <Navigate to="/customer/chat" replace />
  }

  return children
}

// Redirect authenticated users
function PublicRoute({ children }) {
  if (isAuthenticated()) {
    if (isAdmin()) {
      return <Navigate to="/admin/dashboard" replace />
    }
    return <Navigate to="/customer/chat" replace />
  }
  return children
}

function App() {
  return (
    <Routes>
        {/* Public Routes */}
        <Route
          path="/login"
          element={
            <PublicRoute>
              <Login />
            </PublicRoute>
          }
        />
        <Route
          path="/register"
          element={
            <PublicRoute>
              <Register />
            </PublicRoute>
          }
        />

        {/* Customer Routes */}
        <Route
          path="/customer/chat"
          element={
            <ProtectedRoute>
              <CustomerChat />
            </ProtectedRoute>
          }
        />

        {/* Admin Routes */}
        <Route
          path="/admin/dashboard"
          element={
            <ProtectedRoute requireAdmin={true}>
              <Dashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/create"
          element={
            <ProtectedRoute requireAdmin={true}>
              <CreateTicket />
            </ProtectedRoute>
          }
        />

        {/* Default Route */}
        <Route
          path="/"
          element={
            isAuthenticated() ? (
              isAdmin() ? (
                <Navigate to="/admin/dashboard" replace />
              ) : (
                <Navigate to="/customer/chat" replace />
              )
            ) : (
              <Navigate to="/login" replace />
            )
          }
        />

        {/* 404 Route */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
  )
}

export default App
