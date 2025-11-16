import { Link, useLocation, useNavigate } from 'react-router-dom'
import { getCurrentUser, logout, isAdmin, isCustomer } from '../services/auth'
import { useTheme } from '../contexts/ThemeContext'
import './Navbar.css'

/**
 * Modern navigation bar component with role-based menu items.
 * @returns {JSX.Element} Navigation bar component
 */
function Navbar() {
  const location = useLocation()
  const navigate = useNavigate()
  const user = getCurrentUser()
  const { theme, toggleTheme } = useTheme()

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  if (!user) {
    return null
  }

  const isActive = (path) => location.pathname === path

  return (
    <nav className="modern-navbar">
      <div className="navbar-container">
        <div className="navbar-brand">
          <Link to="/" className="brand-link">
            <span className="brand-icon">🎫</span>
            <span className="brand-text">Ticket AI</span>
          </Link>
        </div>

        <div className="navbar-menu">
          {isAdmin() && (
            <>
              <Link
                to="/admin/dashboard"
                className={`nav-link ${isActive('/admin/dashboard') ? 'active' : ''}`}
              >
                <span className="nav-icon">📊</span>
                Dashboard
              </Link>
              <Link
                to="/admin/create"
                className={`nav-link ${isActive('/admin/create') ? 'active' : ''}`}
              >
                <span className="nav-icon">➕</span>
                Create Ticket
              </Link>
            </>
          )}
          
          {isCustomer() && (
            <>
              <Link
                to="/customer/chat"
                className={`nav-link ${isActive('/customer/chat') ? 'active' : ''}`}
              >
                <span className="nav-icon">💬</span>
                Support Chat
              </Link>
              <Link
                to="/customer/ai-agent"
                className={`nav-link ${isActive('/customer/ai-agent') ? 'active' : ''}`}
              >
                <span className="nav-icon">🤖</span>
                AI Agent
              </Link>
            </>
          )}
        </div>

        <div className="navbar-user">
          <button onClick={toggleTheme} className="btn-theme-toggle" title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}>
            {theme === 'dark' ? '☀️' : '🌙'}
          </button>
          <div className="user-info">
            <span className="user-name">{user?.full_name || user?.username}</span>
            <span className="user-role">{isAdmin() ? 'Admin' : 'Customer'}</span>
          </div>
          <button onClick={handleLogout} className="btn-logout">
            <span className="logout-icon">🚪</span>
            Logout
          </button>
        </div>
      </div>
    </nav>
  )
}

export default Navbar

