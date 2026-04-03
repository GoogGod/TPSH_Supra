import api from '../api'

const DEFAULT_TITLE = '\u0423\u0432\u0435\u0434\u043e\u043c\u043b\u0435\u043d\u0438\u0435'
const ERROR_ID = '\u041d\u0435 \u0443\u043a\u0430\u0437\u0430\u043d \u0438\u0434\u0435\u043d\u0442\u0438\u0444\u0438\u043a\u0430\u0442\u043e\u0440 \u0443\u0432\u0435\u0434\u043e\u043c\u043b\u0435\u043d\u0438\u044f'

const asArray = (payload) => {
  if (Array.isArray(payload)) return payload
  if (Array.isArray(payload?.results)) return payload.results
  if (Array.isArray(payload?.items)) return payload.items
  if (Array.isArray(payload?.data)) return payload.data
  return []
}

const firstDefined = (...values) => values.find((value) => value !== undefined && value !== null)

const normalizeBoolean = (value) => {
  if (typeof value === 'boolean') return value
  if (typeof value === 'number') return value > 0
  if (typeof value === 'string') return ['true', '1', 'yes', 'read'].includes(value.toLowerCase())
  return false
}

const extractNotificationPayload = (item) =>
  firstDefined(item?.payload, item?.data, item?.meta, item?.extra, item?.context, {})

const buildNotificationMessage = (item, payload) =>
  firstDefined(
    item?.message,
    item?.description,
    item?.text,
    item?.body,
    payload?.message,
    payload?.description,
    ''
  )

const buildNotificationTitle = (item, payload) =>
  firstDefined(item?.title, item?.subject, item?.name, payload?.title, payload?.subject, DEFAULT_TITLE)

const TYPE_CONFIRM_TOKENS = ['assign', 'assignment', 'slot_assign', 'slot-assign', 'slot_claim', 'slot-claim', 'claim', 'confirm']
const TYPE_REJECT_TOKENS = ['claim', 'slot_claim', 'slot-claim', 'request', 'pending']
const DECISION_STATUSES = ['pending', 'awaiting_review', 'awaiting_confirmation', 'requested']

export const normalizeNotification = (item = {}) => {
  const payload = extractNotificationPayload(item)
  const status = String(
    firstDefined(item?.status, item?.state, payload?.status, payload?.state, '')
  ).toLowerCase()
  const type = String(firstDefined(item?.type, item?.kind, payload?.type, payload?.kind, '')).toLowerCase()
  const canConfirm = normalizeBoolean(
    firstDefined(item?.can_confirm, item?.canConfirm, payload?.can_confirm, payload?.canConfirm)
  )
  const canReject = normalizeBoolean(
    firstDefined(item?.can_reject, item?.canReject, payload?.can_reject, payload?.canReject)
  )
  const actionRequired = normalizeBoolean(
    firstDefined(
      item?.action_required,
      item?.actionRequired,
      payload?.action_required,
      payload?.actionRequired
    )
  )

  return {
    id: firstDefined(item?.id, item?.notification_id, payload?.notification_id, ''),
    title: buildNotificationTitle(item, payload),
    message: buildNotificationMessage(item, payload),
    created_at: firstDefined(item?.created_at, item?.createdAt, item?.timestamp, payload?.created_at, ''),
    read: normalizeBoolean(firstDefined(item?.read, item?.is_read, item?.isRead, payload?.read)),
    audience: firstDefined(item?.audience, payload?.audience, ''),
    venue: firstDefined(item?.venue, item?.venue_id, payload?.venue, payload?.venue_id, null),
    type,
    status,
    action_required: actionRequired,
    can_confirm: canConfirm,
    can_reject: canReject,
    employee_name: firstDefined(
      item?.employee_name,
      payload?.employee_name,
      payload?.employee?.full_name,
      payload?.employee?.name,
      ''
    ),
    slot_label: firstDefined(
      item?.slot_label,
      payload?.slot_label,
      payload?.waiter_label,
      payload?.position_label,
      ''
    ),
    schedule_id: firstDefined(item?.schedule_id, payload?.schedule_id, null),
    raw: item
  }
}

const extractUnreadCount = (payload) => {
  const raw = firstDefined(
    payload?.unread_count,
    payload?.unreadCount,
    payload?.count,
    payload?.total,
    payload?.results?.unread_count
  )
  const value = Number(raw)
  return Number.isFinite(value) && value >= 0 ? value : 0
}

export const notificationCanConfirm = (notification) => {
  if (!notification || notification.read) return false
  if (notification.can_confirm || notification.action_required) return true
  if (DECISION_STATUSES.includes(notification.status)) return true
  return TYPE_CONFIRM_TOKENS.some((token) => notification.type.includes(token))
}

export const notificationCanReject = (notification) => {
  if (!notification || notification.read) return false
  if (notification.can_reject) return true
  return (
    DECISION_STATUSES.includes(notification.status) &&
    TYPE_REJECT_TOKENS.some((token) => notification.type.includes(token))
  )
}

export const notificationNeedsDecision = (notification) => {
  return notificationCanConfirm(notification) || notificationCanReject(notification)
}

export const fetchNotifications = async () => {
  const response = await api.get('/notifications/')
  return asArray(response.data).map(normalizeNotification)
}

export const fetchUnreadNotificationsCount = async () => {
  const response = await api.get('/notifications/unread-count/')
  return extractUnreadCount(response.data)
}

export const markNotificationAsRead = async (notificationId) => {
  if (!notificationId) throw new Error(ERROR_ID)
  const response = await api.post(`/notifications/${notificationId}/read/`)
  return response.data
}

export const markAllNotificationsAsRead = async () => {
  const response = await api.post('/notifications/read-all/')
  return response.data
}

export const confirmNotification = async (notificationId) => {
  if (!notificationId) throw new Error(ERROR_ID)
  const response = await api.post(`/notifications/${notificationId}/confirm/`)
  return response.data
}

export const rejectNotification = async (notificationId) => {
  if (!notificationId) throw new Error(ERROR_ID)
  const response = await api.post(`/notifications/${notificationId}/reject/`)
  return response.data
}
