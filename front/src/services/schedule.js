import api from '../api'

const USE_MOCK_AUTH = import.meta.env.VITE_USE_MOCK_AUTH === 'true'
const MOCK_SCHEDULE_STORAGE_KEY = 'mock_schedule_months'

const INACTIVE_STATUSES = new Set([
  'cancelled',
  'canceled',
  'day_off',
  'off',
  'rejected',
  'removed',
  'unassigned'
])

const DIRECT_LIST_KEYS = [
  'results',
  'items',
  'data',
  'entries',
  'assignments',
  'schedules',
  'slots',
  'waiter_schedule',
  'waiterSchedule',
  'monthly_schedule',
  'monthlySchedule'
]

const NESTED_DAY_KEYS = ['slots', 'entries', 'assignments', 'waiter_schedule', 'waiterSchedule']

const isObject = (value) =>
  value !== null && typeof value === 'object' && !Array.isArray(value)

const firstDefined = (...values) =>
  values.find((value) => value !== undefined && value !== null && value !== '')

const normalizeRole = (role) => String(role || '').toLowerCase()

const normalizeScheduleStatus = (status) => String(status || '').trim().toLowerCase()

const padNumber = (value) => String(value).padStart(2, '0')

const formatDate = (date) =>
  `${date.getFullYear()}-${padNumber(date.getMonth() + 1)}-${padNumber(date.getDate())}`

const buildMonthRange = (monthDate = new Date()) => {
  const currentMonth = new Date(monthDate.getFullYear(), monthDate.getMonth(), 1)
  const nextMonth = new Date(monthDate.getFullYear(), monthDate.getMonth() + 1, 1)
  const lastDayOfMonth = new Date(nextMonth.getTime() - 24 * 60 * 60 * 1000)

  return {
    month: currentMonth.getMonth() + 1,
    year: currentMonth.getFullYear(),
    monthKey: `${currentMonth.getFullYear()}-${padNumber(currentMonth.getMonth() + 1)}`,
    startDate: formatDate(currentMonth),
    endDate: formatDate(lastDayOfMonth)
  }
}

const normalizeDateValue = (value) => {
  if (!value) {
    return ''
  }

  if (value instanceof Date) {
    return formatDate(value)
  }

  const normalized = String(value).trim()

  if (!normalized) {
    return ''
  }

  if (normalized.includes('T')) {
    return normalized.split('T')[0]
  }

  return normalized.slice(0, 10)
}

const normalizeTimeValue = (value) => {
  if (!value) {
    return ''
  }

  const raw = String(value).trim()

  if (!raw) {
    return ''
  }

  const timePart = raw.includes('T') ? raw.split('T')[1] : raw
  const withoutZone = timePart.split('+')[0].replace('Z', '')

  if (withoutZone.length >= 5) {
    return withoutZone.slice(0, 5)
  }

  return withoutZone
}

const getHoursDifference = (start, end) => {
  if (!start || !end) {
    return null
  }

  const [startHours = '0', startMinutes = '0'] = start.split(':')
  const [endHours = '0', endMinutes = '0'] = end.split(':')

  const startTotal = Number(startHours) * 60 + Number(startMinutes)
  let endTotal = Number(endHours) * 60 + Number(endMinutes)

  if (Number.isNaN(startTotal) || Number.isNaN(endTotal)) {
    return null
  }

  if (endTotal < startTotal) {
    endTotal += 24 * 60
  }

  const diff = (endTotal - startTotal) / 60
  return Number.isFinite(diff) ? diff : null
}

const normalizeShiftType = (value, workStart, workEnd, workHours) => {
  const raw = String(value || '').trim().toLowerCase()

  if (raw) {
    return raw
  }

  if (typeof workHours === 'number' && workHours >= 10) {
    return 'full'
  }

  if (workStart && workEnd) {
    const hours = getHoursDifference(workStart, workEnd)

    if (hours !== null && hours >= 10) {
      return 'full'
    }

    const startHours = Number(workStart.split(':')[0])
    return startHours < 13 ? 'morning' : 'evening'
  }

  return 'shift'
}

const extractEmployee = (item) => {
  if (isObject(item.employee)) {
    return item.employee
  }

  if (isObject(item.user)) {
    return item.user
  }

  if (isObject(item.worker)) {
    return item.worker
  }

  if (isObject(item.assigned_employee)) {
    return item.assigned_employee
  }

  if (isObject(item.assignee)) {
    return item.assignee
  }

  return {}
}

const normalizeEmployeeKey = (item, employee) => {
  const raw = firstDefined(
    item.employee_key,
    item.employee_id,
    item.assigned_employee_id,
    item.assigned_employee,
    item.employee,
    item.waiter_id,
    item.waiter_num,
    employee.employee_key,
    employee.waiter_num,
    employee.id,
    employee.username,
    employee.email
  )

  return raw === undefined || raw === null || raw === '' ? '' : String(raw)
}

const buildEmployeeLabel = (item, employee, employeeKey) => {
  if (item.employee_label) {
    return item.employee_label
  }

  if (item.employee_name) {
    return item.employee_name
  }

  const fullName = [employee.first_name, employee.last_name].filter(Boolean).join(' ').trim()

  if (fullName) {
    return fullName
  }

  if (employee.username) {
    return employee.username
  }

  const explicitWaiterNumber = firstDefined(item.waiter_num, employee.waiter_num)

  if (explicitWaiterNumber !== undefined && explicitWaiterNumber !== null && explicitWaiterNumber !== '') {
    return `Официант ${explicitWaiterNumber}`
  }

  if (employeeKey) {
    return `Сотрудник ${employeeKey}`
  }

  return 'Сотрудник'
}

const extractScheduleItems = (payload) => {
  if (Array.isArray(payload)) {
    return payload
  }

  if (!isObject(payload)) {
    return []
  }

  if (Array.isArray(payload.slots)) {
    const slotEntries = payload.slots.flatMap((slot) => {
      if (!isObject(slot)) {
        return []
      }

      if (Array.isArray(slot.entries)) {
        return slot.entries.map((entry) => {
          if (!isObject(entry)) {
            return entry
          }

          return {
            ...slot,
            ...entry,
            slot_id: firstDefined(entry.slot_id, slot.id),
            waiter_num: firstDefined(entry.waiter_num, slot.waiter_num),
            assigned_employee: firstDefined(entry.assigned_employee, slot.assigned_employee),
            employee_name: firstDefined(entry.employee_name, slot.employee_name),
            assignment_status: firstDefined(entry.assignment_status, slot.assignment_status)
          }
        })
      }

      return []
    })

    if (slotEntries.length > 0) {
      return slotEntries
    }
  }

  for (const key of DIRECT_LIST_KEYS) {
    if (Array.isArray(payload[key])) {
      return payload[key]
    }
  }

  if (Array.isArray(payload.days)) {
    const nestedItems = payload.days.flatMap((day) => {
      if (!isObject(day)) {
        return []
      }

      for (const key of NESTED_DAY_KEYS) {
        if (Array.isArray(day[key])) {
          return day[key].map((item) => {
            if (!isObject(item)) {
              return item
            }

            return {
              date: firstDefined(item.date, day.date, day.day, day.work_date),
              ...item
            }
          })
        }
      }

      if (firstDefined(day.date, day.day, day.work_date) !== undefined) {
        return [day]
      }

      return []
    })

    if (nestedItems.length > 0) {
      return nestedItems
    }
  }

  return []
}

const extractScheduleId = (payload) =>
  firstDefined(
    payload?.schedule_id,
    payload?.id,
    payload?.schedule?.schedule_id,
    payload?.schedule?.id,
    payload?.current_schedule_id
  ) || null

const extractScheduleStatus = (payload) =>
  normalizeScheduleStatus(
    firstDefined(
      payload?.status,
      payload?.state,
      payload?.schedule?.status,
      payload?.schedule?.state
    )
  ) || null

const normalizeScheduleEntry = (item) => {
  if (!isObject(item)) {
    return null
  }

  const shift = isObject(item.shift) ? item.shift : {}
  const employee = extractEmployee(item)

  const workStart = normalizeTimeValue(
    firstDefined(
      item.work_start,
      item.start_time,
      item.starts_at,
      item.slot_start,
      shift.work_start,
      shift.start_time,
      shift.starts_at
    )
  )

  const workEnd = normalizeTimeValue(
    firstDefined(
      item.work_end,
      item.end_time,
      item.ends_at,
      item.slot_end,
      shift.work_end,
      shift.end_time,
      shift.ends_at
    )
  )

  const calculatedHours = getHoursDifference(workStart, workEnd)
  const rawHours = firstDefined(item.work_hours, shift.work_hours, calculatedHours)
  const numericHours =
    rawHours === '' || rawHours === null || rawHours === undefined ? null : Number(rawHours)

  const employeeKey = normalizeEmployeeKey(item, employee)
  const date = normalizeDateValue(
    firstDefined(item.date, item.day, item.work_date, shift.date)
  )
  const status = String(
    firstDefined(item.status, item.state, item.assignment_status, item.slot_status, shift.status, '')
  ).toLowerCase()
  const rawIsWorking = firstDefined(item.is_working, shift.is_working, employeeKey ? true : false)
  const isWorkingValue =
    typeof rawIsWorking === 'boolean'
      ? rawIsWorking
      : String(rawIsWorking || '').toLowerCase() === 'true'
  const isWorking = isWorkingValue && !INACTIVE_STATUSES.has(status)

  if (!date) {
    return null
  }

  return {
    date,
    slot_id: firstDefined(item.slot_id, item.id, shift.id, null),
    employee_key: employeeKey,
    employee_id: firstDefined(item.employee_id, employee.id, null),
    employee_label: buildEmployeeLabel(item, employee, employeeKey),
    waiter_num: firstDefined(item.waiter_num, employee.waiter_num, employee.id, employeeKey),
    grade: firstDefined(item.grade, item.employee_grade, employee.grade, employee.role, employee.position, null),
    shift_type: normalizeShiftType(
      firstDefined(item.shift_type, item.slot_type, item.type, shift.shift_type, shift.type),
      workStart,
      workEnd,
      numericHours
    ),
    work_start: workStart,
    work_end: workEnd,
    work_hours: Number.isFinite(numericHours) ? numericHours : null,
    is_working: isWorking,
    assignment_status: status || null
  }
}

const normalizeScheduleCollection = (payload) => {
  const rawItems = extractScheduleItems(payload)
  const scheduleId = extractScheduleId(payload)
  const explicitExists = firstDefined(payload?.exists, payload?.has_schedule, payload?.hasSchedule)
  const scheduleStatus = extractScheduleStatus(payload)

  if (rawItems.length === 0) {
    return {
      entries: [],
      scheduleExists: Boolean(explicitExists || scheduleId),
      scheduleId,
      scheduleStatus
    }
  }

  const entries = rawItems.map((item) => normalizeScheduleEntry(item)).filter(Boolean)

  return {
    entries,
    scheduleExists: true,
    scheduleId,
    scheduleStatus
  }
}

const extractErrorMessage = (error, fallbackMessage) => {
  const data = error?.response?.data

  if (!data) {
    return error?.message || fallbackMessage
  }

  if (typeof data === 'string') {
    const trimmed = data.trim()

    if (trimmed.startsWith('<!DOCTYPE html') || trimmed.startsWith('<html')) {
      return fallbackMessage
    }

    return trimmed || fallbackMessage
  }

  if (data.detail) {
    return Array.isArray(data.detail) ? data.detail.join(', ') : data.detail
  }

  return (
    Object.entries(data)
      .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(', ') : value}`)
      .join('; ') || fallbackMessage
  )
}

const buildMonthQueryParams = (monthDate, user) => {
  const range = buildMonthRange(monthDate)
  const venueId = firstDefined(user?.venue_id, user?.venue?.id, user?.venue)

  const params = {
    month: range.month,
    year: range.year
  }

  if (venueId !== undefined && venueId !== null && venueId !== '') {
    params.venue = venueId
  }

  return params
}

const normalizeStatusResponse = (payload) => {
  const scheduleId = extractScheduleId(payload)
  const rawStatus = extractScheduleStatus(payload)
  const explicitExists = firstDefined(payload?.exists, payload?.has_schedule, payload?.hasSchedule)

  const exists =
    typeof explicitExists === 'boolean'
      ? explicitExists
      : Boolean(scheduleId || (rawStatus && !['none', 'missing', 'empty', 'not_found'].includes(rawStatus)))

  return {
    exists,
    scheduleId,
    status: rawStatus
  }
}

const extractScheduleRecords = (payload) => {
  const list = extractScheduleItems(payload)

  return list
    .filter((item) => isObject(item))
    .map((item) => ({
      scheduleId: extractScheduleId(item),
      status: extractScheduleStatus(item),
      raw: item
    }))
    .filter((item) => item.scheduleId)
}

const pickScheduleRecord = (records, user) => {
  const role = normalizeRole(user?.role)
  const canViewDraft = role === 'manager' || role === 'admin'

  if (canViewDraft) {
    return (
      records.find((item) => item.status === 'draft') ||
      records.find((item) => item.status === 'published') ||
      records[0] ||
      null
    )
  }

  return records.find((item) => item.status === 'published') || null
}

const fetchScheduleStatus = async ({ monthDate, user }) => {
  const response = await api.get('/schedule/status/', {
    params: buildMonthQueryParams(monthDate, user)
  })

  return normalizeStatusResponse(response.data)
}

const fetchScheduleDetail = async (scheduleId) => {
  const response = await api.get(`/schedule/monthly/${scheduleId}/`)
  const normalized = normalizeScheduleCollection(response.data)

  return {
    ...normalized,
    scheduleId: normalized.scheduleId || scheduleId
  }
}

const fetchScheduleList = async ({ monthDate, user }) => {
  const response = await api.get('/schedule/monthly/', {
    params: buildMonthQueryParams(monthDate, user)
  })

  return extractScheduleRecords(response.data)
}

const getStoredMockMonths = () => {
  try {
    return JSON.parse(localStorage.getItem(MOCK_SCHEDULE_STORAGE_KEY) || '{}')
  } catch (error) {
    return {}
  }
}

const storeMockMonth = (monthKey, value) => {
  const saved = getStoredMockMonths()
  saved[monthKey] = value
  localStorage.setItem(MOCK_SCHEDULE_STORAGE_KEY, JSON.stringify(saved))
}

const createMockWaiters = () => [
  {
    employee_key: 'waiter',
    employee_label: 'Официант 1',
    waiter_num: 1,
    grade: 'employee_noob'
  },
  {
    employee_key: 'waiter-2',
    employee_label: 'Официант 2',
    waiter_num: 2,
    grade: 'employee_pro'
  },
  {
    employee_key: 'waiter-3',
    employee_label: 'Официант 3',
    waiter_num: 3,
    grade: 'employee_noob'
  },
  {
    employee_key: 'waiter-4',
    employee_label: 'Официант 4',
    waiter_num: 4,
    grade: 'employee_pro'
  }
]

const buildMockShift = (date, waiter, shiftType, start, end, hours) => ({
  date,
  slot_id: `${date}-${waiter.employee_key}-${shiftType}`,
  employee_key: waiter.employee_key,
  employee_id: waiter.waiter_num,
  employee_label: waiter.employee_label,
  waiter_num: waiter.waiter_num,
  grade: waiter.grade,
  shift_type: shiftType,
  work_start: start,
  work_end: end,
  work_hours: hours,
  is_working: true,
  assignment_status: 'assigned'
})

const generateMockEntriesForMonth = (monthDate) => {
  const range = buildMonthRange(monthDate)
  const waiters = createMockWaiters()
  const entries = []
  const daysInMonth = Number(range.endDate.slice(-2))

  for (let day = 1; day <= daysInMonth; day++) {
    const date = `${range.year}-${padNumber(range.month)}-${padNumber(day)}`

    waiters.forEach((waiter, index) => {
      const cycle = (day + index) % 4

      if (cycle === 0) {
        entries.push(buildMockShift(date, waiter, 'morning', '09:00', '17:00', 8))
      } else if (cycle === 1) {
        entries.push(buildMockShift(date, waiter, 'evening', '15:00', '23:00', 8))
      } else if (cycle === 2) {
        entries.push(buildMockShift(date, waiter, 'full', '10:00', '22:00', 12))
      }
    })

    if (day % 6 === 0) {
      entries.push({
        date,
        slot_id: `${date}-open`,
        employee_key: '',
        employee_id: null,
        employee_label: '',
        waiter_num: null,
        grade: null,
        shift_type: 'morning',
        work_start: '10:00',
        work_end: '18:00',
        work_hours: 8,
        is_working: true,
        assignment_status: 'open'
      })
    }
  }

  return entries
}

const fetchMockScheduleForMonth = ({ monthDate }) => {
  const range = buildMonthRange(monthDate)
  const saved = getStoredMockMonths()

  if (saved[range.monthKey]) {
    return {
      entries: saved[range.monthKey].entries,
      scheduleExists: saved[range.monthKey].entries.length > 0,
      scheduleId: saved[range.monthKey].scheduleId,
      scheduleStatus: saved[range.monthKey].status || 'draft'
    }
  }

  const baseMonth = new Date()
  const sameMonth =
    monthDate.getFullYear() === baseMonth.getFullYear() &&
    monthDate.getMonth() === baseMonth.getMonth()

  if (!sameMonth) {
    return {
      entries: [],
      scheduleExists: false,
      scheduleId: null,
      scheduleStatus: null
    }
  }

  const entries = generateMockEntriesForMonth(monthDate)
  const scheduleId = `mock-${range.monthKey}`
  storeMockMonth(range.monthKey, { scheduleId, entries })

  return {
    entries,
    scheduleExists: entries.length > 0,
    scheduleId,
    scheduleStatus: 'draft'
  }
}

const generateMockSchedule = ({ user, monthDate = new Date() }) => {
  const range = buildMonthRange(monthDate)
  const entries = generateMockEntriesForMonth(monthDate)
  const scheduleId = `mock-${range.monthKey}`

  storeMockMonth(range.monthKey, { scheduleId, entries, status: 'draft' })

  return {
    schedule_id: scheduleId,
    slots_count: entries.length,
    entries_count: entries.filter((item) => item.employee_key).length,
    forecast_run_id: `mock-forecast-${range.monthKey}`,
    venue: firstDefined(user?.venue_id, user?.venue?.id, user?.venue, null)
  }
}

export const fetchScheduleForMonth = async ({
  monthDate = new Date(),
  user = null,
  scheduleId = null
} = {}) => {
  if (USE_MOCK_AUTH) {
    return fetchMockScheduleForMonth({ monthDate, user })
  }

  try {
    if (scheduleId) {
      return await fetchScheduleDetail(scheduleId)
    }

    const status = await fetchScheduleStatus({ monthDate, user })
    const scheduleRecords = await fetchScheduleList({ monthDate, user })
    const selectedRecord = pickScheduleRecord(scheduleRecords, user)
    const role = normalizeRole(user?.role)
    const canViewDraft = role === 'manager' || role === 'admin'

    if (!status.exists && !selectedRecord && !status.scheduleId) {
      return {
        entries: [],
        scheduleExists: false,
        scheduleId: null,
        scheduleStatus: null
      }
    }

    if (!canViewDraft && status.status === 'draft' && !selectedRecord) {
      return {
        entries: [],
        scheduleExists: false,
        scheduleId: null,
        scheduleStatus: null
      }
    }

    const resolvedScheduleId = selectedRecord?.scheduleId || status.scheduleId || null
    const resolvedScheduleStatus = selectedRecord?.status || status.status || null

    if (!resolvedScheduleId) {
      return {
        entries: [],
        scheduleExists: canViewDraft ? Boolean(status.exists) : false,
        scheduleId: null,
        scheduleStatus: resolvedScheduleStatus
      }
    }

    const detail = await fetchScheduleDetail(resolvedScheduleId)

    return {
      ...detail,
      scheduleStatus: detail.scheduleStatus || resolvedScheduleStatus
    }
  } catch (error) {
    throw new Error(extractErrorMessage(error, 'Не удалось загрузить расписание'))
  }
}

export const generateSchedule = async ({ user, monthDate = new Date() } = {}) => {
  if (USE_MOCK_AUTH) {
    return generateMockSchedule({ user, monthDate })
  }

  const venueId = firstDefined(user?.venue_id, user?.venue?.id, user?.venue)

  if (venueId === undefined || venueId === null || venueId === '') {
    throw new Error('Не удалось определить объект для генерации расписания')
  }

  const range = buildMonthRange(monthDate)

  try {
    const response = await api.post('/schedule/generate/', {
      venue: venueId,
      year: range.year,
      month: range.month
    })

    return response.data
  } catch (error) {
    throw new Error(extractErrorMessage(error, 'Не удалось запустить генерацию расписания'))
  }
}

export const publishSchedule = async ({ scheduleId, monthDate = new Date() } = {}) => {
  if (!scheduleId) {
    throw new Error('Не удалось определить расписание для публикации')
  }

  if (USE_MOCK_AUTH) {
    const range = buildMonthRange(monthDate)
    const saved = getStoredMockMonths()
    const monthData = saved[range.monthKey]

    if (monthData && monthData.scheduleId === scheduleId) {
      saved[range.monthKey] = {
        ...monthData,
        status: 'published'
      }

      localStorage.setItem(MOCK_SCHEDULE_STORAGE_KEY, JSON.stringify(saved))
    }

    return { schedule_id: scheduleId, status: 'published' }
  }

  try {
    const response = await api.post(`/schedule/monthly/${scheduleId}/publish/`)
    return response.data
  } catch (error) {
    throw new Error(extractErrorMessage(error, 'Не удалось опубликовать расписание'))
  }
}
