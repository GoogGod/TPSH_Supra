<template>
  <div ref="root" class="notification-bell">
    <button
      class="notification-bell-button"
      type="button"
      :aria-label="t.open"
      :aria-expanded="isOpen ? 'true' : 'false'"
      @click="togglePanel"
    >
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path
          d="M12 3a4 4 0 0 0-4 4v1.1c0 1.1-.3 2.2-.9 3.1L5.6 13.5A1.5 1.5 0 0 0 6.9 16h10.2a1.5 1.5 0 0 0 1.3-2.5l-1.5-2.3a5.7 5.7 0 0 1-.9-3.1V7a4 4 0 0 0-4-4Zm0 18a2.5 2.5 0 0 0 2.4-2h-4.8A2.5 2.5 0 0 0 12 21Z"
          fill="currentColor"
        />
      </svg>
      <span v-if="unreadCount > 0" class="notification-badge">
        {{ badgeLabel }}
      </span>
    </button>

    <transition name="notification-popover">
      <div v-if="isOpen" class="notification-popover">
        <div class="notification-popover-head">
          <div>
            <p>{{ t.events }}</p>
            <h3>{{ t.notifications }}</h3>
          </div>
          <div class="notification-head-actions">
            <button
              v-if="canTogglePush"
              class="notification-head-action"
              type="button"
              :disabled="isRequestingPushPermission"
              @click="handleTogglePush"
            >
              {{ pushButtonLabel }}
            </button>
            <button
              v-if="notifications.length > 0"
              class="notification-head-action"
              type="button"
              @click="handleClearLocal"
            >
              {{ t.clear }}
            </button>
            <button
              v-if="unreadCount > 0"
              class="notification-head-action"
              type="button"
              :disabled="isMarkingAll"
              @click="handleMarkAllRead"
            >
              {{ isMarkingAll ? t.reading : t.readAll }}
            </button>
          </div>
        </div>

        <div v-if="error" class="notification-state is-error">
          {{ error }}
        </div>
        <div v-if="!error && pushStateLabel" class="notification-state">
          {{ pushStateLabel }}
        </div>
        <div v-if="!error && isLoading && notifications.length === 0" class="notification-state">
          {{ t.loading }}
        </div>
        <div v-else-if="!error && notifications.length === 0" class="notification-state">
          {{ t.empty }}
        </div>
        <div v-else class="notification-list">
          <article
            v-for="notification in notifications"
            :key="notification.id"
            class="notification-card"
            :class="{ 'is-unread': !notification.read }"
          >
            <div class="notification-copy">
              <strong>{{ notification.title }}</strong>
              <p>{{ notification.message }}</p>
              <div
                v-if="notification.employee_name || notification.slot_label"
                class="notification-meta"
              >
                <span v-if="notification.employee_name">{{ notification.employee_name }}</span>
                <span v-if="notification.slot_label">{{ notification.slot_label }}</span>
              </div>
              <small>{{ formatDate(notification.created_at) }}</small>
            </div>

            <div class="notification-actions">
              <template v-if="canConfirm(notification) || canReject(notification)">
                <button
                  v-if="canConfirm(notification)"
                  class="notification-action primary"
                  type="button"
                  :disabled="actionLoadingId === notification.id"
                  @click="handleConfirm(notification.id)"
                >
                  {{ t.confirm }}
                </button>
                <button
                  v-if="canReject(notification)"
                  class="notification-action"
                  type="button"
                  :disabled="actionLoadingId === notification.id"
                  @click="handleReject(notification.id)"
                >
                  {{ t.reject }}
                </button>
              </template>
              <button
                v-else-if="!notification.read"
                class="notification-action"
                type="button"
                :disabled="actionLoadingId === notification.id"
                @click="handleRead(notification.id)"
              >
                {{ t.readOne }}
              </button>
            </div>
          </article>
        </div>
      </div>
    </transition>
  </div>
</template>

<script>
import {
  confirmNotification,
  fetchNotifications,
  fetchUnreadNotificationsCount,
  getSystemNotificationPermission,
  markAllNotificationsAsRead,
  markNotificationAsRead,
  notificationCanConfirm,
  notificationCanReject,
  notificationNeedsDecision,
  rejectNotification,
  requestSystemNotificationPermission,
  showSystemNotification,
  supportsSystemNotifications
} from '../services/notifications'

const POLL_INTERVAL_MS = 15000
const HIDDEN_NOTIFICATIONS_STORAGE_KEY = 'hidden_notification_ids'
const SHOWN_SYSTEM_NOTIFICATION_IDS_KEY = 'shown_system_notification_ids'
const PUSH_ENABLED_STORAGE_KEY = 'push_notifications_enabled'

const readHiddenNotificationIds = () => {
  try {
    const raw = JSON.parse(localStorage.getItem(HIDDEN_NOTIFICATIONS_STORAGE_KEY) || '[]')
    return Array.isArray(raw) ? raw.filter(Boolean) : []
  } catch (error) {
    return []
  }
}

const readShownSystemNotificationIds = () => {
  try {
    const raw = JSON.parse(localStorage.getItem(SHOWN_SYSTEM_NOTIFICATION_IDS_KEY) || '[]')
    return Array.isArray(raw) ? raw.filter(Boolean) : []
  } catch (error) {
    return []
  }
}

const readPushEnabled = () => {
  try {
    return localStorage.getItem(PUSH_ENABLED_STORAGE_KEY) === 'true'
  } catch (error) {
    return false
  }
}

const TEXT = {
  open: '\u041e\u0442\u043a\u0440\u044b\u0442\u044c \u0443\u0432\u0435\u0434\u043e\u043c\u043b\u0435\u043d\u0438\u044f',
  events: '\u0421\u043e\u0431\u044b\u0442\u0438\u044f',
  notifications: '\u0423\u0432\u0435\u0434\u043e\u043c\u043b\u0435\u043d\u0438\u044f',
  enablePush: '\u0412\u043a\u043b\u044e\u0447\u0438\u0442\u044c push',
  disablePush: '\u0412\u044b\u043a\u043b\u044e\u0447\u0438\u0442\u044c push \u0443\u0432\u0435\u0434\u043e\u043c\u043b\u0435\u043d\u0438\u044f',
  enablingPush: '\u0412\u043a\u043b\u044e\u0447\u0430\u0435\u043c...',
  pushBlocked: '\u0421\u0438\u0441\u0442\u0435\u043c\u043d\u044b\u0435 \u0443\u0432\u0435\u0434\u043e\u043c\u043b\u0435\u043d\u0438\u044f \u0437\u0430\u0431\u043b\u043e\u043a\u0438\u0440\u043e\u0432\u0430\u043d\u044b',
  clear: '\u041e\u0447\u0438\u0441\u0442\u0438\u0442\u044c',
  reading: '\u0427\u0438\u0442\u0430\u0435\u043c...',
  readAll: '\u041f\u0440\u043e\u0447\u0438\u0442\u0430\u0442\u044c \u0432\u0441\u0435',
  loading: '\u0417\u0430\u0433\u0440\u0443\u0436\u0430\u0435\u043c \u0443\u0432\u0435\u0434\u043e\u043c\u043b\u0435\u043d\u0438\u044f...',
  empty: '\u041d\u043e\u0432\u044b\u0445 \u0443\u0432\u0435\u0434\u043e\u043c\u043b\u0435\u043d\u0438\u0439 \u043f\u043e\u043a\u0430 \u043d\u0435\u0442.',
  confirm: '\u041f\u043e\u0434\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u044c',
  reject: '\u041e\u0442\u043a\u043b\u043e\u043d\u0438\u0442\u044c',
  readOne: '\u041f\u0440\u043e\u0447\u0438\u0442\u0430\u0442\u044c',
  loadError: '\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0437\u0430\u0433\u0440\u0443\u0437\u0438\u0442\u044c \u0443\u0432\u0435\u0434\u043e\u043c\u043b\u0435\u043d\u0438\u044f',
  readError: '\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043e\u0442\u043c\u0435\u0442\u0438\u0442\u044c \u0443\u0432\u0435\u0434\u043e\u043c\u043b\u0435\u043d\u0438\u0435 \u043a\u0430\u043a \u043f\u0440\u043e\u0447\u0438\u0442\u0430\u043d\u043d\u043e\u0435',
  readAllError: '\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043f\u0440\u043e\u0447\u0438\u0442\u0430\u0442\u044c \u0432\u0441\u0435 \u0443\u0432\u0435\u0434\u043e\u043c\u043b\u0435\u043d\u0438\u044f',
  confirmError: '\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u044c \u0437\u0430\u043a\u0440\u0435\u043f\u043b\u0435\u043d\u0438\u0435',
  rejectError: '\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043e\u0442\u043a\u043b\u043e\u043d\u0438\u0442\u044c \u0437\u0430\u043a\u0440\u0435\u043f\u043b\u0435\u043d\u0438\u0435'
}

export default {
  name: 'NotificationBell',
  emits: ['updated'],
  data() {
    return {
      t: TEXT,
      isOpen: false,
      isLoading: false,
      isMarkingAll: false,
      isRequestingPushPermission: false,
      actionLoadingId: null,
      error: '',
      unreadCount: 0,
      notifications: [],
      hiddenNotificationIds: readHiddenNotificationIds(),
      shownSystemNotificationIds: readShownSystemNotificationIds(),
      systemNotificationPermission: getSystemNotificationPermission(),
      pushEnabled: readPushEnabled()
    }
  },
  computed: {
    badgeLabel() {
      return this.unreadCount > 99 ? '99+' : String(this.unreadCount)
    },
    canTogglePush() {
      return supportsSystemNotifications() && this.systemNotificationPermission !== 'denied'
    },
    pushButtonLabel() {
      if (this.isRequestingPushPermission) return this.t.enablingPush
      return this.pushEnabled ? this.t.disablePush : this.t.enablePush
    },
    pushStateLabel() {
      if (this.systemNotificationPermission === 'denied') return this.t.pushBlocked
      return ''
    }
  },
  async mounted() {
    document.addEventListener('click', this.handleOutsideClick)
    document.addEventListener('visibilitychange', this.handleVisibilityChange)
    window.addEventListener('focus', this.handleWindowFocus)
    window.addEventListener('notifications:refresh', this.handleExternalRefresh)
    await this.bootstrapNotifications()
    this.pollTimer = window.setInterval(() => {
      this.refreshNotifications({ silent: true })
    }, POLL_INTERVAL_MS)
  },
  beforeUnmount() {
    document.removeEventListener('click', this.handleOutsideClick)
    document.removeEventListener('visibilitychange', this.handleVisibilityChange)
    window.removeEventListener('focus', this.handleWindowFocus)
    window.removeEventListener('notifications:refresh', this.handleExternalRefresh)
    if (this.pollTimer) {
      window.clearInterval(this.pollTimer)
    }
  },
  methods: {
    needsDecision(notification) {
      return notificationNeedsDecision(notification)
    },
    canConfirm(notification) {
      return notificationCanConfirm(notification)
    },
    canReject(notification) {
      return notificationCanReject(notification)
    },
    formatDate(value) {
      if (!value) return ''

      try {
        return new Date(value).toLocaleString('ru-RU', {
          day: '2-digit',
          month: '2-digit',
          year: 'numeric',
          hour: '2-digit',
          minute: '2-digit'
        })
      } catch (error) {
        return String(value)
      }
    },
    persistShownSystemNotificationIds() {
      try {
        const normalized = this.shownSystemNotificationIds.slice(-200)
        localStorage.setItem(SHOWN_SYSTEM_NOTIFICATION_IDS_KEY, JSON.stringify(normalized))
      } catch (error) {
        // ignore storage write issues
      }
    },
    markSystemNotificationsAsSeen(notifications) {
      const nextIds = notifications.map((item) => item.id).filter(Boolean)
      this.shownSystemNotificationIds = Array.from(new Set([
        ...this.shownSystemNotificationIds,
        ...nextIds
      ])).slice(-200)
      this.persistShownSystemNotificationIds()
    },
    async bootstrapNotifications() {
      try {
        const notifications = this.applyHiddenNotifications(await fetchNotifications())
        this.notifications = this.isOpen ? notifications : this.notifications
        this.unreadCount = notifications.filter((item) => !item.read).length
        this.markSystemNotificationsAsSeen(notifications)
      } catch (error) {
        await this.refreshUnreadCount()
      }
    },
    async syncNotifications({ silent = false, showSystem = true } = {}) {
      if (!silent) this.isLoading = true
      this.error = ''

      try {
        const notifications = this.applyHiddenNotifications(await fetchNotifications())
        this.notifications = this.isOpen ? notifications : this.notifications
        this.unreadCount = notifications.filter((item) => !item.read).length

        if (showSystem && this.pushEnabled && this.systemNotificationPermission === 'granted') {
          const hiddenIds = new Set(this.hiddenNotificationIds)
          const shownIds = new Set(this.shownSystemNotificationIds)
          const freshNotifications = notifications.filter((item) => !item.read && item.id && !hiddenIds.has(item.id) && !shownIds.has(item.id))

          for (const notification of freshNotifications) {
            try {
              await showSystemNotification(notification)
            } catch (error) {
              // ignore notification delivery issues
            }
          }
        }

        this.markSystemNotificationsAsSeen(notifications)
      } catch (error) {
        this.error = error?.message || this.t.loadError
      } finally {
        this.isLoading = false
      }
    },
    async refreshUnreadCount() {
      try {
        if (this.hiddenNotificationIds.length > 0) {
          const notifications = await fetchNotifications()
          const visible = this.applyHiddenNotifications(notifications)
          this.notifications = this.isOpen ? visible : this.notifications
          this.unreadCount = visible.filter((item) => !item.read).length
          return
        }

        this.unreadCount = await fetchUnreadNotificationsCount()
      } catch (error) {
        this.unreadCount = this.notifications.filter((item) => !item.read).length
      }
    },
    async refreshNotifications({ silent = false } = {}) {
      await this.syncNotifications({ silent, showSystem: true })
    },
    async loadNotifications({ silent = false } = {}) {
      await this.syncNotifications({ silent, showSystem: false })
    },
    async togglePanel() {
      this.isOpen = !this.isOpen
      if (this.isOpen) {
        await this.refreshNotifications()
      }
    },
    async handleTogglePush() {
      if (!this.canTogglePush || this.isRequestingPushPermission) return
      this.isRequestingPushPermission = true
      this.error = ''

      try {
        if (!this.pushEnabled) {
          this.systemNotificationPermission = await requestSystemNotificationPermission()
          if (this.systemNotificationPermission === 'granted') {
            this.pushEnabled = true
            localStorage.setItem(PUSH_ENABLED_STORAGE_KEY, 'true')
            await this.syncNotifications({ silent: true, showSystem: false })
          }
        } else {
          this.pushEnabled = false
          localStorage.setItem(PUSH_ENABLED_STORAGE_KEY, 'false')
          const registration = await navigator.serviceWorker.ready
          const subscription = await registration.pushManager.getSubscription()
          if (subscription) {
            await subscription.unsubscribe().catch(() => undefined)
          }
        }
      } catch (error) {
        this.error = error?.message || this.t.loadError
      } finally {
        this.isRequestingPushPermission = false
      }
    },
    handleOutsideClick(event) {
      if (!this.isOpen) return
      if (this.$refs.root?.contains(event.target)) return
      this.isOpen = false
    },
    handleVisibilityChange() {
      if (document.visibilityState === 'visible') {
        this.refreshNotifications({ silent: true })
      }
    },
    handleWindowFocus() {
      this.refreshNotifications({ silent: true })
    },
    handleExternalRefresh() {
      this.refreshNotifications({ silent: true })
    },
    applyHiddenNotifications(notifications) {
      const unreadOnly = notifications.filter((item) => !item.read)

      if (!this.hiddenNotificationIds.length) {
        return unreadOnly
      }

      const hiddenIds = new Set(this.hiddenNotificationIds)
      return unreadOnly.filter((item) => !hiddenIds.has(item.id))
    },
    persistHiddenNotificationIds() {
      try {
        localStorage.setItem(HIDDEN_NOTIFICATIONS_STORAGE_KEY, JSON.stringify(this.hiddenNotificationIds))
      } catch (error) {
        // ignore storage write issues
      }
    },
    handleClearLocal() {
      this.hiddenNotificationIds = Array.from(new Set([
        ...this.hiddenNotificationIds,
        ...this.notifications.map((notification) => notification.id).filter(Boolean)
      ]))
      this.persistHiddenNotificationIds()
      this.notifications = []
      this.unreadCount = 0
      this.error = ''
    },
    async handleRead(notificationId) {
      this.actionLoadingId = notificationId
      this.error = ''

      try {
        await markNotificationAsRead(notificationId)
        await this.loadNotifications({ silent: true })
        this.$emit('updated')
      } catch (error) {
        this.error = error?.message || this.t.readError
      } finally {
        this.actionLoadingId = null
      }
    },
    async handleMarkAllRead() {
      this.isMarkingAll = true
      this.error = ''

      try {
        await markAllNotificationsAsRead()
        await this.loadNotifications({ silent: true })
        this.$emit('updated')
      } catch (error) {
        this.error = error?.message || this.t.readAllError
      } finally {
        this.isMarkingAll = false
      }
    },
    async handleConfirm(notificationId) {
      this.actionLoadingId = notificationId
      this.error = ''

      try {
        await confirmNotification(notificationId)
        await this.loadNotifications({ silent: true })
        this.$emit('updated')
      } catch (error) {
        this.error = error?.message || this.t.confirmError
      } finally {
        this.actionLoadingId = null
      }
    },
    async handleReject(notificationId) {
      this.actionLoadingId = notificationId
      this.error = ''

      try {
        await rejectNotification(notificationId)
        await this.loadNotifications({ silent: true })
        this.$emit('updated')
      } catch (error) {
        this.error = error?.message || this.t.rejectError
      } finally {
        this.actionLoadingId = null
      }
    }
  }
}
</script>

<style scoped>
.notification-bell {
  position: relative;
  flex-shrink: 0;
}

.notification-bell-button {
  position: relative;
  width: 44px;
  height: 44px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.08);
  color: #ffffff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: 0.2s ease;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

.notification-bell-button:hover {
  background: rgba(255, 255, 255, 0.12);
}

.notification-bell-button svg {
  width: 21px;
  height: 21px;
}

.notification-badge {
  position: absolute;
  top: -4px;
  right: -4px;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 999px;
  background: #ff6b6b;
  color: #ffffff;
  font-size: 11px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 6px 14px rgba(255, 107, 107, 0.3);
}

.notification-popover {
  position: absolute;
  top: calc(100% + 10px);
  right: 0;
  width: min(92vw, 380px);
  max-height: min(70vh, 560px);
  overflow-y: auto;
  padding: 14px;
  border-radius: 20px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: linear-gradient(180deg, rgba(12, 20, 76, 0.98), rgba(8, 13, 52, 0.98));
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.35);
  z-index: 120;
}

.notification-popover-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.notification-head-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.notification-popover-head p {
  margin: 0 0 4px;
  color: rgba(255, 255, 255, 0.62);
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.notification-popover-head h3 {
  margin: 0;
  color: #ffffff;
  font-size: 20px;
}

.notification-head-action,
.notification-action {
  min-height: 38px;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: rgba(255, 255, 255, 0.08);
  color: #ffffff;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.notification-head-action {
  padding: 0 12px;
}

.notification-action {
  padding: 0 10px;
}

.notification-action.primary {
  border: none;
  background: linear-gradient(135deg, #49d17d, #2f9e62);
}

.notification-head-action:disabled,
.notification-action:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.notification-state {
  padding: 14px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.05);
  color: rgba(255, 255, 255, 0.8);
}

.notification-state.is-error {
  background: rgba(120, 18, 18, 0.2);
  border: 1px solid rgba(255, 115, 115, 0.35);
  color: #ffd2d8;
}

.notification-list {
  display: grid;
  gap: 10px;
}

.notification-card {
  display: grid;
  gap: 10px;
  padding: 12px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.notification-card.is-unread {
  border-color: rgba(73, 209, 125, 0.3);
  background: rgba(73, 209, 125, 0.08);
}

.notification-copy strong {
  display: block;
  margin-bottom: 6px;
  color: #ffffff;
}

.notification-copy p {
  margin: 0 0 8px;
  color: rgba(255, 255, 255, 0.88);
  line-height: 1.45;
}

.notification-copy small {
  color: rgba(255, 255, 255, 0.62);
  font-size: 12px;
}

.notification-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.notification-meta span {
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.86);
  font-size: 12px;
}

.notification-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.notification-popover-enter-active,
.notification-popover-leave-active {
  transition: opacity 0.16s ease, scale 0.16s ease;
}

.notification-popover-enter-from,
.notification-popover-leave-to {
  opacity: 0;
  scale: 0.98;
}

@media (max-width: 768px), (hover: none) and (pointer: coarse) {
  .notification-popover {
    position: fixed;
    top: 78px;
    left: 50%;
    right: auto;
    transform: translateX(-50%);
    width: min(92vw, 380px);
    padding: 12px;
  }
}
</style>
