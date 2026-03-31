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
      </aside>
    </transition>

    <header class="forecast-header">
      <div class="menu-container">
        <button class="menu-button" @click="openMenu" aria-label="Открыть меню">
          <span></span>
          <span></span>
          <span></span>
        </button>
      </div>
    </header>

    <main class="forecast-content">
      <section class="forecast-card">
        <div class="forecast-card-top">
          <div class="forecast-heading">
            <p class="forecast-subtitle">График работы</p>
            <h1 class="forecast-title">Расписание</h1>
          </div>
        </div>

        <div class="month-switcher">
          <button class="month-button" @click="prevMonth">‹</button>
          <div class="month-label">{{ monthTitle }}</div>
          <button class="month-button" @click="nextMonth">›</button>
        </div>

        <div class="waiter-picker">
          <button
            v-for="waiter in waiters"
            :key="waiter.waiter_num"
            class="waiter-chip"
            :class="{ active: waiter.waiter_num === selectedWaiter }"
            @click="selectedWaiter = waiter.waiter_num"
          >
            <span
              class="waiter-chip-color"
              :style="{ backgroundColor: waiter.color }"
            ></span>

            <span class="waiter-chip-text">
              <span class="waiter-chip-name">Официант {{ waiter.waiter_num }}</span>
              <span class="waiter-chip-grade">
                {{ waiter.grade || 'Не указан' }}
              </span>
            </span>
          </button>
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
<div class="shift-text">
  {{ getShiftLabel(day.shift.shift_type) }}
</div>
</template>
            </div>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>

<script>
import '../assets/forecast.css'

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
      selectedWaiter: 1,
      weekdays: ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'],

      scheduleRaw: [
        { date: '2026-03-02', waiter_num: 1, is_working: true, shift_type: 'morning', waiters_needed: 2, work_start: '09:00', work_end: '17:00', work_hours: 8, grade: 'Стажёр' },
        { date: '2026-03-03', waiter_num: 1, is_working: true, shift_type: 'morning', waiters_needed: 2, work_start: '09:00', work_end: '17:00', work_hours: 8, grade: 'Стажёр' },
        { date: '2026-03-05', waiter_num: 1, is_working: true, shift_type: 'evening', waiters_needed: 2, work_start: '15:00', work_end: '23:00', work_hours: 8, grade: 'Стажёр' },
        { date: '2026-03-08', waiter_num: 1, is_working: true, shift_type: 'full', waiters_needed: 2, work_start: '10:00', work_end: '22:00', work_hours: 12, grade: 'Стажёр' },
        { date: '2026-03-11', waiter_num: 1, is_working: true, shift_type: 'morning', waiters_needed: 2, work_start: '09:00', work_end: '17:00', work_hours: 8, grade: 'Стажёр' },

        { date: '2026-03-04', waiter_num: 2, is_working: true, shift_type: 'full', waiters_needed: 2, work_start: '10:00', work_end: '22:00', work_hours: 12, grade: 'Опытный' },
        { date: '2026-03-06', waiter_num: 2, is_working: true, shift_type: 'morning', waiters_needed: 2, work_start: '09:00', work_end: '17:00', work_hours: 8, grade: 'Опытный' },
        { date: '2026-03-09', waiter_num: 2, is_working: true, shift_type: 'evening', waiters_needed: 2, work_start: '15:00', work_end: '23:00', work_hours: 8, grade: 'Опытный' },
        { date: '2026-03-13', waiter_num: 2, is_working: true, shift_type: 'full', waiters_needed: 2, work_start: '10:00', work_end: '22:00', work_hours: 12, grade: 'Опытный' },

        { date: '2026-03-01', waiter_num: 3, is_working: true, shift_type: 'evening', waiters_needed: 2, work_start: '15:00', work_end: '23:00', work_hours: 8, grade: 'Опытный' },
        { date: '2026-03-07', waiter_num: 3, is_working: true, shift_type: 'full', waiters_needed: 2, work_start: '10:00', work_end: '22:00', work_hours: 12, grade: 'Опытный' },
        { date: '2026-03-10', waiter_num: 3, is_working: true, shift_type: 'morning', waiters_needed: 2, work_start: '09:00', work_end: '17:00', work_hours: 8, grade: 'Опытный' },
        { date: '2026-03-14', waiter_num: 3, is_working: true, shift_type: 'evening', waiters_needed: 2, work_start: '15:00', work_end: '23:00', work_hours: 8, grade: 'Опытный' }
      ]
    }
  },

  computed: {
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

  mounted() {
    if (this.waiters.length > 0) {
      this.selectedWaiter = this.waiters[0].waiter_num
    }
  },

  methods: {
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
    evening: 'Веч.',
    full: 'Полный',
    off: 'Вых.'
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