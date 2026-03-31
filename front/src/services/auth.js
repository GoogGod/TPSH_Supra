export const getAccessToken = () => localStorage.getItem('access')
export const getRefreshToken = () => localStorage.getItem('refresh')

export const getCurrentUser = () => {
  const raw = localStorage.getItem('user')
  return raw ? JSON.parse(raw) : null
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

export const fetchCurrentUser = async () => {
  const access = getAccessToken()

  if (!access) {
    throw new Error('Нет access токена')
  }

  const response = await fetch('http://localhost:8000/api/v1/users/me/', {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${access}`
    },
    credentials: 'include'
  })

  if (!response.ok) {
    throw new Error('Не удалось получить текущего пользователя')
  }

  return await response.json()
}

export const ensureAuth = async () => {
  const access = getAccessToken()
  const isAuthenticated = localStorage.getItem('isAuthenticated') === 'true'

  if (!access || !isAuthenticated) {
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