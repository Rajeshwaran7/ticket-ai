import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { getCurrentUser, getToken } from '../services/auth'
import './AIAgent.css'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// Component to format AI messages with ticket summaries
const FormattedMessage = ({ content }) => {
  // Parse ticket summary pattern: "Ticket #X status summary: - Status: ..."
  const ticketSummaryRegex = /Ticket\s+#(\d+)\s+status\s+summary:\s*([\s\S]*?)(?=Would you like|I can|$)/i
  const ticketMatch = content.match(ticketSummaryRegex)
  
  // Split content into parts
  const parts = []
  
  if (ticketMatch) {
    const ticketId = ticketMatch[1]
    const summaryText = ticketMatch[2]
    const beforeTicket = content.substring(0, ticketMatch.index)
    const afterTicket = content.substring(ticketMatch.index + ticketMatch[0].length)
    
    if (beforeTicket.trim()) {
      parts.push({ type: 'text', content: beforeTicket.trim() })
    }
    
    // Parse ticket summary details - handle both multi-line and single-line formats
    const ticketDetails = {}
    
    // First try splitting by " - " (single line format)
    if (summaryText.includes(' - ')) {
      const detailParts = summaryText.split(' - ').filter(part => part.trim())
      detailParts.forEach(part => {
        const trimmed = part.trim()
        if (trimmed.includes(':')) {
          const [key, ...valueParts] = trimmed.split(':')
          const value = valueParts.join(':').trim()
          ticketDetails[key.trim()] = value
        }
      })
    } else {
      // Multi-line format
      const summaryLines = summaryText.split('\n').filter(line => line.trim())
      summaryLines.forEach(line => {
        const trimmed = line.replace(/^-\s*/, '').trim()
        if (trimmed.includes(':')) {
          const [key, ...valueParts] = trimmed.split(':')
          const value = valueParts.join(':').trim()
          ticketDetails[key.trim()] = value
        }
      })
    }
    
    parts.push({ type: 'ticket-summary', ticketId, details: ticketDetails })
    
    if (afterTicket.trim()) {
      parts.push({ type: 'text', content: afterTicket.trim() })
    }
  } else {
    // No ticket summary, just format the text with bullet points
    parts.push({ type: 'text', content })
  }
  
  return (
    <div className="formatted-message">
      {parts.map((part, index) => {
        if (part.type === 'ticket-summary') {
          return (
            <div key={index} className="ticket-summary-card">
              <div className="ticket-summary-header">
                <span className="ticket-icon">🎫</span>
                <span className="ticket-title">Ticket #{part.ticketId} Summary</span>
              </div>
              <div className="ticket-summary-details">
                {Object.entries(part.details).map(([key, value]) => (
                  <div key={key} className="ticket-detail-row">
                    <span className="ticket-detail-label">{key}:</span>
                    <span className="ticket-detail-value">{value}</span>
                  </div>
                ))}
              </div>
            </div>
          )
        } else {
          // Format text with bullet points and line breaks
          const lines = part.content.split('\n')
          return (
            <div key={index} className="message-text-content">
              {lines.map((line, lineIndex) => {
                const trimmed = line.trim()
                if (!trimmed) return <br key={lineIndex} />
                
                // Check for bullet points
                if (trimmed.startsWith('- ')) {
                  return (
                    <div key={lineIndex} className="message-bullet-point">
                      <span className="bullet">•</span>
                      <span>{trimmed.substring(2)}</span>
                    </div>
                  )
                }
                
                // Check for questions/suggestions
                if (trimmed.startsWith('Would you like') || trimmed.startsWith('I can')) {
                  return (
                    <div key={lineIndex} className="message-suggestion">
                      {trimmed}
                    </div>
                  )
                }
                
                return <div key={lineIndex} className="message-line">{trimmed}</div>
              })}
            </div>
          )
        }
      })}
    </div>
  )
}

/**
 * AI Agent chat page with voice input and document upload.
 * @returns {JSX.Element} AI Agent component
 */
function AIAgent() {
  const [messages, setMessages] = useState([])
  const [inputMessage, setInputMessage] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isRecording, setIsRecording] = useState(false)
  const [uploadedDocs, setUploadedDocs] = useState([])
  const [pendingTickets, setPendingTickets] = useState([])
  const [chatSessions, setChatSessions] = useState([])
  const [currentSessionId, setCurrentSessionId] = useState(null)
  const [showHistory, setShowHistory] = useState(true)
  const [currentStatus, setCurrentStatus] = useState(null)
  
  const messagesEndRef = useRef(null)
  const messagesContainerRef = useRef(null)
  const recognitionRef = useRef(null)
  const fileInputRef = useRef(null)
  const navigate = useNavigate()
  const user = getCurrentUser()

  useEffect(() => {
    if (!user) {
      navigate('/login')
      return
    }
    
    fetchPendingTickets()
    fetchChatSessions()
    initializeSpeechRecognition()
    
    // Add welcome message only if no session is loaded
    if (!currentSessionId) {
      setMessages([{
        id: Date.now(),
        role: 'assistant',
        content: "👋 Hello! I'm your AI ticket assistant. I can help you understand your pending tickets and answer questions about them. You can also upload documents or use voice input!",
        timestamp: new Date()
      }])
    }
  }, [])

  useEffect(() => {
    if (currentSessionId) {
      loadSessionMessages(currentSessionId)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentSessionId])

  useEffect(() => {
    // Scroll to bottom when messages change
    setTimeout(() => {
      scrollToBottom()
    }, 100)
  }, [messages])

  useEffect(() => {
    // Scroll to bottom when status changes
    if (currentStatus) {
      setTimeout(() => {
        scrollToBottom()
      }, 50)
    }
  }, [currentStatus])

  /**
   * Scroll to bottom of messages.
   */
  const scrollToBottom = () => {
    // Use requestAnimationFrame to ensure DOM is updated
    requestAnimationFrame(() => {
      if (messagesContainerRef.current) {
        const container = messagesContainerRef.current
        const targetScroll = container.scrollHeight - container.clientHeight
        
        // Smooth scroll using requestAnimationFrame
        const smoothScroll = () => {
          const currentScroll = container.scrollTop
          const distance = targetScroll - currentScroll
          
          if (Math.abs(distance) > 1) {
            container.scrollTop = currentScroll + distance * 0.3
            requestAnimationFrame(smoothScroll)
          } else {
            container.scrollTop = targetScroll
          }
        }
        
        smoothScroll()
      }
      
      // Also use scrollIntoView as fallback
      if (messagesEndRef.current) {
        messagesEndRef.current.scrollIntoView({ behavior: 'smooth', block: 'end' })
      }
    })
  }

  /**
   * Initialize Web Speech API for voice input.
   */
  const initializeSpeechRecognition = () => {
    if (typeof window !== 'undefined') {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
      if (SpeechRecognition) {
        recognitionRef.current = new SpeechRecognition()
        recognitionRef.current.continuous = false
        recognitionRef.current.interimResults = false
        recognitionRef.current.lang = 'en-US'

        recognitionRef.current.onresult = (event) => {
          const transcript = event.results[0]?.[0]?.transcript
          if (transcript) {
            setInputMessage(transcript)
          }
          setIsRecording(false)
        }

        recognitionRef.current.onerror = () => {
          setIsRecording(false)
        }

        recognitionRef.current.onend = () => {
          setIsRecording(false)
        }
      }
    }
  }

  /**
   * Fetch customer's pending tickets.
   */
  const fetchPendingTickets = async () => {
    try {
      const token = getToken()
      if (!token) return

      const response = await axios.get(
        `${API_BASE_URL}/api/ticket/pending`,
        {
          headers: { 'Authorization': `Bearer ${token}` }
        }
      )
      setPendingTickets(response.data)
    } catch (error) {
      console.error('Failed to fetch pending tickets:', error)
    }
  }

  /**
   * Fetch all chat sessions.
   */
  const fetchChatSessions = async () => {
    try {
      const token = getToken()
      if (!token) return

      const response = await axios.get(
        `${API_BASE_URL}/api/ai-agent/sessions`,
        {
          headers: { 'Authorization': `Bearer ${token}` }
        }
      )
      setChatSessions(response.data)
    } catch (error) {
      console.error('Failed to fetch chat sessions:', error)
    }
  }

  /**
   * Load messages for a specific session.
   */
  const loadSessionMessages = async (sessionId) => {
    try {
      const token = getToken()
      if (!token) return

      const response = await axios.get(
        `${API_BASE_URL}/api/ai-agent/sessions/${sessionId}/messages`,
        {
          headers: { 'Authorization': `Bearer ${token}` }
        }
      )

      const formattedMessages = response.data.map(msg => ({
        id: msg.id,
        role: msg.role,
        content: msg.content,
        timestamp: new Date(msg.created_at)
      }))

      setMessages(formattedMessages)
    } catch (error) {
      console.error('Failed to load session messages:', error)
    }
  }

  /**
   * Start a new chat session.
   */
  const startNewSession = () => {
    setCurrentSessionId(null)
    setMessages([{
      id: Date.now(),
      role: 'assistant',
      content: "👋 Hello! I'm your AI ticket assistant. I can help you understand your pending tickets and answer questions about them. You can also upload documents or use voice input!",
      timestamp: new Date()
    }])
  }

  /**
   * Delete a chat session.
   */
  const deleteSession = async (sessionId, e) => {
    e.stopPropagation()
    if (!window.confirm('Are you sure you want to delete this chat session?')) {
      return
    }

    try {
      const token = getToken()
      if (!token) return

      await axios.delete(
        `${API_BASE_URL}/api/ai-agent/sessions/${sessionId}`,
        {
          headers: { 'Authorization': `Bearer ${token}` }
        }
      )

      // Refresh sessions list
      await fetchChatSessions()

      // If deleted session was current, start new session
      if (currentSessionId === sessionId) {
        startNewSession()
      }
    } catch (error) {
      console.error('Failed to delete session:', error)
      alert('Failed to delete session. Please try again.')
    }
  }

  /**
   * Handle voice input toggle.
   */
  const toggleVoiceInput = () => {
    if (typeof window === 'undefined') {
      return
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRecognition) {
      alert('Speech recognition is not supported in your browser. Please use Chrome or Edge.')
      return
    }

    if (!recognitionRef.current) {
      initializeSpeechRecognition()
    }

    if (!recognitionRef.current) {
      alert('Failed to initialize speech recognition.')
      return
    }

    if (isRecording) {
      recognitionRef.current.stop()
      setIsRecording(false)
    } else {
      try {
        recognitionRef.current.start()
        setIsRecording(true)
      } catch (error) {
        console.error('Speech recognition error:', error)
        setIsRecording(false)
      }
    }
  }

  /**
   * Handle file upload.
   */
  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    if (file.size > 10 * 1024 * 1024) {
      alert('File size must be less than 10MB')
      return
    }

    if (!file.type.startsWith('image/')) {
      alert('Please upload an image file')
      return
    }

    try {
      const token = getToken()
      const formData = new FormData()
      formData.append('screenshot', file)
      formData.append('message', 'Document uploaded for AI analysis')
      formData.append('customer', user?.full_name || user?.username || 'Customer')

      // Upload document
      const response = await axios.post(
        `${API_BASE_URL}/api/ticket/chat`,
        formData,
        {
          headers: { 'Authorization': `Bearer ${token}` }
        }
      )

      const docInfo = {
        id: response.data.id,
        name: file.name,
        url: response.data.screenshot_path 
          ? `${API_BASE_URL}${response.data.screenshot_path}` 
          : URL.createObjectURL(file),
        ticketId: response.data.id
      }

      setUploadedDocs([...uploadedDocs, docInfo])

      // Ask AI about the document
      const docMessage = `I just uploaded a document (${file.name}). Can you analyze it and tell me what information is in it?`
      await sendMessage(docMessage)
    } catch (error) {
      console.error('Failed to upload document:', error)
      alert('Failed to upload document. Please try again.')
    }
  }

  /**
   * Send message to AI agent with streaming status updates.
   */
  const sendMessage = async (messageText = null) => {
    const text = messageText || inputMessage.trim()
    if (!text) return

    // Add user message optimistically
    const userMessage = {
      id: Date.now(),
      role: 'user',
      content: text,
      timestamp: new Date()
    }
    setMessages(prev => [...prev, userMessage])
    setInputMessage('')
    setIsLoading(true)
    setCurrentStatus(null)

    try {
      const token = getToken()
      if (!token) {
        navigate('/login')
        return
      }

      // Use streaming endpoint
      const response = await fetch(`${API_BASE_URL}/api/ai-agent/chat/stream`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          message: text,
          session_id: currentSessionId
        })
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              
              if (data.type === 'status') {
                setCurrentStatus(data.message)
                // Scroll to show status update
                setTimeout(() => {
                  scrollToBottom()
                }, 50)
              } else if (data.type === 'complete') {
                // Update current session ID if it's a new session
                if (!currentSessionId && data.session_id) {
                  setCurrentSessionId(data.session_id)
                }

                // Add AI response
                const aiMessage = {
                  id: data.message_id || Date.now() + 1,
                  role: 'assistant',
                  content: data.response,
                  timestamp: new Date(),
                  actionPerformed: data.action_performed,
                  actionDetails: data.action_details
                }
                setMessages(prev => [...prev, aiMessage])
                setCurrentStatus(null)

                // Scroll to bottom after message is added
                setTimeout(() => {
                  scrollToBottom()
                }, 200)

                // Refresh sessions and pending tickets
                await fetchChatSessions()
                await fetchPendingTickets()
              } else if (data.type === 'error') {
                const errorMessage = {
                  id: Date.now() + 1,
                  role: 'assistant',
                  content: data.message || 'Sorry, I encountered an error. Please try again.',
                  timestamp: new Date(),
                  error: true
                }
                setMessages(prev => [...prev, errorMessage])
                setCurrentStatus(null)
              }
            } catch (e) {
              console.error('Error parsing SSE data:', e)
            }
          }
        }
      }
    } catch (error) {
      console.error('Streaming error:', error)
      const errorMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        content: error.message || 'Sorry, I encountered an error. Please try again.',
        timestamp: new Date(),
        error: true
      }
      setMessages(prev => [...prev, errorMessage])
      setCurrentStatus(null)
    } finally {
      setIsLoading(false)
      setCurrentStatus(null)
    }
  }

  /**
   * Handle form submission.
   */
  const handleSubmit = (e) => {
    e.preventDefault()
    if (!inputMessage.trim() || isLoading) return
    sendMessage()
  }

  return (
    <div className="ai-agent-page">
      <div className="ai-agent-container">
        <div className="ai-agent-main">
          <div className="chat-header">
            <div className="header-content">
              <div className="header-top">
                <div>
                  <h1>🤖 AI Ticket Agent</h1>
                </div>
              
              
              </div>
              <div>
                <button
                  onClick={startNewSession}
                  className="btn-new-chat"
                  title="Start New Chat"
                >
                  ➕ New Chat
                </button>
                </div>
            </div>
            {pendingTickets.length > 0 && (
              <div className="tickets-badge">
                {pendingTickets.length} Pending Ticket{pendingTickets.length !== 1 ? 's' : ''}
              </div>
            )}
          </div>

          <div className="chat-messages" ref={messagesContainerRef}>
            {messages.map((msg) => (
              <div key={msg.id} className={`message ${msg.role}`}>
                <div className="message-avatar">
                  {msg.role === 'user' ? '👤' : '🤖'}
                </div>
                <div className="message-content">
                  {msg.actionPerformed && (
                     <div className="action-badge">
                       {msg.actionPerformed === 'create_ticket' && (
                         <span className="action-icon">✅</span>
                       )}
                       {msg.actionPerformed === 'update_category' && (
                         <span className="action-icon">🔄</span>
                       )}
                       {msg.actionPerformed === 'reopen_ticket' && (
                         <span className="action-icon">🔓</span>
                       )}
                       <span className="action-text">
                         {msg.actionPerformed === 'create_ticket' && msg.actionDetails && (
                           <>
                             <div>✅ Ticket #{msg.actionDetails.ticket_id} created</div>
                             <div>Category: <strong>{msg.actionDetails.category}</strong></div>
                             <div>Assigned to: <strong>{msg.actionDetails.assigned_team}</strong></div>
                             {msg.actionDetails.eta && (
                               <div>ETA: <strong>{new Date(msg.actionDetails.eta).toLocaleString()}</strong></div>
                             )}
                           </>
                         )}
                         {msg.actionPerformed === 'update_category' && msg.actionDetails && (
                           <>
                             <div>Category: <strong>{msg.actionDetails.old_category}</strong> → <strong>{msg.actionDetails.new_category}</strong></div>
                             <div>Status: <strong>{msg.actionDetails.old_status}</strong> → <strong>pending</strong></div>
                             {msg.actionDetails.new_eta && (
                               <div>New ETA: <strong>{new Date(msg.actionDetails.new_eta).toLocaleString()}</strong></div>
                             )}
                           </>
                         )}
                         {msg.actionPerformed === 'reopen_ticket' && msg.actionDetails && (
                           <>Ticket #{msg.actionDetails.ticket_id} reopened</>
                         )}
                       </span>
                    </div>
                  )}
                   <div className="message-text">
                     {msg.role === 'assistant' ? (
                       <FormattedMessage content={msg.content} />
                     ) : (
                       msg.content
                     )}
                   </div>
                  <div className="message-time">
                    {new Date(msg.timestamp).toLocaleTimeString()}
                  </div>
                </div>
              </div>
            ))}
            {isLoading && (
              <div className="message assistant">
                <div className="message-avatar">🤖</div>
                <div className="message-content">
                  {currentStatus ? (
                    <div className="status-indicator">
                      <div className="status-spinner"></div>
                      <span className="status-text">{currentStatus}</span>
                    </div>
                  ) : (
                    <div className="typing-indicator">
                      <span></span>
                      <span></span>
                      <span></span>
                    </div>
                  )}
                </div>
              </div>
            )}
            <div ref={messagesEndRef} style={{ height: '1px' }} />
          </div>

          <div className="chat-input-container">
            <form onSubmit={handleSubmit} className="chat-input-form">
              <div className="input-actions">
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="btn-icon"
                  title="Upload Document"
                >
                  📎
                </button>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  onChange={handleFileUpload}
                  style={{ display: 'none' }}
                />
                <button
                  type="button"
                  onClick={toggleVoiceInput}
                  className={`btn-icon ${isRecording ? 'recording' : ''}`}
                  title="Voice Input"
                >
                  {isRecording ? '🎤' : '🎙️'}
                </button>
              </div>
              <input
                type="text"
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                placeholder={isRecording ? "Listening..." : "Type your message or use voice input..."}
                className="chat-input"
                disabled={isLoading}
              />
              <button
                type="submit"
                className="btn-send"
                disabled={!inputMessage.trim() || isLoading}
              >
                {isLoading ? '⏳' : '➤'}
              </button>
            </form>
            {isRecording && (
              <div className="recording-indicator">
                <span className="pulse"></span>
                Recording...
              </div>
            )}
          </div>
        </div>

        <div className="ai-agent-sidebar">
          <div className="sidebar-section">
            <div className="section-header">
              <h3>💬 Chat History</h3>
              <button
                onClick={() => setShowHistory(!showHistory)}
                className="btn-toggle"
              >
                {showHistory ? '▼' : '▶'}
              </button>
            </div>
            {showHistory && (
              <div className="chat-sessions-list">
                {chatSessions.length === 0 ? (
                  <p className="no-sessions">No chat history yet</p>
                ) : (
                  chatSessions.map((session) => (
                    <div
                      key={session.id}
                      className={`chat-session-item ${currentSessionId === session.id ? 'active' : ''}`}
                      onClick={() => setCurrentSessionId(session.id)}
                    >
                      <div className="session-content">
                        <div className="session-title">
                          {session.title || `Chat ${session.id}`}
                        </div>
                        <div className="session-meta">
                          <span>{session.message_count} messages</span>
                          <span>{new Date(session.updated_at).toLocaleDateString()}</span>
                        </div>
                      </div>
                      <button
                        onClick={(e) => deleteSession(session.id, e)}
                        className="btn-delete-session"
                        title="Delete Session"
                      >
                        🗑️
                      </button>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>

          <div className="sidebar-section">
            <h3>📋 Your Pending Tickets</h3>
            {pendingTickets.length === 0 ? (
              <p className="no-tickets">No pending tickets</p>
            ) : (
              <div className="tickets-list">
                {pendingTickets.map((ticket) => (
                  <div key={ticket.id} className="ticket-card">
                    <div className="ticket-header">
                      <span className="ticket-id">#{ticket.id}</span>
                      <span className={`badge badge-${ticket.category}`}>
                        {ticket.category}
                      </span>
                    </div>
                    <p className="ticket-message">{ticket.message.substring(0, 100)}...</p>
                    <div className="ticket-footer">
                      <span className="ticket-status">{ticket.status}</span>
                      <span className="ticket-team">{ticket.assignedTeam}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {uploadedDocs.length > 0 && (
            <div className="sidebar-section">
              <h3>📎 Uploaded Documents</h3>
              <div className="docs-list">
                {uploadedDocs.map((doc) => (
                  <div key={doc.id} className="doc-item">
                    <span className="doc-name">{doc.name}</span>
                    {doc.url && (
                      <a href={doc.url} target="_blank" rel="noopener noreferrer" className="doc-link">
                        View
                      </a>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="sidebar-section">
            <h3>💡 Tips</h3>
            <ul className="tips-list">
              <li>Ask about your ticket status</li>
              <li>Upload documents for analysis</li>
              <li>Use voice input for quick queries</li>
              <li>Get updates on pending tickets</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}

export default AIAgent

