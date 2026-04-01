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

<div v-if="canManageSchedule" class="manager-empty-state">
  <div>
    <p class="empty-state-title">Расписание пока не создано</p>
  </div>
  <button class="create-schedule-button" @click="handleCreateSchedule">
    Создать расписание
  </button>
</div>

<div v-else-if="showWaiterEmptyState" class="waiter-empty-state">
  <p class="empty-state-title">Расписание на текущий месяц ещё не создано</p>
</div>

        <template v-if="hasSchedule">
          <div class="month-switcher">
            <button class="month-button" @click="prevMonth">‹</button>
            <div class="month-label">{{ monthTitle }}</div>
            <button class="month-button" @click="nextMonth">›</button>
          </div>

          <div class="forecast-controls">
            <div class="waiter-selector-card">
              <label class="selector-label" for="waiterSelect">Выбери официанта</label>
              <select
                id="waiterSelect"
                class="selector-input"
                v-model.number="selectedWaiter"
              >
                <option
                  v-for="waiter in waiters"
                  :key="waiter.waiter_num"
                  :value="waiter.waiter_num"
                >
                  Официант {{ waiter.waiter_num }}
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
                  Официант {{ selectedWaiterInfo.waiter_num }}
                </span>
              </div>

              <div class="selected-waiter-meta">
                Уровень:
                <strong>{{ selectedWaiterInfo.grade || 'не указан' }}</strong>
              </div>
            </div>
          </div>

          <div class="waiter-legend">
            <div
              v-for="waiter in waiters"
              :key="waiter.waiter_num"
              class="legend-item"
              :class="{ active: waiter.waiter_num === selectedWaiter }"
              @click="selectedWaiter = waiter.waiter_num"
            >
              <span
                class="legend-color"
                :style="{ backgroundColor: waiter.color }"
              ></span>
              <span class="legend-text">Официант {{ waiter.waiter_num }}</span>
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

const MOCK_SCHEDULE = []

export default {
  name: 'ForeCastView',
data() {
  return {
    menuOpen: false,
    currentMonth: new Date(new Date().getFullYear(), new Date().getMonth(), 1),
    selectedWaiter: null,
    weekdays: ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'],
    scheduleRaw: MOCK_SCHEDULE,
    user: (() => {
      try {
        return JSON.parse(localStorage.getItem('user')) || { role: '' }
      } catch (e) {
        return { role: '' }
      }
    })()
  }
},
  computed: {
    isManager() {
      return ['MANAGER', 'manager'].includes(this.user.role)
    },
      isAdmin() {
    return String(this.user.role || '').toUpperCase() === 'ADMIN'
  },
  canManageSchedule() {
    const role = String(this.user.role || '').toUpperCase()
    return role === 'MANAGER' || role === 'ADMIN'
  },
    hasSchedule() {
      return this.workingSchedule.length > 0
    },
    showCreateScheduleButton() {
      return this.isManager && !this.hasSchedule
    },
    showWaiterEmptyState() {
  return !this.isManager && !this.hasSchedule
},
    workingSchedule() {
      return this.scheduleRaw.filter(item => item.is_working === true)
    },

    waiters() {
      const grouped = new Map()

      this.workingSchedule.forEach(item => {
        if (!grouped.has(item.waiter_num)) {
          grouped.set(item.waiter_num, {
            waiter_num: item.waiter_num,
            grade: item.grade || null,
            color: this.getWaiterColor(item.waiter_num)
          })
        }
      })

      return Array.from(grouped.values()).sort((a, b) => a.waiter_num - b.waiter_num)
    },

    selectedWaiterInfo() {
      return this.waiters.find(item => item.waiter_num === this.selectedWaiter) || null
    },

    selectedWaiterScheduleMap() {
      const map = {}

      this.workingSchedule
        .filter(item => item.waiter_num === this.selectedWaiter)
        .forEach(item => {
          map[item.date] = item
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
        this.user = JSON.parse(savedUser)
      }
    }

    if (this.waiters.length > 0) {
      this.selectedWaiter = this.waiters[0].waiter_num
    }
  },

  methods: {
    handleLogout() {
  this.menuOpen = false
  logoutUser()
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

    prevMonth() {
      this.currentMonth = new Date(
        this.currentMonth.getFullYear(),
        this.currentMonth.getMonth() - 1,
        1
      )
    },

    nextMonth() {
      this.currentMonth = new Date(
        this.currentMonth.getFullYear(),
        this.currentMonth.getMonth() + 1,
        1
      )
    },

    handleCreateSchedule() {
      window.alert('Эндпоинт создания расписания пока не подключен. Кнопка перенесена на страницу расписания и показывается только при его отсутствии.')
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
        shift: this.selectedWaiterScheduleMap[key] || null
      }
    },

    formatDateKey(date) {
      const year = date.getFullYear()
      const month = String(date.getMonth() + 1).padStart(2, '0')
      const day = String(date.getDate()).padStart(2, '0')
      return `${year}-${month}-${day}`
    },

    getWaiterColor(waiterNum) {
      return WAITER_COLORS[(waiterNum - 1) % WAITER_COLORS.length]
    },

    getShiftLabel(shiftType) {
      const map = {
        morning: 'Утро',
        evening: 'Вечер',
        full: 'Полный',
        off: 'Выходной'
      }

      return map[shiftType] || shiftType || ''
    },

    getDayStyle(day) {
      if (!day.shift) {
        return {}
      }

      return {
        backgroundColor: this.getWaiterColor(this.selectedWaiter),
        color: '#ffffff'
      }
    }
  }
}
</script>