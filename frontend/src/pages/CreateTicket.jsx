import { useState } from 'react'
import { createTicket, classifyTicket } from '../services/api'
import './CreateTicket.css'

function CreateTicket() {
  const [formData, setFormData] = useState({
    customer: '',
    message: ''
  })
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(false)

  const handleChange = (e) => {
    const { name, value } = e.target
    setFormData(prev => ({
      ...prev,
      [name]: value
    }))
    setError(null)
    setResult(null)
    setSuccess(false)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    setSuccess(false)
    setResult(null)

    if (!formData.customer.trim() || !formData.message.trim()) {
      setError('Please fill in all required fields')
      return
    }

    setLoading(true)

    try {
      const response = await createTicket(formData)
      setResult(response)
      setSuccess(true)
      setFormData({ customer: '', message: '' })
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to create ticket')
    } finally {
      setLoading(false)
    }
  }

  const handleClassify = async () => {
    if (!formData.message.trim()) {
      setError('Please enter a message to classify')
      return
    }

    setError(null)
    setResult(null)
    setLoading(true)

    try {
      const response = await classifyTicket(formData.message)
      setResult(response)
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to classify ticket')
    } finally {
      setLoading(false)
    }
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

  return (
    <div className="create-ticket">
      <div className="card">
        <h2>Create New Ticket</h2>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="customer">Customer Name *</label>
            <input
              type="text"
              id="customer"
              name="customer"
              value={formData.customer}
              onChange={handleChange}
              placeholder="Enter customer name"
              required
              disabled={loading}
            />
          </div>

          <div className="form-group">
            <label htmlFor="message">Ticket Message *</label>
            <textarea
              id="message"
              name="message"
              value={formData.message}
              onChange={handleChange}
              placeholder="Describe your issue or inquiry..."
              required
              disabled={loading}
            />
          </div>

          {error && (
            <div className="alert alert-error">
              {error}
            </div>
          )}

          {success && (
            <div className="alert alert-success">
              Ticket created successfully!
            </div>
          )}

          <div className="form-actions">
            <button
              type="button"
              onClick={handleClassify}
              className="btn btn-secondary"
              disabled={loading || !formData.message.trim()}
            >
              Preview Classification
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={loading}
            >
              {loading ? 'Submitting...' : 'Submit Ticket'}
            </button>
          </div>
        </form>

        {result && (
          <div className="ticket-result">
            <h3>Classification Result</h3>
            <div className="result-item">
              <span className="result-label">Category:</span>
              <span className={`badge ${getCategoryBadgeClass(result.category)}`}>
                {result.category}
              </span>
            </div>
            <div className="result-item">
              <span className="result-label">Assigned Team:</span>
              <span className="result-value">{result.assignedTeam}</span>
            </div>
            {result.confidence && (
              <div className="result-item">
                <span className="result-label">Confidence:</span>
                <span className="result-value">
                  {(parseFloat(result.confidence) * 100).toFixed(1)}%
                </span>
              </div>
            )}
            {result.status && (
              <div className="result-item">
                <span className="result-label">Status:</span>
                <span className={`badge ${getStatusBadgeClass(result.status)}`}>
                  {result.status}
                </span>
              </div>
            )}
            {result.id && (
              <div className="result-item">
                <span className="result-label">Ticket ID:</span>
                <span className="result-value">#{result.id}</span>
              </div>
            )}
            {result.error && (
              <div className="alert alert-error" style={{ marginTop: '1rem' }}>
                Warning: {result.error}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default CreateTicket

