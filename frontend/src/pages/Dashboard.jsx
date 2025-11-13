import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { getCurrentUser, logout, getToken } from '../services/auth'
import './Dashboard.css'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function Dashboard() {
  const [tickets, setTickets] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const navigate = useNavigate()
  const user = getCurrentUser()

  const fetchTickets = async () => {
    const token = getToken()
    if (!token) {
      navigate('/login')
      return
    }

    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams()
      if (searchTerm) params.append('search', searchTerm)
      if (categoryFilter) params.append('category', categoryFilter)
      if (statusFilter) params.append('status_filter', statusFilter)

      const response = await axios.get(
        `${API_BASE_URL}/api/ticket?${params.toString()}`,
        {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        }
      )
      setTickets(response.data)
    } catch (err) {
      if (err.response?.status === 401) {
        navigate('/login')
      } else {
        setError(err.response?.data?.detail || err.message || 'Failed to fetch tickets')
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    // Small delay to ensure token is loaded from localStorage
    const timer = setTimeout(() => {
      fetchTickets()
    }, 50)
    return () => clearTimeout(timer)
  }, [searchTerm, categoryFilter, statusFilter])

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  const getCategoryBadgeClass = (category) => {
    const categoryLower = category?.toLowerCase() ?? ''
    if (categoryLower.includes('billing')) return 'badge-billing'
    if (categoryLower.includes('technical')) return 'badge-technical'
    if (categoryLower.includes('delivery')) return 'badge-delivery'
    return 'badge-general'
  }

  const getStatusBadgeClass = (status) => {
    const statusLower = status?.toLowerCase() ?? ''
    if (statusLower === 'pending') return 'badge-pending'
    if (statusLower === 'in_progress') return 'badge-in_progress'
    if (statusLower === 'resolved') return 'badge-resolved'
    if (statusLower === 'closed') return 'badge-closed'
    return 'badge-pending'
  }

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A'
    try {
      const date = new Date(dateString)
      return date.toLocaleString()
    } catch {
      return dateString
    }
  }

  if (loading && tickets.length === 0) {
    return (
      <div className="card">
        <div className="loading">Loading tickets...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="card">
        <div className="alert alert-error">{error}</div>
        <button onClick={fetchTickets} className="btn btn-primary">
          Retry
        </button>
      </div>
    )
  }

  return (
    <div className="dashboard">
      <div className="dashboard-header-main">
        <div className="header-content">
          <h1>🎫 Admin Dashboard</h1>
          <div className="user-info">
            <span>Welcome, {user?.full_name || user?.username}!</span>
            <button onClick={handleLogout} className="btn btn-secondary btn-sm">
              Logout
            </button>
          </div>
        </div>
      </div>

      <div className="dashboard-container">
        <div className="card">
          <div className="dashboard-header">
            <h2>Ticket Management</h2>
            <button onClick={fetchTickets} className="btn btn-primary" disabled={loading}>
              {loading ? 'Refreshing...' : 'Refresh'}
            </button>
          </div>

          <div className="filters-section">
            <div className="filter-group">
              <input
                type="text"
                placeholder="🔍 Search by customer or message..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="search-input"
              />
            </div>
            <div className="filter-group">
              <select
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
                className="filter-select"
              >
                <option value="">All Categories</option>
                <option value="billing">Billing</option>
                <option value="technical">Technical</option>
                <option value="delivery">Delivery</option>
                <option value="general">General</option>
              </select>
            </div>
            <div className="filter-group">
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="filter-select"
              >
                <option value="">All Status</option>
                <option value="pending">Pending</option>
                <option value="in_progress">In Progress</option>
                <option value="resolved">Resolved</option>
                <option value="closed">Closed</option>
              </select>
            </div>
            {(searchTerm || categoryFilter || statusFilter) && (
              <button
                onClick={() => {
                  setSearchTerm('')
                  setCategoryFilter('')
                  setStatusFilter('')
                }}
                className="btn btn-secondary"
              >
                Clear Filters
              </button>
            )}
          </div>

          {tickets.length === 0 ? (
            <div className="empty-state">
              <p>No tickets found</p>
              {(searchTerm || categoryFilter || statusFilter) ? (
                <p>Try adjusting your filters</p>
              ) : (
                <p>Tickets will appear here once created</p>
              )}
            </div>
          ) : (
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Customer</th>
                  <th>Message</th>
                  <th>Category</th>
                  <th>Assigned Team</th>
                  <th>Status</th>
                  <th>Confidence</th>
                  <th>Created At</th>
                </tr>
              </thead>
              <tbody>
                {tickets.map((ticket) => (
                  <tr key={ticket.id}>
                    <td>#{ticket.id}</td>
                    <td>{ticket.customer}</td>
                    <td className="message-cell">
                      {ticket.message.length > 100
                        ? `${ticket.message.substring(0, 100)}...`
                        : ticket.message}
                    </td>
                    <td>
                      <span className={`badge ${getCategoryBadgeClass(ticket.category)}`}>
                        {ticket.category}
                      </span>
                    </td>
                    <td>{ticket.assignedTeam}</td>
                    <td>
                      <span className={`badge ${getStatusBadgeClass(ticket.status)}`}>
                        {ticket.status}
                      </span>
                    </td>
                    <td>
                      {ticket.confidence
                        ? `${(parseFloat(ticket.confidence) * 100).toFixed(1)}%`
                        : 'N/A'}
                    </td>
                    <td>{formatDate(ticket.createdAt)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default Dashboard

