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
          <button class="side-menu-close" @click="closeMenu">✕</button>
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
          <button class="menu-button" @click="openMenu">
            <span></span>
            <span></span>
            <span></span>
          </button>

          <div class="forecast-heading">
            <p class="forecast-subtitle">График работы</p>
            <h1 class="forecast-title">Расписание</h1>
          </div>
        </div>

        <div v-if="isLoadingSchedule" class="schedule-status-card">
          <p class="empty-state-title">Загружаем расписание</p>
          <p class="empty-state-text">
            Подтягиваем смены из базы за выбранный месяц.
          </p>
        </div>

        <div v-else-if="scheduleError" class="schedule-status-card is-error">
          <p class="empty-state-title">Не удалось загрузить расписание</p>
          <p class="empty-state-text">{{ scheduleError }}</p>
          <button class="create-schedule-button secondary-action-button" @click="loadSchedule">
            Повторить
          </button>
        </div>

        <div v-else-if="showCreateScheduleButton" class="manager-empty-state">
          <div>
            <p class="empty-state-title">Расписание пока не создано</p>
            <p class="empty-state-text">
              В базе нет расписания на выбранный месяц. Можно запустить
              автогенерацию прямо с этого экрана.
            </p>
          </div>
          <button
            class="create-schedule-button"
            :disabled="isGeneratingSchedule"
            @click="handleCreateSchedule"
          >
            {{ isGeneratingSchedule ? 'Создаем...' : 'Создать расписание' }}
          </button>
        </div>

        <div v-else-if="!hasSchedule" class="manager-empty-state">
          <div>
            <p class="empty-state-title">Расписание на текущий месяц ещё не создано</p>
            <p class="empty-state-text">
              За выбранный период в базе пока нет доступных назначений.
            </p>
          </div>
        </div>

        <template v-else>
          <div class="month-switcher">
            <button class="month-button" :disabled="isMonthSwitching" @click="prevMonth">‹</button>
            <div class="month-label">{{ monthTitle }}</div>
            <button class="month-button" :disabled="isMonthSwitching" @click="nextMonth">›</button>
          </div>

          <div v-if="waiters.length > 0">
            <div class="forecast-controls">
              <div class="waiter-selector-card">
                <label class="selector-label" for="waiterSelect">Выбери сотрудника</label>
                <select
                  id="waiterSelect"
                  class="selector-input"
                  v-model="selectedWaiter"
                >
                  <option
                    v-for="waiter in waiters"
                    :key="waiter.employee_key"
                    :value="waiter.employee_key"
                  >
                    {{ waiter.label }}
                  </option>
                </select>
              </div>

              <div v-if="selectedWaiterInfo" class="selected-waiter-card">
                <div class="selected-waiter-head">
                  <span
                    class="waiter-color-dot"
                    :style="{ backgroundColor: selectedWaiterInfo.color }"
                  ></span>
                  <span class="selected-waiter-name">
                    {{ selectedWaiterInfo.label }}
                  </span>
                </div>

                <div class="selected-waiter-meta">
                  Уровень:
                  <strong>{{ selectedWaiterInfo.grade || 'не указан' }}</strong>
                </div>
              </div>
            </div>
          </div>

          <div v-if="waiters.length > 0" class="waiter-legend">
            <div
              v-for="waiter in waiters"
              :key="waiter.employee_key"
              class="legend-item"
              :class="{ active: waiter.employee_key === selectedWaiter }"
              @click="selectedWaiter = waiter.employee_key"
            >
              <span
                class="legend-color"
                :style="{ backgroundColor: waiter.color }"
              ></span>
              <span class="legend-text">{{ waiter.label }}</span>
            </div>
          </div>

          <div v-else class="schedule-status-card">
            <p class="empty-state-title">Расписание создано, но сотрудники ещё не назначены</p>
            <p class="empty-state-text">
              Ниже показаны свободные слоты по дням. Их можно использовать для последующих назначений.
            </p>
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
                  'has-open-slots': !day.shift && day.slots.length > 0,
                  'is-today': day.isToday
                }"
                :style="getDayStyle(day)"
              >
                <div class="day-number">{{ day.date.getDate() }}</div>

                <template v-if="day.shift">
                  <div class="shift-badge">
                    {{ getShiftLabel(day.shift.shift_type) }}
                  </div>

                  <div
                    v-if="day.shift.work_start && day.shift.work_end"
                    class="shift-time"
                  >
                    {{ day.shift.work_start }}–{{ day.shift.work_end }}
                  </div>

                  <div v-else-if="day.shift.work_hours" class="shift-time">
                    {{ day.shift.work_hours }} ч
                  </div>
                </template>

                <template v-else-if="day.slots.length > 0">
                  <div class="shift-badge open-slot-badge">
                    {{ getOpenSlotsLabel(day.slots.length) }}
                  </div>

                  <div class="shift-time">
                    {{ formatOpenSlots(day.slots) }}
                  </div>
                </template>
              </div>
            </div>
          </div>
        </template>
      </section>
    </main>
  </div>
</template>

<script>
import '../assets/forecast.css'
import { fetchCurrentUser, logoutUser } from '../services/auth'
import { fetchScheduleForMonth, generateSchedule } from '../services/schedule'

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

export default {
  name: 'ForeCastView',
  data() {
    return {
      menuOpen: false,
      currentMonth: new Date(new Date().getFullYear(), new Date().getMonth(), 1),
      selectedWaiter: '',
      weekdays: ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'],
      scheduleRaw: [],
      scheduleExists: false,
      scheduleError: '',
      isLoadingSchedule: false,
      isMonthSwitching: false,
      isGeneratingSchedule: false,
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
    canManageSchedule() {
      return ['manager', 'admin'].includes(String(this.user.role || '').toLowerCase())
    },
    hasSchedule() {
      return this.scheduleExists
    },
    showCreateScheduleButton() {
      return this.canManageSchedule && !this.hasSchedule
    },
    workingSchedule() {
      return this.scheduleRaw.filter(
        (item) => item.is_working === true && item.employee_key
      )
    },
    waiters() {
      const grouped = new Map()

      this.workingSchedule.forEach((item) => {
        if (!grouped.has(item.employee_key)) {
          grouped.set(item.employee_key, {
            employee_key: item.employee_key,
            waiter_num: item.waiter_num,
            label: item.employee_label || this.getFallbackEmployeeLabel(item),
            grade: item.grade || null,
            color: this.getWaiterColor(item.employee_key)
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
    selectedWaiterScheduleMap() {
      const map = {}

      this.workingSchedule
        .filter((item) => item.employee_key === this.selectedWaiter)
        .forEach((item) => {
          map[item.date] = item
        })

      return map
    },
    dailyScheduleMap() {
      const map = {}

      this.scheduleRaw
        .filter((item) => item.date && item.is_working === true && !item.employee_key)
        .forEach((item) => {
          if (!map[item.date]) {
            map[item.date] = []
          }

          map[item.date].push(item)
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
        const date = new Date(year, month, 1 - i)
        result.push(this.buildCalendarDay(date, false))
      }

      for (let day = 1; day <= daysInMonth; day++) {
        const date = new Date(year, month, day)
        result.push(this.buildCalendarDay(date, true))
      }

      const rest = result.length % 7
      if (rest !== 0) {
        const need = 7 - rest
        for (let i = 1; i <= need; i++) {
          const date = new Date(year, month + 1, i)
          result.push(this.buildCalendarDay(date, false))
        }
      }

      return result
    }
  },
  async mounted() {
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
    async prevMonth() {
      this.currentMonth = new Date(
        this.currentMonth.getFullYear(),
        this.currentMonth.getMonth() - 1,
        1
      )

      await this.loadSchedule({ isMonthSwitching: true })
    },
    async nextMonth() {
      this.currentMonth = new Date(
        this.currentMonth.getFullYear(),
        this.currentMonth.getMonth() + 1,
        1
      )

      await this.loadSchedule({ isMonthSwitching: true })
    },
    async loadSchedule({ isMonthSwitching = false } = {}) {
      this.scheduleError = ''
      this.isLoadingSchedule = !isMonthSwitching
      this.isMonthSwitching = isMonthSwitching

      try {
        const schedule = await fetchScheduleForMonth({
          monthDate: this.currentMonth,
          user: this.user
        })

        this.scheduleRaw = Array.isArray(schedule.entries) ? schedule.entries : []
        this.scheduleExists = Boolean(schedule.scheduleExists)
        this.syncSelectedWaiter()
      } catch (error) {
        this.scheduleRaw = []
        this.scheduleExists = false
        this.selectedWaiter = ''
        this.scheduleError = error.message || 'Не удалось загрузить расписание'
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

      const hasSelectedWaiter = this.waiters.some(
        (item) => item.employee_key === this.selectedWaiter
      )

      if (!hasSelectedWaiter) {
        this.selectedWaiter = this.waiters[0].employee_key
      }
    },
    async handleCreateSchedule() {
      if (this.isGeneratingSchedule) {
        return
      }

      this.isGeneratingSchedule = true

      try {
        const response = await generateSchedule({ user: this.user })
        const createdCount = Number(response?.created)
        const successMessage = Number.isFinite(createdCount)
          ? `Расписание создано. Новых смен: ${createdCount}.`
          : 'Генерация расписания запущена.'

        await this.loadSchedule()
        window.alert(successMessage)
      } catch (error) {
        window.alert(error.message || 'Не удалось создать расписание')
      } finally {
        this.isGeneratingSchedule = false
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
        slots: this.dailyScheduleMap[key] || []
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
    getWaiterColor(employeeKey) {
      const key = String(employeeKey || '')
      const hash = key.split('').reduce((accumulator, char) => {
        return accumulator + char.charCodeAt(0)
      }, 0)

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
    getOpenSlotsLabel(count) {
      if (count === 1) {
        return '1 слот'
      }

      if (count >= 2 && count <= 4) {
        return `${count} слота`
      }

      return `${count} слотов`
    },
    formatOpenSlots(slots) {
      const preview = slots
        .slice(0, 2)
        .map((slot) => {
          if (slot.work_start && slot.work_end) {
            return `${slot.work_start}–${slot.work_end}`
          }

          if (slot.work_hours) {
            return `${slot.work_hours} ч`
          }

          return this.getShiftLabel(slot.shift_type)
        })
        .filter(Boolean)
        .join(', ')

      if (slots.length > 2) {
        return `${preview} и еще ${slots.length - 2}`
      }

      return preview || 'Без назначений'
    },
    getDayStyle(day) {
      if (!day.shift) {
        if (day.slots.length > 0 && this.waiters.length === 0) {
          return {
            backgroundColor: 'rgba(73, 209, 125, 0.18)',
            color: '#ffffff'
          }
        }

        return {}
      }

      return {
        backgroundColor: this.selectedWaiterInfo?.color || this.getWaiterColor(this.selectedWaiter),
        color: '#ffffff'
      }
    }
  }
}
</script>
