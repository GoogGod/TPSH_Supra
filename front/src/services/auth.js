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
  if (access) {
    localStorage.setItem('access', access)
  }

  if (refresh) {
    localStorage.setItem('refresh', refresh)
  }
}

export const setCurrentUser = (user) => {
  if (!user) {
    return
  }

  localStorage.setItem('user', JSON.stringify(user))
  localStorage.setItem('isAuthenticated', 'true')
}

export const clearAuthData = () => {
  localStorage.removeItem('access')
  localStorage.removeItem('refresh')
  localStorage.removeItem('user')
  localStorage.removeItem('isAuthenticated')
}

const extractAuthErrorMessage = (error, fallbackMessage) => {
  const data = error?.response?.data

  if (!data) {
    return error?.message || fallbackMessage
  }

  if (typeof data === 'string') {
    return data
  }

  if (data.detail) {
    return Array.isArray(data.detail) ? data.detail.join(', ') : data.detail
  }

  return (
    Object.entries(data)
      .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(', ') : value}`)
      .join('; ') || fallbackMessage
  )
}

export const fetchCurrentUser = async () => {
  const access = getAccessToken()

  if (!access) {
    throw new Error('Нет access токена')
  }

  const response = await api.get('/users/me/')
  return response.data
}

export const loginUser = async ({ username, password }) => {
  try {
    const response = await api.post('/auth/login/', {
      username,
      password
    })

    const { access, refresh, user } = response.data || {}

    if (!access || !refresh) {
      throw new Error('Бэкенд не вернул access и refresh токены')
    }

    setTokens({ access, refresh })

    if (user) {
      setCurrentUser(user)
      return user
    }

    const freshUser = await fetchCurrentUser()
    setCurrentUser(freshUser)
    return freshUser
  } catch (error) {
    clearAuthData()
    throw new Error(extractAuthErrorMessage(error, 'Ошибка авторизации'))
  }
}

export const logoutUser = async () => {
  const refresh = getRefreshToken()

  try {
    if (refresh) {
      await api.post('/auth/logout/', { refresh })
    }
  } catch (error) {
    // Even if backend logout fails, local auth must be cleared.
  } finally {
    clearAuthData()
  }
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
