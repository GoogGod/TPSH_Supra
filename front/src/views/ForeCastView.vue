<template>
  <div class="forecast-page" :class="{ 'is-handheld': isHandheldDevice }">
    <transition name="menu-overlay">
      <div v-if="menuOpen" class="side-menu-overlay" @click="closeMenu"></div>
    </transition>

    <transition name="side-menu">
      <aside v-if="menuOpen" class="side-menu">
        <div class="side-menu-top">
          <button class="side-menu-close" @click="closeMenu">&times;</button>
        </div>
        <div class="side-menu-section">
          <button class="side-menu-item" @click="goToProfile">Профиль</button>
          <button class="side-menu-item active" @click="closeMenu">Расписание</button>
        </div>
        <div class="side-menu-footer">
          <button class="side-menu-item side-menu-item-danger" @click="handleLogout">Выйти</button>
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
          <NotificationBell @updated="handleNotificationsUpdated" />
        </div>

        <div class="month-toolbar">
          <div class="month-switcher">
            <button class="month-button" :disabled="isMonthSwitching" @click="prevMonth">‹</button>
            <div class="month-label">{{ monthTitle }}</div>
            <button class="month-button" :disabled="isMonthSwitching" @click="nextMonth">›</button>
          </div>
          <button v-if="canManageSchedule" class="create-schedule-button" :disabled="isGeneratingSchedule" @click="handleCreateSchedule">
            {{ isGeneratingSchedule ? 'Создаем...' : 'Создать расписание' }}
          </button>
        </div>

        <div class="schedule-info-row">
          <div v-if="scheduleNotice" class="schedule-status-card is-success">{{ scheduleNotice }}</div>
          <div v-else-if="isLoadingSchedule" class="schedule-status-card">Загружаем расписание...</div>
          <div v-else-if="scheduleError" class="schedule-status-card is-error">{{ scheduleError }}</div>
          <div v-else-if="!hasSchedule" class="schedule-status-card">На этот месяц расписание пока не создано</div>
          <div v-else class="schedule-status-card is-soft">{{ roleHint }}</div>
        </div>

        <article v-if="staffShortageSummary" class="schedule-shortage-card">
          <div class="schedule-shortage-head">
            <span class="schedule-shortage-badge">Нехватка персонала</span>
            <strong class="schedule-shortage-value">
              {{ staffShortageSummary.shortage }}
            </strong>
          </div>
          <p class="schedule-shortage-copy">
            Сейчас в заведении доступно {{ staffShortageSummary.available }} сотрудников, а в пиковый момент нужно {{ staffShortageSummary.required }}.
            <span v-if="staffShortageSummary.shortage > 0">
              Не хватает {{ staffShortageSummary.shortage }} {{ getShortageUnitLabel(staffShortageSummary.shortage) }}.
            </span>
            <span v-else>
              Нехватки персонала нет.
            </span>
          </p>
        </article>

        <div v-if="scheduleMetrics.length" class="schedule-metrics-grid">
          <article v-for="metric in scheduleMetrics" :key="metric.key" class="schedule-metric-card">
            <span class="schedule-metric-label">{{ metric.label }}</span>
            <strong class="schedule-metric-value">{{ metric.value }}</strong>
          </article>
        </div>

        <div class="waiter-picker-card">
          <div class="waiter-picker-head">
            <h2>Места</h2>
            <p class="waiter-picker-description-desktop">{{ selectorDescription }}</p>
            <button
              v-if="useMobileSelectorInfo"
              class="waiter-picker-info-button"
              type="button"
              :aria-expanded="showMobileSelectorInfo ? 'true' : 'false'"
              @click="showMobileSelectorInfo = !showMobileSelectorInfo"
            >
              i
            </button>
          </div>
          <div v-if="useMobileSelectorInfo && showMobileSelectorInfo" class="waiter-picker-info-mobile">
            {{ selectorDescription }}
          </div>
          <div v-if="waiters.length === 0" class="waiter-empty-state">Нет доступных мест для отображения</div>
          <div v-else class="waiter-button-list">
            <button
              v-for="waiter in waiters"
              :key="waiter.slot_position_key"
              class="waiter-button"
              :class="{ active: waiter.slot_position_key === selectedWaiter, disabled: !canSelectWaiter(waiter) }"
              :style="getWaiterButtonStyle(waiter)"
              :disabled="!canSelectWaiter(waiter)"
              @click="selectWaiter(waiter.slot_position_key)"
            >
              <span class="waiter-button-name">{{ waiter.label }}</span>
              <span class="waiter-button-meta">{{ getWaiterMeta(waiter) }}</span>
            </button>
          </div>

        </div>

        <section v-if="canEditSelectedWaiterSchedule" class="schedule-editor-card">
          <div class="schedule-editor-head">
            <div>
              <p class="schedule-editor-subtitle">Черновик</p>
              <h2 class="schedule-editor-title">Редактирование места {{ selectedWaiterInfo?.label }}</h2>
            </div>
            <button class="claim-slot-button schedule-editor-save" :disabled="!hasPendingScheduleEdits || isSavingDraft" @click="saveDraftEdits">
              {{ isSavingDraft ? 'Сохраняем...' : 'Сохранить изменения' }}
            </button>
          </div>
          <p class="schedule-editor-copy">Меняйте рабочие дни, тип смены, время и нужное количество официантов.</p>
          <div v-if="editableEntries.length === 0" class="waiter-empty-state">Для выбранного места нет записей для редактирования.</div>
          <div v-else class="schedule-editor-list">
            <article v-for="(entry, index) in editableEntries" :key="entry.entry_id || `${entry.date}-${index}`" class="schedule-editor-entry">
              <div class="schedule-editor-entry-top">
                <div>
                  <strong>{{ formatEntryDate(entry.date) }}</strong>
                  <p>{{ entry.is_working ? getShiftLabel(entry.shift_type) : 'Выходной день' }}</p>
                </div>
                <label class="schedule-editor-check">
                  <input v-model="entry.is_working" type="checkbox" @change="handleEditableWorkingToggle(entry)" />
                  <span>Рабочий день</span>
                </label>
              </div>
              <div class="schedule-editor-grid">
                <label class="schedule-editor-field">
                  <span>Тип смены</span>
                  <ThemedSelect
                    v-model="entry.shift_type"
                    :options="shiftTypeOptions"
                    :disabled="!entry.is_working"
                    placeholder="Тип смены"
                  />
                </label>
                <label class="schedule-editor-field">
                  <span>Нужно официантов</span>
                  <input v-model.number="entry.waiters_needed" type="number" min="0" step="1" :disabled="!entry.is_working" />
                </label>
                <label class="schedule-editor-field">
                  <span>Начало</span>
                  <input v-model="entry.work_start" type="time" :disabled="!entry.is_working" @change="handleEditableTimeChange(index)" />
                </label>
                <label class="schedule-editor-field">
                  <span>Конец</span>
                  <input v-model="entry.work_end" type="time" :disabled="!entry.is_working" @change="handleEditableTimeChange(index)" />
                </label>
                <label class="schedule-editor-field schedule-editor-field-wide">
                  <span>Часы</span>
                  <input v-model.number="entry.work_hours" type="number" min="0" step="0.5" :disabled="!entry.is_working" />
                </label>
              </div>
            </article>
          </div>
          <div class="schedule-editor-actions">
            <button class="unassign-slot-button" :disabled="!hasPendingScheduleEdits || isSavingDraft" @click="resetEditableEntries">Сбросить</button>
            <button class="claim-slot-button" :disabled="!hasPendingScheduleEdits || isSavingDraft" @click="saveDraftEdits">{{ isSavingDraft ? 'Сохраняем...' : 'Сохранить изменения' }}</button>
          </div>
        </section>

        <div class="calendar-card">
          <div class="calendar-weekdays">
            <div v-for="weekday in weekdays" :key="weekday" class="weekday-cell">{{ weekday }}</div>
          </div>
          <div class="calendar-grid">
            <div
              v-for="day in calendarDays"
              :key="day.key"
              class="calendar-cell"
              :class="{ 'outside-month': !day.isCurrentMonth, 'is-working': !!day.shift, 'is-open-slot': !day.shift && day.hasOpenSlots, 'is-today': day.isToday, 'is-selected-waiter': !!day.shift }"
              :style="getDayStyle(day)"
            >
              <div class="day-number">{{ day.date.getDate() }}</div>
              <div v-if="day.shift" class="day-shift-mark">
                <span class="shift-chip">
                  <span class="shift-chip-full">{{ getShiftLabel(day.shift.shift_type) }}</span>
                  <span class="shift-chip-short">{{ getShiftShortLabel(day.shift.shift_type) }}</span>
                </span>
                <span v-if="day.shift.work_start && day.shift.work_end" class="shift-caption">
                  <span>{{ day.shift.work_start }}</span>
                  <span>{{ day.shift.work_end }}</span>
                </span>
              </div>
              <div v-else-if="day.hasOpenSlots" class="day-open-mark"><span class="shift-chip open-slot-chip">Есть смены</span></div>
            </div>
          </div>
        </div>

        <div v-if="canPublishCurrentSchedule" class="bottom-actions bottom-actions-single">
          <button class="publish-schedule-button" :disabled="isPublishingSchedule" @click="handlePublishSchedule">{{ isPublishingSchedule ? 'Публикуем...' : 'Опубликовать' }}</button>
        </div>

        <div v-if="selectedWaiterInfo" class="slot-actions-card slot-actions-card-bottom">
          <p class="slot-actions-title">{{ selectedWaiterInfo.label }}</p>
          <p class="slot-actions-caption">{{ selectedWaiterCaption }}</p>
          <div v-if="isWaiterView" class="slot-actions-buttons slot-actions-buttons-single">
            <button class="claim-slot-button" :disabled="!canClaimSelectedWaiter || isClaimingSlot" @click="handleClaimSelectedWaiter">
              {{ isClaimingSlot ? 'Закрепляем...' : 'Закрепиться' }}
            </button>
          </div>
          <div v-else class="slot-actions-buttons">
            <button class="claim-slot-button" :disabled="!canOpenAssignPanel || isAssigningSlot || isUnassigningSlot" @click="openAssignPanel">Закрепить</button>
            <button class="unassign-slot-button" :disabled="!canUnassignSelectedWaiter || isUnassigningSlot || isAssigningSlot" @click="handleUnassignSelectedWaiter">
              {{ isUnassigningSlot ? 'Открепляем...' : 'Открепить' }}
            </button>
          </div>
          <div v-if="showAssignPanel && canManageSchedule" class="assign-panel">
            <label class="assign-panel-field">
              <span>Выберите сотрудника</span>
              <ThemedSelect
                v-model="selectedEmployeeToAssign"
                :options="assignableEmployeeOptions"
                placeholder="Выберите сотрудника"
              />
            </label>
            <div class="assign-panel-actions">
              <button class="claim-slot-button" :disabled="!selectedEmployeeToAssign || isAssigningSlot" @click="handleAssignSelectedWaiter">{{ isAssigningSlot ? 'Закрепляем...' : 'Подтвердить' }}</button>
              <button class="unassign-slot-button" :disabled="isAssigningSlot" @click="closeAssignPanel">Отмена</button>
            </div>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>

<script>
import '../assets/forecast.css'
import api from '../api'
import NotificationBell from '../components/NotificationBell.vue'
import ThemedSelect from '../components/ThemedSelect.vue'
import { fetchCurrentUser, logoutUser } from '../services/auth'
import { assignScheduleSlot, claimScheduleSlot, fetchScheduleForMonth, generateSchedule, publishSchedule, unassignScheduleSlot, updateScheduleEntriesBulk } from '../services/schedule'

const USE_MOCK_AUTH = import.meta.env.VITE_USE_MOCK_AUTH === 'true'
const WAITER_COLORS = ['#b98597', '#7898c2', '#6f9b97', '#c08d78', '#9487bb', '#b7aa72', '#7ea88a', '#a98bb3']
const SHIFT_LABELS = { morning: 'Утро', evening: 'Вечер', full: 'Полный день', off: 'Выходной', shift: 'Смена' }
const normalizeRole = (role) => String(role || '').toLowerCase()
const normalizeIdentity = (value) => value === undefined || value === null || value === '' ? '' : String(value).toLowerCase()
const asArray = (payload) => Array.isArray(payload) ? payload : Array.isArray(payload?.results) ? payload.results : Array.isArray(payload?.items) ? payload.items : Array.isArray(payload?.data) ? payload.data : []
const getVenueId = (entity) => { const raw = entity?.venue_id ?? entity?.venue?.id ?? entity?.venue; return raw === undefined || raw === null || raw === '' ? null : Number(raw) }
const detectHandheldDevice = () => {
  if (typeof window === 'undefined' || typeof navigator === 'undefined') return false
  const uaDataMobile = navigator.userAgentData?.mobile === true
  const ua = String(navigator.userAgent || '').toLowerCase()
  const mobileUa = /android|iphone|ipod|blackberry|iemobile|opera mini|mobile/.test(ua)
  const coarsePointer =
    window.matchMedia?.('(pointer: coarse)')?.matches ||
    window.matchMedia?.('(any-pointer: coarse)')?.matches ||
    navigator.maxTouchPoints > 0
  return Boolean(uaDataMobile || mobileUa || coarsePointer)
}
const formatTimeForApi = (value) => { const normalized = String(value || '').trim(); return normalized && normalized.length === 5 ? `${normalized}:00` : normalized }
const getHoursDifference = (start, end) => {
  if (!start || !end) return null
  const [sh = '0', sm = '0'] = String(start).split(':')
  const [eh = '0', em = '0'] = String(end).split(':')
  const startTotal = Number(sh) * 60 + Number(sm)
  let endTotal = Number(eh) * 60 + Number(em)
  if (!Number.isFinite(startTotal) || !Number.isFinite(endTotal)) return null
  if (endTotal < startTotal) endTotal += 24 * 60
  return Number(((endTotal - startTotal) / 60).toFixed(2))
}
const buildComparableEntryState = (entry) => ({
  entry_id: Number(entry?.entry_id ?? 0),
  is_working: Boolean(entry?.is_working),
  shift_type: String(entry?.shift_type || '').toLowerCase(),
  waiters_needed: Number(entry?.waiters_needed ?? 0),
  work_start: String(entry?.work_start || ''),
  work_end: String(entry?.work_end || ''),
  work_hours: entry?.work_hours === '' || entry?.work_hours === null || entry?.work_hours === undefined ? null : Number(entry.work_hours)
})

export default {
  name: 'ForeCastView',
  components: { NotificationBell, ThemedSelect },
  data() {
    return {
      menuOpen: false,
      currentMonth: new Date(new Date().getFullYear(), new Date().getMonth(), 1),
      currentScheduleId: null,
      currentScheduleStatus: null,
      selectedWaiter: '',
      selectedEmployeeToAssign: '',
      showAssignPanel: false,
      showMobileSelectorInfo: false,
      isHandheldDevice: detectHandheldDevice(),
      weekdays: ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'],
      scheduleRaw: [],
      scheduleExists: false,
      scheduleError: '',
      scheduleNotice: '',
      latestGenerationSummary: null,
      isLoadingSchedule: false,
      isMonthSwitching: false,
      isGeneratingSchedule: false,
      isPublishingSchedule: false,
      isClaimingSlot: false,
      isUnassigningSlot: false,
      isAssigningSlot: false,
      isSavingDraft: false,
      employees: [],
      editableEntries: [],
      user: (() => { try { return JSON.parse(localStorage.getItem('user')) || { role: '' } } catch (error) { return { role: '' } } })()
    }
  },
  computed: {
    currentUserRole() { return normalizeRole(this.user.role) },
    currentVenueId() { return getVenueId(this.user) },
    canManageSchedule() { return ['manager', 'admin'].includes(this.currentUserRole) },
    useMobileSelectorInfo() { return this.isHandheldDevice },
    isWaiterView() { return !this.canManageSchedule },
    hasSchedule() { return this.scheduleExists },
    isDraftSchedule() { return this.currentScheduleStatus === 'draft' },
    canPublishCurrentSchedule() { return this.canManageSchedule && this.hasSchedule && !!this.currentScheduleId && this.isDraftSchedule },
    roleHint() { return this.canManageSchedule ? (this.isDraftSchedule ? 'Черновик открыт: выберите место, поправьте смены и затем опубликуйте расписание.' : 'Выберите место и управляйте закреплениями сотрудников.') : 'Выберите место и закрепитесь за ним. Официант может быть закреплен только за одним местом.' },
    selectorDescription() { return this.waiters.length === 0 ? 'Кнопки появятся, когда в расписании будут доступные места.' : this.canManageSchedule ? 'Менеджер и админ могут закреплять сотрудников, снимать их и редактировать черновик по выбранному месту.' : 'Доступны только места вашей категории. Закрепиться можно только за одним местом.' },
    workingSchedule() { return this.scheduleRaw.filter((item) => item.is_working === true && item.employee_key) },
    waiters() {
      const grouped = new Map()
      this.workingSchedule.forEach((item) => {
        const slotPositionKey = item.slot_position_key || item.employee_key
        if (!grouped.has(slotPositionKey)) {
          grouped.set(slotPositionKey, {
            slot_position_key: slotPositionKey,
            employee_key: item.employee_key,
            employee_id: item.employee_id,
            assigned_employee_id: item.assigned_employee_id,
            assigned_employee_username: item.assigned_employee_username,
            assigned_employee_name: item.assigned_employee_name,
            slot_id: item.slot_id,
            waiter_num: item.waiter_num,
            label: item.employee_label || this.getFallbackEmployeeLabel(item),
            grade: item.grade || null,
            roleDisplay: item.employee_role_display || '',
            color: this.getWaiterColor(slotPositionKey),
            isClaimed: Boolean(item.assigned_employee_id || item.assigned_employee_name),
            claimedByCurrentUser: this.isCurrentUserAssignment(item),
            identities: [normalizeIdentity(item.employee_key), normalizeIdentity(item.employee_id), normalizeIdentity(item.waiter_num), normalizeIdentity(item.assigned_employee_id), normalizeIdentity(item.assigned_employee_username)].filter(Boolean)
          })
        }
      })
      return Array.from(grouped.values()).sort((left, right) => (left.waiter_num ?? 0) - (right.waiter_num ?? 0))
    },
    selectedWaiterInfo() { return this.waiters.find((item) => item.slot_position_key === this.selectedWaiter) || null },
    pinnedWaiterKey() {
      const ids = [normalizeIdentity(this.user.id), normalizeIdentity(this.user.username), normalizeIdentity(this.user.email), normalizeIdentity(this.user.waiter_num)].filter(Boolean)
      const matched = this.waiters.find((waiter) => waiter.identities.some((identity) => ids.includes(identity)))
      return matched?.slot_position_key || ''
    },
    currentWaiterGrade() { if (this.currentUserRole === 'employee_noob' || this.currentUserRole === 'employee_pro') return this.currentUserRole; return String(this.waiters.find((waiter) => waiter.slot_position_key === this.pinnedWaiterKey)?.grade || '').toLowerCase() },
    currentUserAssignedWaiterKey() { return this.waiters.find((waiter) => waiter.claimedByCurrentUser)?.slot_position_key || '' },
    selectedWaiterEntries() { return this.scheduleRaw.filter((item) => (item.slot_position_key || item.employee_key) === this.selectedWaiter).sort((left, right) => String(left.date).localeCompare(String(right.date))) },
    selectedWaiterScheduleMap() { return this.selectedWaiterEntries.reduce((accumulator, item) => { if (item.is_working) accumulator[item.date] = item; return accumulator }, {}) },
    openSlotsMap() { return this.scheduleRaw.reduce((accumulator, item) => { if (item.date && item.is_working === true && !item.employee_key) accumulator[item.date] = true; return accumulator }, {}) },
    selectedWaiterCaption() {
      if (!this.selectedWaiterInfo) return ''
      if (this.isWaiterView) {
        if (this.currentScheduleStatus !== 'published') return 'Это черновик расписания. Закрепление станет доступно после публикации.'
        if (this.currentUserAssignedWaiterKey && this.currentUserAssignedWaiterKey !== this.selectedWaiterInfo.slot_position_key) return 'Вы уже закреплены за другим местом.'
        if (this.selectedWaiterInfo.isClaimed && !this.selectedWaiterInfo.claimedByCurrentUser) return 'Это место уже занято другим сотрудником.'
        if (this.selectedWaiterInfo.claimedByCurrentUser) return 'Это ваше текущее закрепленное место.'
        return 'Нажмите «Закрепиться», чтобы отправить заявку на это место.'
      }
      if (this.currentScheduleStatus !== 'published') {
        return this.selectedWaiterInfo.isClaimed
          ? 'Это черновик. Закрепления появятся после публикации, а сейчас можно только редактировать смены ниже.'
          : 'Это черновик. Закрепление сотрудников станет доступно после публикации, а пока можно редактировать смены по дням.'
      }
      return this.selectedWaiterInfo.isClaimed ? 'Место занято. Можно снять сотрудника или отредактировать черновик смен ниже.' : 'Вы можете закрепить сотрудника, а ниже при необходимости отредактировать смены по дням.'
    },
    canClaimSelectedWaiter() { return !!(this.currentScheduleStatus === 'published' && this.isWaiterView && this.selectedWaiterInfo && this.canSelectWaiter(this.selectedWaiterInfo) && this.selectedWaiterInfo.slot_id && (!this.currentUserAssignedWaiterKey || this.currentUserAssignedWaiterKey === this.selectedWaiterInfo.slot_position_key) && (!this.selectedWaiterInfo.isClaimed || this.selectedWaiterInfo.claimedByCurrentUser)) },
    canOpenAssignPanel() { return Boolean(this.currentScheduleStatus === 'published' && this.canManageSchedule && this.selectedWaiterInfo && this.selectedWaiterInfo.slot_id && !this.selectedWaiterInfo.isClaimed) },
    canUnassignSelectedWaiter() { return Boolean(this.currentScheduleStatus === 'published' && this.canManageSchedule && this.selectedWaiterInfo?.slot_id && this.selectedWaiterInfo.isClaimed) },
    assignedEmployeeIds() { return this.waiters.map((waiter) => Number(waiter.assigned_employee_id)).filter((value) => Number.isFinite(value) && value > 0) },
    assignableEmployees() {
      const grade = String(this.selectedWaiterInfo?.grade || '').toLowerCase()
      return this.employees.filter((employee) => {
        const role = normalizeRole(employee.role)
        const employeeId = Number(employee.id)
        if (!['employee_noob', 'employee_pro'].includes(role)) return false
        if (getVenueId(employee) !== this.currentVenueId) return false
        if (this.assignedEmployeeIds.includes(employeeId)) return false
        return !grade || role === grade
      })
    },
    assignableEmployeeOptions() {
      return this.assignableEmployees.map((employee) => ({
        value: employee.id,
        label: this.getEmployeeOptionLabel(employee)
      }))
    },
    shiftTypeOptions() {
      return [
        { value: 'morning', label: 'Утро' },
        { value: 'evening', label: 'Вечер' },
        { value: 'full', label: 'Полный день' },
        { value: 'shift', label: 'Смена' },
        { value: 'off', label: 'Выходной' }
      ]
    },
    monthTitle() { return this.currentMonth.toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' }) },
    calendarDays() {
      const year = this.currentMonth.getFullYear()
      const month = this.currentMonth.getMonth()
      const first = new Date(year, month, 1)
      const last = new Date(year, month + 1, 0)
      const firstWeekday = (first.getDay() + 6) % 7
      const result = []
      for (let i = firstWeekday; i > 0; i -= 1) result.push(this.buildCalendarDay(new Date(year, month, 1 - i), false))
      for (let day = 1; day <= last.getDate(); day += 1) result.push(this.buildCalendarDay(new Date(year, month, day), true))
      const rest = result.length % 7
      if (rest !== 0) for (let i = 1; i <= 7 - rest; i += 1) result.push(this.buildCalendarDay(new Date(year, month + 1, i), false))
      return result
    },
    canEditSelectedWaiterSchedule() { return Boolean(this.canManageSchedule && this.isDraftSchedule && this.currentScheduleId && this.selectedWaiterEntries.length) },
    hasPendingScheduleEdits() {
      if (this.editableEntries.length !== this.selectedWaiterEntries.length) return this.editableEntries.length > 0
      return this.editableEntries.some((entry, index) => JSON.stringify(buildComparableEntryState(entry)) !== JSON.stringify(buildComparableEntryState(this.selectedWaiterEntries[index])))
    },
    staffShortageSummary() {
      const summary = this.latestGenerationSummary
      if (!summary) return null

      const available = Number(summary.available_staff)
      const required = Number(summary.required_waiters_peak)
      const explicitShortage = Number(summary.lack_staff_peak)

      if (!Number.isFinite(available) || !Number.isFinite(required)) {
        return null
      }

      const shortage = Number.isFinite(explicitShortage)
        ? explicitShortage
        : Math.max(required - available, 0)

      return {
        available,
        required,
        shortage: Math.max(shortage, 0)
      }
    },
    scheduleMetrics() {
      const summary = this.latestGenerationSummary
      if (!summary) return []
      return [
        { key: 'available_staff', label: 'Доступно сотрудников', value: summary.available_staff ?? '—' },
        { key: 'required_waiters_peak', label: 'Нужно в пик', value: summary.required_waiters_peak ?? '—' },
        { key: 'lack_staff_peak', label: 'Нехватка в пик', value: summary.lack_staff_peak ?? '—' },
        { key: 'days_with_shortage', label: 'Дней с нехваткой', value: summary.days_with_shortage ?? '—' },
        { key: 'shortage_person_days', label: 'Человеко-дней нехватки', value: summary.shortage_person_days ?? '—' }
      ].filter((item) => item.value !== undefined && item.value !== null)
    }
  },
  watch: {
    selectedWaiter() { this.syncEditableEntries() }
  },
  async mounted() {
    this.updateDeviceMode()
    window.addEventListener('resize', this.updateDeviceMode)
    window.addEventListener('orientationchange', this.updateDeviceMode)
    if (!USE_MOCK_AUTH) {
      try {
        const freshUser = await fetchCurrentUser()
        this.user = freshUser
        localStorage.setItem('user', JSON.stringify(freshUser))
      } catch (error) {
        const saved = localStorage.getItem('user')
        if (saved) {
          try { this.user = JSON.parse(saved) } catch (parseError) { this.user = { role: '' } }
        }
      }
    }
    if (this.canManageSchedule) await this.loadEmployees()
    await this.loadSchedule()
  },
  beforeUnmount() {
    window.removeEventListener('resize', this.updateDeviceMode)
    window.removeEventListener('orientationchange', this.updateDeviceMode)
  },
  methods: {
    updateDeviceMode() {
      this.isHandheldDevice = detectHandheldDevice()
      if (!this.isHandheldDevice) this.showMobileSelectorInfo = false
    },
    async loadEmployees() {
      if (USE_MOCK_AUTH) return
      try { const response = await api.get('/users/'); this.employees = asArray(response.data) } catch (error) { this.employees = [] }
    },
    async handleLogout() { this.menuOpen = false; await logoutUser(); this.$router.replace('/login') },
    openMenu() { this.menuOpen = true },
    closeMenu() { this.menuOpen = false },
    goToProfile() { this.menuOpen = false; this.$router.push('/cabinet') },
    clearScheduleNotice() { this.scheduleNotice = '' },
    openAssignPanel() { if (!this.canOpenAssignPanel) return; this.selectedEmployeeToAssign = ''; this.showAssignPanel = true },
    closeAssignPanel() { this.selectedEmployeeToAssign = ''; this.showAssignPanel = false },
    async prevMonth() { this.clearScheduleNotice(); this.currentMonth = new Date(this.currentMonth.getFullYear(), this.currentMonth.getMonth() - 1, 1); await this.loadSchedule({ isMonthSwitching: true }) },
    async nextMonth() { this.clearScheduleNotice(); this.currentMonth = new Date(this.currentMonth.getFullYear(), this.currentMonth.getMonth() + 1, 1); await this.loadSchedule({ isMonthSwitching: true }) },
    async loadSchedule({ isMonthSwitching = false, scheduleId = null } = {}) {
      this.scheduleError = ''
      this.isLoadingSchedule = !isMonthSwitching
      this.isMonthSwitching = isMonthSwitching
      this.closeAssignPanel()
      try {
        const schedule = await fetchScheduleForMonth({ monthDate: this.currentMonth, user: this.user, scheduleId })
        this.scheduleRaw = Array.isArray(schedule.entries) ? schedule.entries : []
        this.scheduleExists = Boolean(schedule.scheduleExists)
        this.currentScheduleId = schedule.scheduleId || null
        this.currentScheduleStatus = schedule.scheduleStatus || null
        this.syncSelectedWaiter()
        this.syncEditableEntries()
      } catch (error) {
        this.scheduleRaw = []
        this.scheduleExists = false
        this.currentScheduleId = null
        this.currentScheduleStatus = null
        this.selectedWaiter = ''
        this.editableEntries = []
        this.scheduleError = error.message || 'Не удалось загрузить расписание'
      } finally {
        this.isLoadingSchedule = false
        this.isMonthSwitching = false
      }
    },
    syncSelectedWaiter() {
      if (this.waiters.length === 0) { this.selectedWaiter = ''; return }
      if (this.waiters.some((item) => item.slot_position_key === this.selectedWaiter)) return
      if (this.isWaiterView && this.currentUserAssignedWaiterKey) { this.selectedWaiter = this.currentUserAssignedWaiterKey; return }
      if (this.isWaiterView && this.pinnedWaiterKey) {
        const pinned = this.waiters.find((item) => item.slot_position_key === this.pinnedWaiterKey)
        if (pinned && this.canSelectWaiter(pinned)) { this.selectedWaiter = this.pinnedWaiterKey; return }
      }
      this.selectedWaiter = this.waiters.find((item) => this.canSelectWaiter(item))?.slot_position_key || ''
    },
    syncEditableEntries() { this.editableEntries = this.selectedWaiterEntries.map((entry) => this.createEditableEntry(entry)) },
    createEditableEntry(entry) { return { entry_id: entry.entry_id, date: entry.date, is_working: Boolean(entry.is_working), shift_type: entry.shift_type || 'shift', waiters_needed: Number(entry.waiters_needed ?? 1), work_start: entry.work_start || '', work_end: entry.work_end || '', work_hours: entry.work_hours ?? getHoursDifference(entry.work_start, entry.work_end) ?? 0 } },
    resetEditableEntries() { this.syncEditableEntries(); this.scheduleNotice = 'Изменения в форме сброшены.'; this.scheduleError = '' },
    handleEditableWorkingToggle(entry) {
      if (!entry.is_working) { entry.shift_type = 'off'; entry.waiters_needed = 0; entry.work_hours = 0; return }
      if (entry.shift_type === 'off') entry.shift_type = 'shift'
      if (!entry.waiters_needed) entry.waiters_needed = 1
      this.updateEditableWorkHours(entry)
    },
    handleEditableTimeChange(index) { const entry = this.editableEntries[index]; if (entry) this.updateEditableWorkHours(entry) },
    updateEditableWorkHours(entry) { const hours = getHoursDifference(entry.work_start, entry.work_end); if (hours !== null) entry.work_hours = hours },
    buildEntryUpdatePayload(entry) {
      return {
        id: Number(entry.entry_id),
        is_working: Boolean(entry.is_working),
        shift_type: entry.is_working ? String(entry.shift_type || 'shift').toLowerCase() : 'off',
        waiters_needed: entry.is_working ? Number(entry.waiters_needed ?? 0) : 0,
        work_start: entry.is_working ? formatTimeForApi(entry.work_start) : '',
        work_end: entry.is_working ? formatTimeForApi(entry.work_end) : '',
        work_hours: entry.is_working ? Number(entry.work_hours ?? getHoursDifference(entry.work_start, entry.work_end) ?? 0) : 0
      }
    },
    getChangedEntryUpdates() {
      return this.editableEntries.map((entry, index) => {
        const original = this.selectedWaiterEntries[index]
        if (JSON.stringify(buildComparableEntryState(entry)) === JSON.stringify(buildComparableEntryState(original))) return null
        return this.buildEntryUpdatePayload(entry)
      }).filter(Boolean)
    },
    async saveDraftEdits() {
      if (!this.canEditSelectedWaiterSchedule || this.isSavingDraft) return
      const updates = this.getChangedEntryUpdates()
      if (!updates.length) { this.scheduleNotice = 'Нет изменений для сохранения.'; this.scheduleError = ''; return }
      this.isSavingDraft = true
      this.scheduleError = ''
      this.scheduleNotice = ''
      try {
        const response = await updateScheduleEntriesBulk({ scheduleId: this.currentScheduleId, updates })
        await this.loadSchedule({ scheduleId: this.currentScheduleId })
        this.scheduleNotice = `Черновик обновлен. Изменено записей: ${Number(response?.updated_entries_count) || updates.length}.`
      } catch (error) {
        this.scheduleError = error.message || 'Не удалось обновить черновик расписания'
      } finally {
        this.isSavingDraft = false
      }
    },
    selectWaiter(slotPositionKey) {
      if (!slotPositionKey) return
      const waiter = this.waiters.find((item) => item.slot_position_key === slotPositionKey)
      if (waiter && !this.canSelectWaiter(waiter)) return
      this.selectedWaiter = slotPositionKey
      this.closeAssignPanel()
      this.scheduleError = ''
      this.scheduleNotice = ''
    },
    getEmployeeOptionLabel(employee) {
      const fullName = [employee.first_name, employee.last_name].filter(Boolean).join(' ').trim()
      const label = fullName || employee.username || `Сотрудник ${employee.id}`
      const role = this.getGradeLabel(employee.role)
      return role ? `${label} · ${role}` : label
    },
    isCurrentUserAssignment(item) {
      const users = [normalizeIdentity(this.user.id), normalizeIdentity(this.user.username), normalizeIdentity(this.user.email)].filter(Boolean)
      const assignment = [normalizeIdentity(item.employee_id), normalizeIdentity(item.employee_key), normalizeIdentity(item.assigned_employee_id), normalizeIdentity(item.assigned_employee_username)].filter(Boolean)
      return assignment.some((identity) => users.includes(identity))
    },
    async handleClaimSelectedWaiter() {
      if (!this.canClaimSelectedWaiter || !this.selectedWaiterInfo) return
      this.isClaimingSlot = true
      this.scheduleError = ''
      this.scheduleNotice = ''
      try {
        await claimScheduleSlot({ slotId: this.selectedWaiterInfo.slot_id })
        await this.loadSchedule({ scheduleId: this.currentScheduleId })
        window.dispatchEvent(new CustomEvent('notifications:refresh'))
        this.scheduleNotice = 'Запрос на закрепление отправлен.'
      } catch (error) {
        this.scheduleError = error.message || 'Не удалось закрепиться за местом'
      } finally { this.isClaimingSlot = false }
    },
    async handleAssignSelectedWaiter() {
      if (!this.selectedWaiterInfo || !this.selectedEmployeeToAssign) return
      this.isAssigningSlot = true
      this.scheduleError = ''
      this.scheduleNotice = ''
      try {
        await assignScheduleSlot({ slotId: this.selectedWaiterInfo.slot_id, employeeId: Number(this.selectedEmployeeToAssign) })
        await this.loadSchedule({ scheduleId: this.currentScheduleId })
        window.dispatchEvent(new CustomEvent('notifications:refresh'))
        this.scheduleNotice = 'Сотрудник закреплен за выбранным местом.'
      } catch (error) {
        this.scheduleError = error.message || 'Не удалось закрепить сотрудника'
      } finally { this.isAssigningSlot = false }
    },
    async handleUnassignSelectedWaiter() {
      if (!this.canUnassignSelectedWaiter || !this.selectedWaiterInfo) return
      this.isUnassigningSlot = true
      this.scheduleError = ''
      this.scheduleNotice = ''
      try {
        await unassignScheduleSlot({ slotId: this.selectedWaiterInfo.slot_id })
        await this.loadSchedule({ scheduleId: this.currentScheduleId })
        window.dispatchEvent(new CustomEvent('notifications:refresh'))
        this.scheduleNotice = 'Сотрудник откреплен от выбранного места.'
      } catch (error) {
        this.scheduleError = error.message || 'Не удалось открепить сотрудника'
      } finally { this.isUnassigningSlot = false }
    },
    buildGenerationSummary(response) {
      const summary = { available_staff: response?.available_staff, required_waiters_peak: response?.required_waiters_peak, lack_staff_peak: response?.lack_staff_peak, days_with_shortage: response?.days_with_shortage, shortage_person_days: response?.shortage_person_days }
      return Object.values(summary).some((value) => value !== undefined && value !== null) ? summary : null
    },
    buildGenerationNotice(response) {
      const parts = ['Черновик расписания создан']
      if (Number.isFinite(Number(response?.slots_count))) parts.push(`слотов: ${Number(response.slots_count)}`)
      if (Number.isFinite(Number(response?.entries_count))) parts.push(`записей: ${Number(response.entries_count)}`)
      if (Number.isFinite(Number(response?.lack_staff_peak))) parts.push(`нехватка в пик: ${Number(response.lack_staff_peak)}`)
      return `${parts.join(', ')}.`
    },
    async handleCreateSchedule() {
      if (this.isGeneratingSchedule) return
      this.isGeneratingSchedule = true
      this.scheduleError = ''
      this.scheduleNotice = ''
      try {
        const response = await generateSchedule({ user: this.user, monthDate: this.currentMonth })
        const scheduleId = response?.schedule_id || response?.scheduleId || null
        this.latestGenerationSummary = this.buildGenerationSummary(response)
        if (scheduleId) await this.loadSchedule({ scheduleId }); else await this.loadSchedule()
        window.dispatchEvent(new CustomEvent('notifications:refresh'))
        this.scheduleNotice = this.buildGenerationNotice(response)
      } catch (error) {
        this.scheduleError = error.message || 'Не удалось создать расписание'
      } finally { this.isGeneratingSchedule = false }
    },
    async handlePublishSchedule() {
      if (this.isPublishingSchedule || !this.currentScheduleId) return
      this.isPublishingSchedule = true
      this.scheduleError = ''
      this.scheduleNotice = ''
      try {
        await publishSchedule({ scheduleId: this.currentScheduleId, monthDate: this.currentMonth })
        await this.loadSchedule({ scheduleId: this.currentScheduleId })
        window.dispatchEvent(new CustomEvent('notifications:refresh'))
        this.scheduleNotice = 'Расписание опубликовано.'
      } catch (error) {
        this.scheduleError = error.message || 'Не удалось опубликовать расписание'
      } finally { this.isPublishingSchedule = false }
    },
    async handleNotificationsUpdated() { await this.loadSchedule({ scheduleId: this.currentScheduleId }) },
    buildCalendarDay(date, isCurrentMonth) {
      const key = this.formatDateKey(date)
      const today = new Date()
      return { key, date, isCurrentMonth, isToday: date.getFullYear() === today.getFullYear() && date.getMonth() === today.getMonth() && date.getDate() === today.getDate(), shift: this.selectedWaiterScheduleMap[key] || null, hasOpenSlots: Boolean(this.openSlotsMap[key]) }
    },
    formatDateKey(date) { return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}` },
    formatEntryDate(date) { return new Date(`${date}T00:00:00`).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', weekday: 'short' }) },
    getFallbackEmployeeLabel(item) { return item.waiter_num || item.waiter_num === 0 ? `Официант ${item.waiter_num}` : item.employee_key ? `Сотрудник ${item.employee_key}` : 'Сотрудник' },
    getWaiterMeta(waiter) {
      const role = waiter.roleDisplay || this.getGradeLabel(waiter.grade) || 'Без категории'
      if (waiter.isClaimed) return `${role} · занято: ${waiter.assigned_employee_name || waiter.assigned_employee_username || 'сотрудник'}`
      return `${role} · свободно`
    },
    getGradeLabel(grade) { const normalized = String(grade || '').toLowerCase(); if (normalized === 'employee_noob') return 'Стажер'; if (normalized === 'employee_pro') return 'Опытный'; return '' },
    getShortageUnitLabel(value) {
      const count = Math.abs(Number(value)) % 100
      const last = count % 10
      if (count > 10 && count < 20) return 'сотрудников'
      if (last === 1) return 'сотрудника'
      if (last >= 2 && last <= 4) return 'сотрудников'
      return 'сотрудников'
    },
    canSelectWaiter(waiter) {
      if (!waiter) return false
      if (!this.isWaiterView) return true
      const currentGrade = String(this.currentWaiterGrade || '').toLowerCase()
      const waiterGrade = String(waiter.grade || '').toLowerCase()
      if (currentGrade !== 'employee_noob' && currentGrade !== 'employee_pro') return true
      if (!waiterGrade) return true
      return waiterGrade === currentGrade
    },
    getWaiterColor(key) { const hash = String(key || '').split('').reduce((accumulator, char) => accumulator + char.charCodeAt(0), 0); return WAITER_COLORS[hash % WAITER_COLORS.length] },
    getShiftLabel(shiftType) { return SHIFT_LABELS[shiftType] || shiftType || '' },
    getShiftShortLabel(shiftType) {
      const normalized = String(shiftType || '').toLowerCase()
      if (normalized === 'full') return 'П'
      if (normalized === 'morning') return 'У'
      if (normalized === 'evening') return 'В'
      return this.getShiftLabel(shiftType)
    },
    getWaiterButtonStyle(waiter) { return waiter.slot_position_key !== this.selectedWaiter ? {} : { borderColor: waiter.color, boxShadow: `0 0 0 1px ${waiter.color} inset` } },
    getDayStyle(day) {
      if (day.shift) return { backgroundColor: this.selectedWaiterInfo?.color || this.getWaiterColor(this.selectedWaiter), color: '#ffffff' }
      if (day.hasOpenSlots) return { backgroundColor: 'rgba(73, 209, 125, 0.16)', color: '#ffffff' }
      return {}
    }
  }
}
</script>

