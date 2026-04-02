<template>
  <div class="forecast-page">
    <transition name="menu-overlay">
      <div
        v-if="menuOpen"
        class="side-menu-overlay"
        @click="closeMenu"
      ></div>
    </transition>

    <transition name="side-menu">
      <aside v-if="menuOpen" class="side-menu">
        <div class="side-menu-top">
          <button class="side-menu-close" @click="closeMenu">×</button>
        </div>

        <div class="side-menu-section">
          <button class="side-menu-item" @click="goToProfile">
            Профиль
          </button>
          <button class="side-menu-item active" @click="closeMenu">
            Расписание
          </button>
        </div>

        <div class="side-menu-footer">
          <button class="side-menu-item side-menu-item-danger" @click="handleLogout">
            Выйти
          </button>
        </div>
      </aside>
    </transition>

    <main class="forecast-content">
      <section class="forecast-card">
        <div class="forecast-card-top">
          <button class="menu-button" @click="openMenu" aria-label="Открыть меню">
            <span></span>
            <span></span>
            <span></span>
          </button>

          <div class="forecast-heading">
            <p class="forecast-subtitle">График работы</p>
            <h1 class="forecast-title">Расписание</h1>
          </div>
        </div>

        <div class="month-toolbar">
          <div class="month-switcher">
            <button class="month-button" :disabled="isMonthSwitching" @click="prevMonth">‹</button>
            <div class="month-label">{{ monthTitle }}</div>
            <button class="month-button" :disabled="isMonthSwitching" @click="nextMonth">›</button>
          </div>

          <button
            v-if="canManageSchedule"
            class="create-schedule-button"
            :disabled="isGeneratingSchedule"
            @click="handleCreateSchedule"
          >
            {{ isGeneratingSchedule ? 'Создаем...' : 'Создать расписание' }}
          </button>

          <button
            v-if="canPublishCurrentSchedule"
            class="publish-schedule-button"
            :disabled="isPublishingSchedule"
            @click="handlePublishSchedule"
          >
            {{ isPublishingSchedule ? 'Публикуем...' : 'Опубликовать' }}
          </button>
        </div>

        <div class="schedule-info-row">
          <div v-if="scheduleNotice" class="schedule-status-card is-success">
            {{ scheduleNotice }}
          </div>
          <div v-else-if="isLoadingSchedule" class="schedule-status-card">
            Загружаем расписание...
          </div>
          <div v-else-if="scheduleError" class="schedule-status-card is-error">
            {{ scheduleError }}
          </div>
          <div v-else-if="!hasSchedule" class="schedule-status-card">
            На этот месяц расписание пока не создано
          </div>
          <div v-else class="schedule-status-card is-soft">
            {{ roleHint }}
          </div>
        </div>

        <div class="waiter-picker-card">
          <div class="waiter-picker-head">
            <h2>{{ selectorTitle }}</h2>
            <p>{{ selectorDescription }}</p>
          </div>

          <div v-if="waiters.length === 0" class="waiter-empty-state">
            Нет доступных официантов для отображения
          </div>

          <div v-else class="waiter-button-list">
            <button
              v-for="waiter in waiters"
              :key="waiter.employee_key"
              class="waiter-button"
              :class="{
                active: waiter.employee_key === selectedWaiter,
                disabled: !canSelectWaiter(waiter)
              }"
              :style="getWaiterButtonStyle(waiter)"
              :disabled="!canSelectWaiter(waiter)"
              @click="selectWaiter(waiter.employee_key)"
            >
              <span class="waiter-button-name">{{ waiter.label }}</span>
              <span class="waiter-button-meta">{{ getWaiterMeta(waiter) }}</span>
            </button>
          </div>
        </div>

        <div class="calendar-card">
          <div class="calendar-weekdays">
            <div
              v-for="weekday in weekdays"
              :key="weekday"
              class="weekday-cell"
            >
              {{ weekday }}
            </div>
          </div>

          <div class="calendar-grid">
            <div
              v-for="day in calendarDays"
              :key="day.key"
              class="calendar-cell"
              :class="{
                'outside-month': !day.isCurrentMonth,
                'is-working': !!day.shift,
                'is-open-slot': !day.shift && day.hasOpenSlots,
                'is-today': day.isToday,
                'is-selected-waiter': !!day.shift
              }"
              :style="getDayStyle(day)"
            >
              <div class="day-number">{{ day.date.getDate() }}</div>

              <div v-if="day.shift" class="day-shift-mark">
                <span class="shift-chip">{{ getShiftLabel(day.shift.shift_type) }}</span>
                <span v-if="day.shift.work_start && day.shift.work_end" class="shift-caption">
                  {{ day.shift.work_start }}-{{ day.shift.work_end }}
                </span>
              </div>

              <div v-else-if="day.hasOpenSlots" class="day-open-mark">
                <span class="shift-chip open-slot-chip">Есть смены</span>
              </div>
            </div>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>

<script>
import '../assets/forecast.css'
import { fetchCurrentUser, logoutUser } from '../services/auth'
import { fetchScheduleForMonth, generateSchedule, publishSchedule } from '../services/schedule'

const USE_MOCK_AUTH = import.meta.env.VITE_USE_MOCK_AUTH === 'true'

const WAITER_COLORS = [
  '#f06292',
  '#64b5f6',
  '#4db6ac',
  '#ff8a65',
  '#9575cd',
  '#ffd54f',
  '#81c784',
  '#ba68c8'
]

const normalizeRole = (role) => String(role || '').toLowerCase()

const normalizeIdentity = (value) =>
  value === undefined || value === null || value === '' ? '' : String(value).toLowerCase()

export default {
  name: 'ForeCastView',
  data() {
    return {
      menuOpen: false,
      currentMonth: new Date(new Date().getFullYear(), new Date().getMonth(), 1),
      currentScheduleId: null,
      currentScheduleStatus: null,
      selectedWaiter: '',
      weekdays: ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'],
      scheduleRaw: [],
      scheduleExists: false,
      scheduleError: '',
      scheduleNotice: '',
      isLoadingSchedule: false,
      isMonthSwitching: false,
      isGeneratingSchedule: false,
      isPublishingSchedule: false,
      user: (() => {
        try {
          return JSON.parse(localStorage.getItem('user')) || { role: '' }
        } catch (error) {
          return { role: '' }
        }
      })()
    }
  },
  computed: {
    currentUserRole() {
      return normalizeRole(this.user.role)
    },
    canManageSchedule() {
      return ['manager', 'admin'].includes(this.currentUserRole)
    },
    isWaiterView() {
      return !this.canManageSchedule
    },
    hasSchedule() {
      return this.scheduleExists
    },
    canPublishCurrentSchedule() {
      return (
        this.canManageSchedule &&
        this.hasSchedule &&
        !!this.currentScheduleId &&
        this.currentScheduleStatus === 'draft'
      )
    },
    roleHint() {
      if (this.canManageSchedule) {
        if (this.currentScheduleStatus === 'draft') {
          return 'Открылся черновик расписания. Проверьте его и затем опубликуйте.'
        }

        return 'Выберите сотрудника и посмотрите его рабочие дни'
      }

      return 'Нажмите на нужного официанта, и календарь покажет его смены'
    },
    selectorTitle() {
      return this.canManageSchedule ? 'Сотрудники' : 'Официанты'
    },
    selectorDescription() {
      if (this.waiters.length === 0) {
        return 'Кнопки появятся, когда в расписании будут сотрудники'
      }

      return this.canManageSchedule
        ? 'Менеджер может переключаться между официантами и смотреть смены каждого'
        : 'Доступны только кнопки с той же ролью, что и у вас'
    },
    workingSchedule() {
      return this.scheduleRaw.filter((item) => item.is_working === true && item.employee_key)
    },
    waiters() {
      const grouped = new Map()

      this.workingSchedule.forEach((item) => {
        if (!grouped.has(item.employee_key)) {
          grouped.set(item.employee_key, {
            employee_key: item.employee_key,
            employee_id: item.employee_id,
            waiter_num: item.waiter_num,
            label: item.employee_label || this.getFallbackEmployeeLabel(item),
            grade: item.grade || null,
            color: this.getWaiterColor(item.employee_key),
            identities: [
              normalizeIdentity(item.employee_key),
              normalizeIdentity(item.employee_id),
              normalizeIdentity(item.waiter_num)
            ].filter(Boolean)
          })
        }
      })

      return Array.from(grouped.values()).sort((left, right) =>
        left.label.localeCompare(right.label, 'ru')
      )
    },
    selectedWaiterInfo() {
      return this.waiters.find((item) => item.employee_key === this.selectedWaiter) || null
    },
    pinnedWaiterKey() {
      const userIdentities = [
        normalizeIdentity(this.user.id),
        normalizeIdentity(this.user.username),
        normalizeIdentity(this.user.email),
        normalizeIdentity(this.user.waiter_num)
      ].filter(Boolean)

      const matchedWaiter = this.waiters.find((waiter) =>
        waiter.identities.some((identity) => userIdentities.includes(identity))
      )

      return matchedWaiter?.employee_key || ''
    },
    currentWaiterGrade() {
      if (this.currentUserRole === 'employee_noob' || this.currentUserRole === 'employee_pro') {
        return this.currentUserRole
      }

      const pinnedWaiter = this.waiters.find((waiter) => waiter.employee_key === this.pinnedWaiterKey)
      return String(pinnedWaiter?.grade || '').toLowerCase()
    },
    selectedWaiterScheduleMap() {
      const map = {}

      this.workingSchedule
        .filter((item) => item.employee_key === this.selectedWaiter)
        .forEach((item) => {
          map[item.date] = item
        })

      return map
    },
    openSlotsMap() {
      const map = {}

      this.scheduleRaw
        .filter((item) => item.date && item.is_working === true && !item.employee_key)
        .forEach((item) => {
          map[item.date] = true
        })

      return map
    },
    monthTitle() {
      return this.currentMonth.toLocaleDateString('ru-RU', {
        month: 'long',
        year: 'numeric'
      })
    },
    calendarDays() {
      const year = this.currentMonth.getFullYear()
      const month = this.currentMonth.getMonth()

      const firstDayOfMonth = new Date(year, month, 1)
      const lastDayOfMonth = new Date(year, month + 1, 0)
      const firstWeekday = (firstDayOfMonth.getDay() + 6) % 7
      const daysInMonth = lastDayOfMonth.getDate()

      const result = []

      for (let i = firstWeekday; i > 0; i--) {
        result.push(this.buildCalendarDay(new Date(year, month, 1 - i), false))
      }

      for (let day = 1; day <= daysInMonth; day++) {
        result.push(this.buildCalendarDay(new Date(year, month, day), true))
      }

      const rest = result.length % 7

      if (rest !== 0) {
        for (let i = 1; i <= 7 - rest; i++) {
          result.push(this.buildCalendarDay(new Date(year, month + 1, i), false))
        }
      }

      return result
    }
  },
  async mounted() {
    if (!USE_MOCK_AUTH) {
      try {
        const freshUser = await fetchCurrentUser()
        this.user = freshUser
        localStorage.setItem('user', JSON.stringify(freshUser))
      } catch (error) {
        const savedUser = localStorage.getItem('user')

        if (savedUser) {
          try {
            this.user = JSON.parse(savedUser)
          } catch (parseError) {
            this.user = { role: '' }
          }
        }
      }
    }

    await this.loadSchedule()
  },
  methods: {
    async handleLogout() {
      this.menuOpen = false
      await logoutUser()
      this.$router.replace('/login')
    },
    openMenu() {
      this.menuOpen = true
    },
    closeMenu() {
      this.menuOpen = false
    },
    goToProfile() {
      this.menuOpen = false
      this.$router.push('/cabinet')
    },
    clearScheduleNotice() {
      this.scheduleNotice = ''
    },
    async prevMonth() {
      this.clearScheduleNotice()
      this.currentMonth = new Date(
        this.currentMonth.getFullYear(),
        this.currentMonth.getMonth() - 1,
        1
      )

      await this.loadSchedule({ isMonthSwitching: true })
    },
    async nextMonth() {
      this.clearScheduleNotice()
      this.currentMonth = new Date(
        this.currentMonth.getFullYear(),
        this.currentMonth.getMonth() + 1,
        1
      )

      await this.loadSchedule({ isMonthSwitching: true })
    },
    async loadSchedule({ isMonthSwitching = false, scheduleId = null } = {}) {
      this.scheduleError = ''
      this.isLoadingSchedule = !isMonthSwitching
      this.isMonthSwitching = isMonthSwitching

      try {
        const schedule = await fetchScheduleForMonth({
          monthDate: this.currentMonth,
          user: this.user,
          scheduleId
        })

        this.scheduleRaw = Array.isArray(schedule.entries) ? schedule.entries : []
        this.scheduleExists = Boolean(schedule.scheduleExists)
        this.currentScheduleId = schedule.scheduleId || null
        this.currentScheduleStatus = schedule.scheduleStatus || null
        this.syncSelectedWaiter()
      } catch (error) {
        this.scheduleRaw = []
        this.scheduleExists = false
        this.currentScheduleId = null
        this.currentScheduleStatus = null
        this.scheduleError = error.message || 'Не удалось загрузить расписание'
        this.syncSelectedWaiter()
      } finally {
        this.isLoadingSchedule = false
        this.isMonthSwitching = false
      }
    },
    syncSelectedWaiter() {
      if (this.waiters.length === 0) {
        this.selectedWaiter = ''
        return
      }

      if (this.selectedWaiter) {
        const selectedWaiter = this.waiters.find((item) => item.employee_key === this.selectedWaiter)

        if (selectedWaiter && !this.canSelectWaiter(selectedWaiter)) {
          this.selectedWaiter = ''
        }
      }

      const hasSelectedWaiter = this.waiters.some(
        (item) => item.employee_key === this.selectedWaiter
      )

      if (hasSelectedWaiter) {
        return
      }

      if (this.isWaiterView && this.pinnedWaiterKey) {
        const pinnedWaiter = this.waiters.find((item) => item.employee_key === this.pinnedWaiterKey)

        if (pinnedWaiter && this.canSelectWaiter(pinnedWaiter)) {
          this.selectedWaiter = this.pinnedWaiterKey
          return
        }
      }

      const firstAllowedWaiter = this.waiters.find((item) => this.canSelectWaiter(item))
      this.selectedWaiter = firstAllowedWaiter?.employee_key || ''
    },
    selectWaiter(employeeKey) {
      if (!employeeKey) {
        return
      }

      const waiter = this.waiters.find((item) => item.employee_key === employeeKey)

      if (waiter && !this.canSelectWaiter(waiter)) {
        return
      }

      this.selectedWaiter = employeeKey
    },
    async handleCreateSchedule() {
      if (this.isGeneratingSchedule) {
        return
      }

      this.isGeneratingSchedule = true
      this.scheduleError = ''
      this.scheduleNotice = ''

      try {
        const response = await generateSchedule({
          user: this.user,
          monthDate: this.currentMonth
        })

        const scheduleId = response?.schedule_id || response?.scheduleId || null
        const slotsCount = Number(response?.slots_count)
        const entriesCount = Number(response?.entries_count)

        if (scheduleId) {
          await this.loadSchedule({ scheduleId })
        } else {
          await this.loadSchedule()
        }

        const parts = ['Черновик расписания создан']

        if (Number.isFinite(slotsCount)) {
          parts.push(`слотов: ${slotsCount}`)
        }

        if (Number.isFinite(entriesCount)) {
          parts.push(`назначений: ${entriesCount}`)
        }

        this.scheduleNotice = parts.join(', ') + '.'
      } catch (error) {
        this.scheduleError = error.message || 'Не удалось создать расписание'
      } finally {
        this.isGeneratingSchedule = false
      }
    },
    async handlePublishSchedule() {
      if (this.isPublishingSchedule || !this.currentScheduleId) {
        return
      }

      this.isPublishingSchedule = true
      this.scheduleError = ''
      this.scheduleNotice = ''

      try {
        await publishSchedule({
          scheduleId: this.currentScheduleId,
          monthDate: this.currentMonth
        })

        await this.loadSchedule({ scheduleId: this.currentScheduleId })
        this.scheduleNotice = 'Расписание опубликовано.'
      } catch (error) {
        this.scheduleError = error.message || 'Не удалось опубликовать расписание'
      } finally {
        this.isPublishingSchedule = false
      }
    },
    buildCalendarDay(date, isCurrentMonth) {
      const key = this.formatDateKey(date)
      const today = new Date()

      return {
        key,
        date,
        isCurrentMonth,
        isToday:
          date.getFullYear() === today.getFullYear() &&
          date.getMonth() === today.getMonth() &&
          date.getDate() === today.getDate(),
        shift: this.selectedWaiterScheduleMap[key] || null,
        hasOpenSlots: Boolean(this.openSlotsMap[key])
      }
    },
    formatDateKey(date) {
      const year = date.getFullYear()
      const month = String(date.getMonth() + 1).padStart(2, '0')
      const day = String(date.getDate()).padStart(2, '0')
      return `${year}-${month}-${day}`
    },
    getFallbackEmployeeLabel(item) {
      if (item.waiter_num || item.waiter_num === 0) {
        return `Официант ${item.waiter_num}`
      }

      return item.employee_key ? `Сотрудник ${item.employee_key}` : 'Сотрудник'
    },
    getWaiterMeta(waiter) {
      const parts = []

      if (waiter.waiter_num || waiter.waiter_num === 0) {
        parts.push(`#${waiter.waiter_num}`)
      }

      const gradeLabel = this.getGradeLabel(waiter.grade)

      if (gradeLabel) {
        parts.push(gradeLabel)
      }

      return parts.join(' · ') || 'Официант'
    },
    getGradeLabel(grade) {
      const normalizedGrade = String(grade || '').toLowerCase()

      if (normalizedGrade === 'employee_noob') {
        return 'Стажер'
      }

      if (normalizedGrade === 'employee_pro') {
        return 'Профи'
      }

      return ''
    },
    canSelectWaiter(waiter) {
      if (!waiter) {
        return false
      }

      if (!this.isWaiterView) {
        return true
      }

      const currentGrade = String(this.currentWaiterGrade || '').toLowerCase()
      const waiterGrade = String(waiter.grade || '').toLowerCase()

      if (currentGrade !== 'employee_noob' && currentGrade !== 'employee_pro') {
        return true
      }

      if (!waiterGrade) {
        return true
      }

      return waiterGrade === currentGrade
    },
    getWaiterColor(employeeKey) {
      const key = String(employeeKey || '')
      const hash = key.split('').reduce((accumulator, char) => accumulator + char.charCodeAt(0), 0)

      return WAITER_COLORS[hash % WAITER_COLORS.length]
    },
    getShiftLabel(shiftType) {
      const map = {
        morning: 'Утро',
        evening: 'Вечер',
        full: 'Полный',
        off: 'Выходной',
        shift: 'Смена'
      }

      return map[shiftType] || shiftType || ''
    },
    getWaiterButtonStyle(waiter) {
      if (waiter.employee_key !== this.selectedWaiter) {
        return {}
      }

      return {
        borderColor: waiter.color,
        boxShadow: `0 0 0 1px ${waiter.color} inset`
      }
    },
    getDayStyle(day) {
      if (day.shift) {
        return {
          backgroundColor: this.selectedWaiterInfo?.color || this.getWaiterColor(this.selectedWaiter),
          color: '#ffffff'
        }
      }

      if (day.hasOpenSlots) {
        return {
          backgroundColor: 'rgba(73, 209, 125, 0.16)',
          color: '#ffffff'
        }
      }

      return {}
    }
  }
}
</script>
