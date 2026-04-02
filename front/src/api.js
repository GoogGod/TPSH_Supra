import axios from 'axios'

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

const REFRESH_URL = '/auth/token/refresh/'

let refreshRequest = null

const clearStoredAuth = () => {
  localStorage.removeItem('access')
  localStorage.removeItem('refresh')
  localStorage.removeItem('user')
  localStorage.removeItem('isAuthenticated')
}

const getStoredAccessToken = () => localStorage.getItem('access')
const getStoredRefreshToken = () => localStorage.getItem('refresh')

const storeTokens = ({ access, refresh }) => {
  if (access) {
    localStorage.setItem('access', access)
  }

  if (refresh) {
    localStorage.setItem('refresh', refresh)
  }
}

const api = axios.create({
  baseURL: API_BASE_URL
})

api.interceptors.request.use((config) => {
  const token = getStoredAccessToken()

  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }

  return config
})

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error?.config
    const status = error?.response?.status

    if (!originalRequest || status !== 401 || originalRequest._retry) {
      return Promise.reject(error)
    }

    const refreshToken = getStoredRefreshToken()

    if (!refreshToken) {
      clearStoredAuth()
      return Promise.reject(error)
    }

    if (!refreshRequest) {
      refreshRequest = axios
        .post(`${API_BASE_URL}${REFRESH_URL}`, { refresh: refreshToken })
        .then((response) => {
          const nextAccessToken = response?.data?.access

          if (!nextAccessToken) {
            throw new Error('Backend did not return a refreshed access token')
          }

          storeTokens({
            access: nextAccessToken,
            refresh: response?.data?.refresh
          })

          return nextAccessToken
        })
        .catch((refreshError) => {
          clearStoredAuth()
          throw refreshError
        })
        .finally(() => {
          refreshRequest = null
        })
    }

    try {
      const nextAccessToken = await refreshRequest
      originalRequest._retry = true
      originalRequest.headers = originalRequest.headers || {}
      originalRequest.headers.Authorization = `Bearer ${nextAccessToken}`
      return api(originalRequest)
    } catch (refreshError) {
      return Promise.reject(refreshError)
    }
  }
)

export default api
