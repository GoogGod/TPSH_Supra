<template>
  <div class="forecast-page">
    <transition name="menu-overlay"><div v-if="menuOpen" class="side-menu-overlay" @click="closeMenu"></div></transition>
    <transition name="side-menu">
      <aside v-if="menuOpen" class="side-menu">
        <div class="side-menu-top"><button class="side-menu-close" @click="closeMenu">×</button></div>
        <div class="side-menu-section">
          <button class="side-menu-item" @click="goToProfile">Профиль</button>
          <button class="side-menu-item active" @click="closeMenu">Расписание</button>
        </div>
        <div class="side-menu-footer"><button class="side-menu-item side-menu-item-danger" @click="handleLogout">Выйти</button></div>
      </aside>
    </transition>
    <main class="forecast-content">
      <section class="forecast-card">
        <div class="forecast-card-top">
          <button class="menu-button" @click="openMenu" aria-label="Открыть меню"><span></span><span></span><span></span></button>
          <div class="forecast-heading"><p class="forecast-subtitle">График работы</p><h1 class="forecast-title">Расписание</h1></div>
        </div>
        <div class="month-toolbar">
          <div class="month-switcher">
            <button class="month-button" :disabled="isMonthSwitching" @click="prevMonth">‹</button>
            <div class="month-label">{{ monthTitle }}</div>
            <button class="month-button" :disabled="isMonthSwitching" @click="nextMonth">›</button>
          </div>
          <button v-if="canManageSchedule" class="create-schedule-button" :disabled="isGeneratingSchedule" @click="handleCreateSchedule">{{ isGeneratingSchedule ? 'Создаем...' : 'Создать расписание' }}</button>
          <button v-if="canPublishCurrentSchedule" class="publish-schedule-button" :disabled="isPublishingSchedule" @click="handlePublishSchedule">{{ isPublishingSchedule ? 'Публикуем...' : 'Опубликовать' }}</button>
        </div>
        <div class="schedule-info-row">
          <div v-if="scheduleNotice" class="schedule-status-card is-success">{{ scheduleNotice }}</div>
          <div v-else-if="isLoadingSchedule" class="schedule-status-card">Загружаем расписание...</div>
          <div v-else-if="scheduleError" class="schedule-status-card is-error">{{ scheduleError }}</div>
          <div v-else-if="!hasSchedule" class="schedule-status-card">На этот месяц расписание пока не создано</div>
          <div v-else class="schedule-status-card is-soft">{{ roleHint }}</div>
        </div>
        <div class="waiter-picker-card">
          <div class="waiter-picker-head"><h2>Места</h2><p>{{ selectorDescription }}</p></div>
          <div v-if="waiters.length === 0" class="waiter-empty-state">Нет доступных мест для отображения</div>
          <div v-else class="waiter-button-list">
            <button v-for="waiter in waiters" :key="waiter.slot_position_key" class="waiter-button" :class="{ active: waiter.slot_position_key === selectedWaiter, disabled: !canSelectWaiter(waiter) }" :style="getWaiterButtonStyle(waiter)" :disabled="!canSelectWaiter(waiter)" @click="selectWaiter(waiter.slot_position_key)">
              <span class="waiter-button-name">{{ waiter.label }}</span>
              <span class="waiter-button-meta">{{ getWaiterMeta(waiter) }}</span>
            </button>
          </div>
          <div v-if="selectedWaiterInfo" class="slot-actions-card">
            <p class="slot-actions-title">{{ selectedWaiterInfo.label }}</p>
            <p class="slot-actions-caption">{{ selectedWaiterCaption }}</p>
            <div v-if="isWaiterView" class="slot-actions-buttons slot-actions-buttons-single">
              <button class="claim-slot-button" :disabled="!canClaimSelectedWaiter || isClaimingSlot" @click="handleClaimSelectedWaiter">{{ isClaimingSlot ? 'Закрепляем...' : 'Закрепиться' }}</button>
            </div>
            <div v-else class="slot-actions-buttons">
              <button class="claim-slot-button" :disabled="!canOpenAssignPanel || isAssigningSlot || isUnassigningSlot" @click="openAssignPanel">Закрепить</button>
              <button class="unassign-slot-button" :disabled="!canUnassignSelectedWaiter || isUnassigningSlot || isAssigningSlot" @click="handleUnassignSelectedWaiter">{{ isUnassigningSlot ? 'Открепляем...' : 'Открепить' }}</button>
            </div>
            <div v-if="showAssignPanel && canManageSchedule" class="assign-panel">
              <label class="assign-panel-field"><span>Выберите сотрудника</span><select v-model="selectedEmployeeToAssign"><option disabled value="">Выберите сотрудника</option><option v-for="employee in assignableEmployees" :key="employee.id" :value="employee.id">{{ getEmployeeOptionLabel(employee) }}</option></select></label>
              <div class="assign-panel-actions">
                <button class="claim-slot-button" :disabled="!selectedEmployeeToAssign || isAssigningSlot" @click="handleAssignSelectedWaiter">{{ isAssigningSlot ? 'Закрепляем...' : 'Подтвердить' }}</button>
                <button class="unassign-slot-button" :disabled="isAssigningSlot" @click="closeAssignPanel">Отмена</button>
              </div>
            </div>
          </div>
        </div>
        <div class="calendar-card">
          <div class="calendar-weekdays"><div v-for="weekday in weekdays" :key="weekday" class="weekday-cell">{{ weekday }}</div></div>
          <div class="calendar-grid">
            <div v-for="day in calendarDays" :key="day.key" class="calendar-cell" :class="{ 'outside-month': !day.isCurrentMonth, 'is-working': !!day.shift, 'is-open-slot': !day.shift && day.hasOpenSlots, 'is-today': day.isToday, 'is-selected-waiter': !!day.shift }" :style="getDayStyle(day)">
              <div class="day-number">{{ day.date.getDate() }}</div>
              <div v-if="day.shift" class="day-shift-mark"><span class="shift-chip">{{ getShiftLabel(day.shift.shift_type) }}</span><span v-if="day.shift.work_start && day.shift.work_end" class="shift-caption">{{ day.shift.work_start }}-{{ day.shift.work_end }}</span></div>
              <div v-else-if="day.hasOpenSlots" class="day-open-mark"><span class="shift-chip open-slot-chip">Есть смены</span></div>
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
import { fetchCurrentUser, logoutUser } from '../services/auth'
import { assignScheduleSlot, claimScheduleSlot, fetchScheduleForMonth, generateSchedule, publishSchedule, unassignScheduleSlot } from '../services/schedule'
import { pushProfileNotification } from '../services/profileNotifications'

const USE_MOCK_AUTH = import.meta.env.VITE_USE_MOCK_AUTH === 'true'
const WAITER_COLORS = ['#c9839f','#7fa8d8','#72a9a2','#d89a7f','#9b90c8','#d7c07a','#86b592','#b18fc0']
const normalizeRole = (role) => String(role || '').toLowerCase()
const normalizeIdentity = (value) => value === undefined || value === null || value === '' ? '' : String(value).toLowerCase()
const asArray = (payload) => Array.isArray(payload) ? payload : Array.isArray(payload?.results) ? payload.results : Array.isArray(payload?.items) ? payload.items : Array.isArray(payload?.data) ? payload.data : []
const getVenueId = (entity) => { const raw = entity?.venue_id ?? entity?.venue?.id ?? entity?.venue; return raw === undefined || raw === null || raw === '' ? null : Number(raw) }

export default {
  name: 'ForeCastView',
  data() { return { menuOpen:false,currentMonth:new Date(new Date().getFullYear(),new Date().getMonth(),1),currentScheduleId:null,currentScheduleStatus:null,selectedWaiter:'',selectedEmployeeToAssign:'',showAssignPanel:false,weekdays:['Пн','Вт','Ср','Чт','Пт','Сб','Вс'],scheduleRaw:[],scheduleExists:false,scheduleError:'',scheduleNotice:'',isLoadingSchedule:false,isMonthSwitching:false,isGeneratingSchedule:false,isPublishingSchedule:false,isClaimingSlot:false,isUnassigningSlot:false,isAssigningSlot:false,employees:[],user:(() => { try { return JSON.parse(localStorage.getItem('user')) || { role:'' } } catch (error) { return { role:'' } } })() } },
  computed: {
    currentUserRole() { return normalizeRole(this.user.role) }, currentVenueId() { return getVenueId(this.user) }, canManageSchedule() { return ['manager','admin'].includes(this.currentUserRole) }, isWaiterView() { return !this.canManageSchedule }, hasSchedule() { return this.scheduleExists },
    canPublishCurrentSchedule() { return this.canManageSchedule && this.hasSchedule && !!this.currentScheduleId && this.currentScheduleStatus === 'draft' },
    roleHint() { if (this.canManageSchedule) return this.currentScheduleStatus === 'draft' ? 'Открылся черновик расписания. Проверьте его и затем опубликуйте.' : 'Выберите место и управляйте закреплениями сотрудников.'; return 'Выберите место и закрепитесь за ним. Официант может быть закреплен только за одним местом.' },
    selectorDescription() { if (this.waiters.length === 0) return 'Кнопки появятся, когда в расписании будут доступные места.'; return this.canManageSchedule ? 'Менеджер может закреплять свободных сотрудников на места и снимать их.' : 'Доступны только места вашей категории. Закрепиться можно только за одним местом.' },
    workingSchedule() { return this.scheduleRaw.filter((item) => item.is_working === true && item.employee_key) },
    waiters() {
      const grouped = new Map()
      this.workingSchedule.forEach((item) => {
        const slotPositionKey = item.slot_position_key || item.employee_key
        if (!grouped.has(slotPositionKey)) grouped.set(slotPositionKey,{ slot_position_key:slotPositionKey,employee_key:item.employee_key,employee_id:item.employee_id,assigned_employee_id:item.assigned_employee_id,assigned_employee_username:item.assigned_employee_username,assigned_employee_name:item.assigned_employee_name,slot_id:item.slot_id,waiter_num:item.waiter_num,label:item.employee_label || this.getFallbackEmployeeLabel(item),grade:item.grade || null,color:this.getWaiterColor(slotPositionKey),isClaimed:Boolean(item.assigned_employee_id || item.assigned_employee_name),claimedByCurrentUser:this.isCurrentUserAssignment(item),identities:[normalizeIdentity(item.employee_key),normalizeIdentity(item.employee_id),normalizeIdentity(item.waiter_num),normalizeIdentity(item.assigned_employee_id),normalizeIdentity(item.assigned_employee_username)].filter(Boolean) })
      })
      return Array.from(grouped.values()).sort((left,right) => (left.waiter_num ?? 0) - (right.waiter_num ?? 0))
    },
    selectedWaiterInfo() { return this.waiters.find((item) => item.slot_position_key === this.selectedWaiter) || null },
    pinnedWaiterKey() { const ids = [normalizeIdentity(this.user.id),normalizeIdentity(this.user.username),normalizeIdentity(this.user.email),normalizeIdentity(this.user.waiter_num)].filter(Boolean); const matched = this.waiters.find((waiter) => waiter.identities.some((identity) => ids.includes(identity))); return matched?.slot_position_key || '' },
    currentWaiterGrade() { if (this.currentUserRole === 'employee_noob' || this.currentUserRole === 'employee_pro') return this.currentUserRole; const pinned = this.waiters.find((waiter) => waiter.slot_position_key === this.pinnedWaiterKey); return String(pinned?.grade || '').toLowerCase() },
    currentUserAssignedWaiterKey() { const assigned = this.waiters.find((waiter) => waiter.claimedByCurrentUser); return assigned?.slot_position_key || '' },
    selectedWaiterScheduleMap() { const map = {}; this.workingSchedule.filter((item) => (item.slot_position_key || item.employee_key) === this.selectedWaiter).forEach((item) => { map[item.date] = item }); return map },
    openSlotsMap() { const map = {}; this.scheduleRaw.filter((item) => item.date && item.is_working === true && !item.employee_key).forEach((item) => { map[item.date] = true }); return map },
    selectedWaiterCaption() { if (!this.selectedWaiterInfo) return ''; if (this.isWaiterView) { if (this.currentUserAssignedWaiterKey && this.currentUserAssignedWaiterKey !== this.selectedWaiterInfo.slot_position_key) return 'Вы уже закреплены за другим местом.'; if (this.selectedWaiterInfo.isClaimed && !this.selectedWaiterInfo.claimedByCurrentUser) return 'Это место уже занято другим сотрудником.'; if (this.selectedWaiterInfo.claimedByCurrentUser) return 'Это ваше текущее закрепленное место.'; return 'Нажмите "Закрепиться", чтобы занять это место.' } if (this.selectedWaiterInfo.isClaimed) return 'Это место уже занято. Менеджер может снять сотрудника с места.'; return 'Нажмите "Закрепить", чтобы выбрать свободного сотрудника.' },
    canClaimSelectedWaiter() { if (!this.isWaiterView || !this.selectedWaiterInfo || !this.canSelectWaiter(this.selectedWaiterInfo) || !this.selectedWaiterInfo.slot_id) return false; if (this.currentUserAssignedWaiterKey && this.currentUserAssignedWaiterKey !== this.selectedWaiterInfo.slot_position_key) return false; return !this.selectedWaiterInfo.isClaimed || this.selectedWaiterInfo.claimedByCurrentUser },
    canOpenAssignPanel() { return Boolean(this.canManageSchedule && this.selectedWaiterInfo && this.selectedWaiterInfo.slot_id && !this.selectedWaiterInfo.isClaimed) },
    canUnassignSelectedWaiter() { return Boolean(this.canManageSchedule && this.selectedWaiterInfo?.slot_id && this.selectedWaiterInfo.isClaimed) },
    assignedEmployeeIds() { return this.waiters.map((waiter) => Number(waiter.assigned_employee_id)).filter((value) => Number.isFinite(value) && value > 0) },
    assignableEmployees() { const grade = String(this.selectedWaiterInfo?.grade || '').toLowerCase(); return this.employees.filter((employee) => { const role = normalizeRole(employee.role); const employeeId = Number(employee.id); if (!['employee_noob','employee_pro'].includes(role)) return false; if (getVenueId(employee) !== this.currentVenueId) return false; if (this.assignedEmployeeIds.includes(employeeId)) return false; return !grade || role === grade }) },
    monthTitle() { return this.currentMonth.toLocaleDateString('ru-RU',{ month:'long',year:'numeric' }) },
    calendarDays() { const year = this.currentMonth.getFullYear(); const month = this.currentMonth.getMonth(); const first = new Date(year,month,1); const last = new Date(year,month + 1,0); const firstWeekday = (first.getDay() + 6) % 7; const daysInMonth = last.getDate(); const result = []; for (let i = firstWeekday; i > 0; i--) result.push(this.buildCalendarDay(new Date(year,month,1 - i),false)); for (let day = 1; day <= daysInMonth; day++) result.push(this.buildCalendarDay(new Date(year,month,day),true)); const rest = result.length % 7; if (rest !== 0) for (let i = 1; i <= 7 - rest; i++) result.push(this.buildCalendarDay(new Date(year,month + 1,i),false)); return result }
  },
  async mounted() { if (!USE_MOCK_AUTH) { try { const freshUser = await fetchCurrentUser(); this.user = freshUser; localStorage.setItem('user',JSON.stringify(freshUser)) } catch (error) { const saved = localStorage.getItem('user'); if (saved) { try { this.user = JSON.parse(saved) } catch (parseError) { this.user = { role:'' } } } } } if (this.canManageSchedule) await this.loadEmployees(); await this.loadSchedule() },
  methods: {
    async loadEmployees() { if (USE_MOCK_AUTH) return; try { const response = await api.get('/users/'); this.employees = asArray(response.data) } catch (error) { this.employees = [] } },
    async handleLogout() { this.menuOpen = false; await logoutUser(); this.$router.replace('/login') }, openMenu() { this.menuOpen = true }, closeMenu() { this.menuOpen = false }, goToProfile() { this.menuOpen = false; this.$router.push('/cabinet') }, clearScheduleNotice() { this.scheduleNotice = '' },
    openAssignPanel() { if (!this.canOpenAssignPanel) return; this.selectedEmployeeToAssign = ''; this.showAssignPanel = true }, closeAssignPanel() { this.selectedEmployeeToAssign = ''; this.showAssignPanel = false },
    async prevMonth() { this.clearScheduleNotice(); this.currentMonth = new Date(this.currentMonth.getFullYear(),this.currentMonth.getMonth() - 1,1); await this.loadSchedule({ isMonthSwitching:true }) },
    async nextMonth() { this.clearScheduleNotice(); this.currentMonth = new Date(this.currentMonth.getFullYear(),this.currentMonth.getMonth() + 1,1); await this.loadSchedule({ isMonthSwitching:true }) },
    pushAdminOpenSlotsNotification() { const openCount = this.waiters.filter((waiter) => !waiter.isClaimed).length; if (!openCount || this.currentVenueId === null) return; pushProfileNotification({ venue:this.currentVenueId,audience:'admin',type:'unclaimed-slots',dedupe_key:`unclaimed-${this.currentVenueId}-${this.currentMonth.getFullYear()}-${this.currentMonth.getMonth() + 1}`,title:'Есть незакрепленные места',message:`На ${this.monthTitle} осталось незакрепленных мест: ${openCount}.` }) },
    async loadSchedule({ isMonthSwitching = false, scheduleId = null } = {}) { this.scheduleError = ''; this.isLoadingSchedule = !isMonthSwitching; this.isMonthSwitching = isMonthSwitching; this.closeAssignPanel(); try { const schedule = await fetchScheduleForMonth({ monthDate:this.currentMonth,user:this.user,scheduleId }); this.scheduleRaw = Array.isArray(schedule.entries) ? schedule.entries : []; this.scheduleExists = Boolean(schedule.scheduleExists); this.currentScheduleId = schedule.scheduleId || null; this.currentScheduleStatus = schedule.scheduleStatus || null; this.syncSelectedWaiter(); this.pushAdminOpenSlotsNotification() } catch (error) { this.scheduleRaw = []; this.scheduleExists = false; this.currentScheduleId = null; this.currentScheduleStatus = null; this.scheduleError = error.message || 'Не удалось загрузить расписание'; this.syncSelectedWaiter() } finally { this.isLoadingSchedule = false; this.isMonthSwitching = false } },
    syncSelectedWaiter() { if (this.waiters.length === 0) { this.selectedWaiter = ''; return } if (this.waiters.some((item) => item.slot_position_key === this.selectedWaiter)) return; if (this.isWaiterView && this.currentUserAssignedWaiterKey) { this.selectedWaiter = this.currentUserAssignedWaiterKey; return } if (this.isWaiterView && this.pinnedWaiterKey) { const pinned = this.waiters.find((item) => item.slot_position_key === this.pinnedWaiterKey); if (pinned && this.canSelectWaiter(pinned)) { this.selectedWaiter = this.pinnedWaiterKey; return } } const firstAllowed = this.waiters.find((item) => this.canSelectWaiter(item)); this.selectedWaiter = firstAllowed?.slot_position_key || '' },
    selectWaiter(slotPositionKey) { if (!slotPositionKey) return; const waiter = this.waiters.find((item) => item.slot_position_key === slotPositionKey); if (waiter && !this.canSelectWaiter(waiter)) return; this.selectedWaiter = slotPositionKey; this.closeAssignPanel() },
    getCurrentUserFullName() { const fullName = [this.user.first_name,this.user.last_name].filter(Boolean).join(' ').trim(); return fullName || this.user.username || 'Сотрудник' },
    getEmployeeOptionLabel(employee) { const fullName = [employee.first_name,employee.last_name].filter(Boolean).join(' ').trim(); const label = fullName || employee.username || `Сотрудник ${employee.id}`; const role = this.getGradeLabel(employee.role); return role ? `${label} · ${role}` : label },
    isCurrentUserAssignment(item) { const users = [normalizeIdentity(this.user.id),normalizeIdentity(this.user.username),normalizeIdentity(this.user.email)].filter(Boolean); const assignment = [normalizeIdentity(item.employee_id),normalizeIdentity(item.employee_key),normalizeIdentity(item.assigned_employee_id),normalizeIdentity(item.assigned_employee_username)].filter(Boolean); return assignment.some((identity) => users.includes(identity)) },
    notifyManagerAboutClaim(waiter) { pushProfileNotification({ venue:this.currentVenueId,audience:'manager',type:'slot-claim',title:'Новое закрепление',message:`${this.getCurrentUserFullName()} закрепился за местом ${waiter.waiter_num || waiter.label}.` }) },
    notifyManagerAboutAssignment(employee,waiter) { pushProfileNotification({ venue:this.currentVenueId,audience:'manager',type:'slot-assign',title:'Менеджер закрепил сотрудника',message:`${this.getEmployeeOptionLabel(employee)} закреплен за местом ${waiter.waiter_num || waiter.label}.` }) },
    async handleClaimSelectedWaiter() { if (!this.canClaimSelectedWaiter || !this.selectedWaiterInfo) return; this.isClaimingSlot = true; this.scheduleError = ''; this.scheduleNotice = ''; try { await claimScheduleSlot({ slotId:this.selectedWaiterInfo.slot_id }); this.notifyManagerAboutClaim(this.selectedWaiterInfo); await this.loadSchedule({ scheduleId:this.currentScheduleId }); this.scheduleNotice = 'Вы успешно закрепились за выбранным местом.' } catch (error) { this.scheduleError = error.message || 'Не удалось закрепиться за местом' } finally { this.isClaimingSlot = false } },
    async handleAssignSelectedWaiter() { if (!this.selectedWaiterInfo || !this.selectedEmployeeToAssign) return; this.isAssigningSlot = true; this.scheduleError = ''; this.scheduleNotice = ''; try { await assignScheduleSlot({ slotId:this.selectedWaiterInfo.slot_id, employeeId:Number(this.selectedEmployeeToAssign) }); const employee = this.assignableEmployees.find((item) => Number(item.id) === Number(this.selectedEmployeeToAssign)); if (employee) this.notifyManagerAboutAssignment(employee,this.selectedWaiterInfo); await this.loadSchedule({ scheduleId:this.currentScheduleId }); this.scheduleNotice = 'Сотрудник закреплен за выбранным местом.' } catch (error) { this.scheduleError = error.message || 'Не удалось закрепить сотрудника' } finally { this.isAssigningSlot = false } },
    async handleUnassignSelectedWaiter() { if (!this.canUnassignSelectedWaiter || !this.selectedWaiterInfo) return; this.isUnassigningSlot = true; this.scheduleError = ''; this.scheduleNotice = ''; try { await unassignScheduleSlot({ slotId:this.selectedWaiterInfo.slot_id }); await this.loadSchedule({ scheduleId:this.currentScheduleId }); this.scheduleNotice = 'Сотрудник откреплен от выбранного места.' } catch (error) { this.scheduleError = error.message || 'Не удалось открепить сотрудника' } finally { this.isUnassigningSlot = false } },
    async handleCreateSchedule() { if (this.isGeneratingSchedule) return; this.isGeneratingSchedule = true; this.scheduleError = ''; this.scheduleNotice = ''; try { const response = await generateSchedule({ user:this.user,monthDate:this.currentMonth }); const scheduleId = response?.schedule_id || response?.scheduleId || null; const slotsCount = Number(response?.slots_count); const entriesCount = Number(response?.entries_count); if (scheduleId) await this.loadSchedule({ scheduleId }); else await this.loadSchedule(); const parts = ['Черновик расписания создан']; if (Number.isFinite(slotsCount)) parts.push(`слотов: ${slotsCount}`); if (Number.isFinite(entriesCount)) parts.push(`назначений: ${entriesCount}`); this.scheduleNotice = parts.join(', ') + '.' } catch (error) { this.scheduleError = error.message || 'Не удалось создать расписание' } finally { this.isGeneratingSchedule = false } },
    async handlePublishSchedule() { if (this.isPublishingSchedule || !this.currentScheduleId) return; this.isPublishingSchedule = true; this.scheduleError = ''; this.scheduleNotice = ''; try { await publishSchedule({ scheduleId:this.currentScheduleId,monthDate:this.currentMonth }); await this.loadSchedule({ scheduleId:this.currentScheduleId }); this.scheduleNotice = 'Расписание опубликовано.' } catch (error) { this.scheduleError = error.message || 'Не удалось опубликовать расписание' } finally { this.isPublishingSchedule = false } },
    buildCalendarDay(date,isCurrentMonth) { const key = this.formatDateKey(date); const today = new Date(); return { key,date,isCurrentMonth,isToday:date.getFullYear() === today.getFullYear() && date.getMonth() === today.getMonth() && date.getDate() === today.getDate(),shift:this.selectedWaiterScheduleMap[key] || null,hasOpenSlots:Boolean(this.openSlotsMap[key]) } },
    formatDateKey(date) { const year = date.getFullYear(); const month = String(date.getMonth() + 1).padStart(2,'0'); const day = String(date.getDate()).padStart(2,'0'); return `${year}-${month}-${day}` },
    getFallbackEmployeeLabel(item) { if (item.waiter_num || item.waiter_num === 0) return `Официант ${item.waiter_num}`; return item.employee_key ? `Сотрудник ${item.employee_key}` : 'Сотрудник' },
    getWaiterMeta(waiter) { return this.getGradeLabel(waiter.grade) || 'Без категории' },
    getGradeLabel(grade) { const normalized = String(grade || '').toLowerCase(); if (normalized === 'employee_noob') return 'Стажер'; if (normalized === 'employee_pro') return 'Профессионал'; return '' },
    canSelectWaiter(waiter) { if (!waiter) return false; if (!this.isWaiterView) return true; const currentGrade = String(this.currentWaiterGrade || '').toLowerCase(); const waiterGrade = String(waiter.grade || '').toLowerCase(); if (currentGrade !== 'employee_noob' && currentGrade !== 'employee_pro') return true; if (!waiterGrade) return true; return waiterGrade === currentGrade },
    getWaiterColor(key) { const source = String(key || ''); const hash = source.split('').reduce((accumulator,char) => accumulator + char.charCodeAt(0),0); return WAITER_COLORS[hash % WAITER_COLORS.length] },
    getShiftLabel(shiftType) { const map = { morning:'Утро',evening:'Вечер',full:'Полный',off:'Выходной',shift:'Смена' }; return map[shiftType] || shiftType || '' },
    getWaiterButtonStyle(waiter) { if (waiter.slot_position_key !== this.selectedWaiter) return {}; return { borderColor:waiter.color, boxShadow:`0 0 0 1px ${waiter.color} inset` } },
    getDayStyle(day) { if (day.shift) return { backgroundColor:this.selectedWaiterInfo?.color || this.getWaiterColor(this.selectedWaiter), color:'#ffffff' }; if (day.hasOpenSlots) return { backgroundColor:'rgba(73, 209, 125, 0.16)', color:'#ffffff' }; return {} }
  }
}
</script>
