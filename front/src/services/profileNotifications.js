const STORAGE_KEY = 'profile_notifications'

const readNotifications = () => {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
    return Array.isArray(parsed) ? parsed : []
  } catch (error) {
    return []
  }
}

const writeNotifications = (items) => {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(items))
}

export const getProfileNotifications = () => readNotifications()

export const pushProfileNotification = (payload) => {
  const items = readNotifications()
  const dedupeKey = payload?.dedupe_key

  if (dedupeKey) {
    const existingIndex = items.findIndex((item) => item.dedupe_key === dedupeKey)

    if (existingIndex >= 0) {
      const updated = {
        ...items[existingIndex],
        ...payload,
        read: false,
        created_at: new Date().toISOString()
      }

      items.splice(existingIndex, 1)
      items.unshift(updated)
      writeNotifications(items)
      return updated
    }
  }

  const notification = {
    id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    created_at: new Date().toISOString(),
    read: false,
    ...payload
  }

  items.unshift(notification)
  writeNotifications(items)
  return notification
}

export const markProfileNotificationRead = (notificationId) => {
  const items = readNotifications().map((item) =>
    item.id === notificationId
      ? {
          ...item,
          read: true
        }
      : item
  )

  writeNotifications(items)
}
