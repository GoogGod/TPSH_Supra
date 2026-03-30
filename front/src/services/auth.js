export const getAccessToken = () => localStorage.getItem('access')
export const getRefreshToken = () => localStorage.getItem('refresh')

export const getCurrentUser = () => {
  const raw = localStorage.getItem('currentUser')
  return raw ? JSON.parse(raw) : null
}

export const getUserRole = () => {
  const user = getCurrentUser()
  return String(user?.ROLE || '').toLowerCase()
}

export const setTokens = ({ access, refresh }) => {
  if (access) localStorage.setItem('access', access)
  if (refresh) localStorage.setItem('refresh', refresh)
}

export const setCurrentUser = (user) => {
  if (!user) return
  localStorage.setItem('currentUser', JSON.stringify(user))
  localStorage.setItem('isAuthenticated', 'true')
}

export const clearAuthData = () => {
  localStorage.removeItem('access')
  localStorage.removeItem('refresh')
  localStorage.removeItem('currentUser')
  localStorage.removeItem('isAuthenticated')
}

export const ensureAuth = async () => {
  return true
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
// export const fetchCurrentUser = async () => {
//   const access = getAccessToken()

//   if (!access) {
//     throw new Error('Нет access токена')
//   }

//   return {
//     ID: 1,
//     USERNAME: 'test_user',
//     EMAIL: 'test@mail.com',
//     FIRST_NAME: 'Иван',
//     LAST_NAME: 'Иванов',
//     PHONE: '+79990000000',
//     ROLE: 'employee',
//     VENUE: 1,
//     VENUE_NAME: 'Ресторан №1',
//     SCHEDULE_PATTERN: '2/2',
//     SHIFT_DURATION: '12H',
//     IS_ACTIVE: true
//   }
// }