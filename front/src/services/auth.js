import api from '../api'

export const getAccessToken = () => localStorage.getItem('access')
export const getRefreshToken = () => localStorage.getItem('refresh')

export const isAuthenticated = () => !!getAccessToken()

export const getCurrentUser = () => {
  const raw = localStorage.getItem('user')

  if (!raw) {
    return null
  }

  try {
    return JSON.parse(raw)
  } catch (error) {
    localStorage.removeItem('user')
    return null
  }
}

export const getUserRole = () => {
  const user = getCurrentUser()
  return String(user?.role || user?.ROLE || '').toLowerCase()
}

export const setTokens = ({ access, refresh }) => {
  if (access) localStorage.setItem('access', access)
  if (refresh) localStorage.setItem('refresh', refresh)
}

export const setCurrentUser = (user) => {
  if (!user) return
  localStorage.setItem('user', JSON.stringify(user))
  localStorage.setItem('isAuthenticated', 'true')
}

export const clearAuthData = () => {
  localStorage.removeItem('access')
  localStorage.removeItem('refresh')
  localStorage.removeItem('user')
  localStorage.removeItem('isAuthenticated')
}

export const logoutUser = () => {
  clearAuthData()
}

export const fetchCurrentUser = async () => {
  const access = getAccessToken()

  if (!access) {
    throw new Error('Нет access токена')
  }

  const response = await api.get('/users/me/')
  return response.data
}

export const ensureAuth = async () => {
  if (!isAuthenticated()) {
    return false
  }

  const savedUser = getCurrentUser()
  if (savedUser) {
    return true
  }

  try {
    const user = await fetchCurrentUser()
    setCurrentUser(user)
    return true
  } catch (error) {
    clearAuthData()
    return false
  }
}
