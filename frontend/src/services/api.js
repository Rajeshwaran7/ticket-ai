import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

export const createTicket = async (ticketData) => {
  const response = await api.post('/api/ticket', ticketData)
  return response.data
}

export const classifyTicket = async (text) => {
  const response = await api.post('/api/classify', { text })
  return response.data
}

export const getTickets = async () => {
  const response = await api.get('/api/ticket')
  return response.data
}

export const getTicket = async (id) => {
  const response = await api.get(`/api/ticket/${id}`)
  return response.data
}

export const updateTicketStatus = async (id, status) => {
  const response = await api.put(`/api/ticket/${id}/status`, { status })
  return response.data
}

export default api

