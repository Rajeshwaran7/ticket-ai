import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const authApi = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add token to requests if available
authApi.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Handle 401 errors
authApi.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export const register = async (userData) => {
  const response = await authApi.post('/api/auth/register', userData)
  if (response.data.access_token) {
    localStorage.setItem('token', response.data.access_token)
    localStorage.setItem('user', JSON.stringify(response.data.user))
  }
  return response.data
}

export const login = async (credentials) => {
  const response = await authApi.post('/api/auth/login', credentials)
  if (response.data.access_token) {
    localStorage.setItem('token', response.data.access_token)
    localStorage.setItem('user', JSON.stringify(response.data.user))
  }
  return response.data
}

export const logout = async () => {
  try {
    await authApi.post('/api/auth/logout')
  } finally {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }
}

export const getCurrentUser = () => {
  const userStr = localStorage.getItem('user')
  return userStr ? JSON.parse(userStr) : null
}

export const getToken = () => {
  return localStorage.getItem('token')
}

export const isAuthenticated = () => {
  return !!getToken()
}

export const isAdmin = () => {
  const user = getCurrentUser()
  return user?.role === 'admin'
}

export const isCustomer = () => {
  const user = getCurrentUser()
  return user?.role === 'customer'
}

export default authApi

