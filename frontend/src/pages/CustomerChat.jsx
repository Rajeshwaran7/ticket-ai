import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { getCurrentUser, getToken } from '../services/auth'
import './CustomerChat.css'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function CustomerChat() {
  const [message, setMessage] = useState('')
  const [screenshot, setScreenshot] = useState(null)
  const [previewUrl, setPreviewUrl] = useState(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const fileInputRef = useRef(null)
  const navigate = useNavigate()
  const user = getCurrentUser()

  const handleFileChange = (e) => {
    const file = e.target.files?.[0]
    if (file) {
      if (file.size > 10 * 1024 * 1024) {
        setError('File size must be less than 10MB')
        return
      }
      
      if (!file.type.startsWith('image/')) {
        setError('Please upload an image file')
        return
      }

      setScreenshot(file)
      setPreviewUrl(URL.createObjectURL(file))
      setError(null)
    }
  }

  const handleRemoveScreenshot = () => {
    setScreenshot(null)
    setPreviewUrl(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    
    if (!message.trim()) {
      setError('Please enter a message')
      return
    }

    setLoading(true)
    setError(null)
    setResult(null)

    try {
      // Get fresh token right before making the request
      const token = getToken()
      if (!token) {
        setError('Authentication required. Please login again.')
        navigate('/login')
        return
      }

      console.log('Submitting ticket with token:', token.substring(0, 20) + '...')

      const formData = new FormData()
      formData.append('message', message)
      formData.append('customer', user?.full_name || user?.username || 'Customer')
      
      if (screenshot) {
        formData.append('screenshot', screenshot)
      }

      const response = await axios.post(
        `${API_BASE_URL}/api/ticket/chat`,
        formData,
        {
          headers: {
            'Authorization': `Bearer ${token}`
            // Don't set Content-Type - let browser set it with boundary for multipart
          }
        }
      )

      setResult(response.data)
      setMessage('')
      handleRemoveScreenshot()
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to submit ticket. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="customer-chat">
      <div className="chat-container">
        <div className="chat-main">
          <div className="welcome-message">
            <h2>👋 How can we help you today?</h2>
            <p>Describe your issue below. You can also upload a screenshot to help us understand better.</p>
          </div>

          <form onSubmit={handleSubmit} className="chat-form">
            <div className="form-group">
              <label htmlFor="message">Your Message *</label>
              <textarea
                id="message"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="Describe your issue or question..."
                rows={6}
                disabled={loading}
                required
              />
            </div>

            <div className="form-group">
              <label>Screenshot (Optional)</label>
              <div className="file-upload-area">
                {!previewUrl ? (
                  <div className="upload-prompt">
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="image/*"
                      onChange={handleFileChange}
                      disabled={loading}
                      id="screenshot-input"
                    />
                    <label htmlFor="screenshot-input" className="upload-label">
                      <span className="upload-icon">📷</span>
                      <span>Click to upload screenshot</span>
                      <span className="upload-hint">PNG, JPG up to 10MB</span>
                    </label>
                  </div>
                ) : (
                  <div className="preview-container">
                    <img src={previewUrl} alt="Screenshot preview" className="screenshot-preview" />
                    <button
                      type="button"
                      onClick={handleRemoveScreenshot}
                      className="btn-remove"
                      disabled={loading}
                    >
                      ✕ Remove
                    </button>
                  </div>
                )}
              </div>
            </div>

            {error && (
              <div className="alert alert-error">
                {error}
              </div>
            )}

            <button
              type="submit"
              className="btn btn-primary btn-large"
              disabled={loading || !message.trim()}
            >
              {loading ? '📤 Sending...' : '📤 Send Ticket'}
            </button>
          </form>

          {result && (
            <div className="result-card">
              <h3>✅ Ticket Submitted Successfully!</h3>
              <div className="result-details">
                <div className="result-item">
                  <span className="label">Ticket ID:</span>
                  <span className="value">#{result.id}</span>
                </div>
                <div className="result-item">
                  <span className="label">Category:</span>
                  <span className={`badge badge-${result.category}`}>
                    {result.category}
                  </span>
                </div>
                <div className="result-item">
                  <span className="label">Assigned To:</span>
                  <span className="value">{result.assignedTeam}</span>
                </div>
                <div className="result-item">
                  <span className="label">Status:</span>
                  <span className={`badge badge-${result.status}`}>
                    {result.status}
                  </span>
                </div>
                {result.confidence && (
                  <div className="result-item">
                    <span className="label">Confidence:</span>
                    <span className="value">
                      {(parseFloat(result.confidence) * 100).toFixed(1)}%
                    </span>
                  </div>
                )}
              </div>
              <p className="result-message">
                Your ticket has been routed to the {result.assignedTeam} team. 
                We'll get back to you as soon as possible!
              </p>
            </div>
          )}
        </div>

        <div className="chat-sidebar">
          <div className="sidebar-card">
            <h3>📋 Quick Tips</h3>
            <ul>
              <li>Be specific about your issue</li>
              <li>Include error messages if any</li>
              <li>Screenshots help us understand better</li>
              <li>Check your email for updates</li>
            </ul>
          </div>

          <div className="sidebar-card">
            <h3>📊 Categories</h3>
            <div className="category-list">
              <div className="category-item">
                <span className="badge badge-billing">Billing</span>
                <span>Payment & invoices</span>
              </div>
              <div className="category-item">
                <span className="badge badge-technical">Technical</span>
                <span>Bugs & errors</span>
              </div>
              <div className="category-item">
                <span className="badge badge-delivery">Delivery</span>
                <span>Shipping & tracking</span>
              </div>
              <div className="category-item">
                <span className="badge badge-general">General</span>
                <span>Other inquiries</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default CustomerChat

