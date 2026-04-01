import api from '../api'

const FALLBACK_GET_STATUSES = new Set([400, 404, 405])
const INACTIVE_STATUSES = new Set([
  'cancelled',
  'canceled',
  'day_off',
  'off',
  'rejected',
  'removed',
  'unassigned'
])

const LIST_KEYS = ['results', 'items', 'data', 'entries', 'assignments', 'schedules']
const DETAIL_LIST_KEYS = ['slots', 'assignments', 'entries']

const isObject = (value) =>
  value !== null && typeof value === 'object' && !Array.isArray(value)

const firstDefined = (...values) =>
  values.find((value) => value !== undefined && value !== null && value !== '')

const asArray = (value) => (Array.isArray(value) ? value : [])

const padNumber = (value) => String(value).padStart(2, '0')

const formatDate = (date) =>
  `${date.getFullYear()}-${padNumber(date.getMonth() + 1)}-${padNumber(date.getDate())}`

const buildMonthRange = (monthDate = new Date()) => {
  const currentMonth = new Date(monthDate.getFullYear(), monthDate.getMonth(), 1)
  const nextMonth = new Date(monthDate.getFullYear(), monthDate.getMonth() + 1, 1)
  const lastDayOfMonth = new Date(nextMonth.getTime() - 24 * 60 * 60 * 1000)

  return {
    month: currentMonth.getMonth() + 1,
    monthKey: `${currentMonth.getFullYear()}-${padNumber(currentMonth.getMonth() + 1)}`,
    year: currentMonth.getFullYear(),
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
    if (startHours < 13) {
      return 'morning'
    }

    return 'evening'
  }

  return 'shift'
}

const normalizeEmployeeKey = (item, employee) => {
  const raw = firstDefined(
    item.employee_key,
    item.employee_id,
    item.assigned_employee,
    item.waiter_id,
    employee.employee_key,
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

const extractList = (payload, keys = LIST_KEYS) => {
  if (Array.isArray(payload)) {
    return payload
  }

  if (!isObject(payload)) {
    return []
  }

  for (const key of keys) {
    const value = payload[key]

    if (Array.isArray(value)) {
      return value
    }

    if (isObject(value)) {
      const nested = extractList(value, keys)
      if (nested.length > 0) {
        return nested
      }
    }
  }

  return []
}

const normalizeScheduleEntry = (item, fallbackDate = '') => {
  if (!isObject(item)) {
    return null
  }

  const shift = isObject(item.shift) ? item.shift : {}
  const employee = isObject(item.employee)
    ? item.employee
    : isObject(item.user)
      ? item.user
      : isObject(item.worker)
        ? item.worker
        : {}

  const workStart = normalizeTimeValue(
    firstDefined(
      item.work_start,
      item.start_time,
      item.starts_at,
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
      shift.work_end,
      shift.end_time,
      shift.ends_at
    )
  )

  const calculatedHours = getHoursDifference(workStart, workEnd)
  const rawHours = firstDefined(item.work_hours, shift.work_hours, calculatedHours)
  const numericHours = rawHours === '' || rawHours === null || rawHours === undefined
    ? null
    : Number(rawHours)

  const employeeKey = normalizeEmployeeKey(item, employee)
  const date = normalizeDateValue(
    firstDefined(item.date, shift.date, item.day?.date, fallbackDate)
  )
  const status = String(
    firstDefined(item.status, item.assignment_status, item.slot_status, shift.status, '')
  ).toLowerCase()
  const rawIsWorking = firstDefined(item.is_working, shift.is_working)
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
    employee_key: employeeKey,
    employee_label: buildEmployeeLabel(item, employee, employeeKey),
    waiter_num: firstDefined(item.waiter_num, employee.waiter_num, employee.id, employeeKey),
    grade: firstDefined(item.grade, employee.grade, employee.role, employee.position, null),
    shift_type: normalizeShiftType(
      firstDefined(item.shift_type, item.type, shift.shift_type, shift.type),
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
  const rawItems = extractList(payload)

  if (rawItems.length === 0) {
    return {
      entries: [],
      scheduleExists: false,
      recognizable: true
    }
  }

  const entries = rawItems
    .map((item) => normalizeScheduleEntry(item))
    .filter(Boolean)

  return {
    entries,
    scheduleExists: rawItems.length > 0,
    recognizable: entries.length > 0
  }
}

const flattenMonthlyDetail = (payload) => {
  if (!isObject(payload)) {
    return []
  }

  const directItems = extractList(payload, DETAIL_LIST_KEYS)
  const slotEntryItems = asArray(payload.slots).flatMap((slot) =>
    asArray(slot?.entries).map((entry) => ({
      ...slot,
      ...entry,
      employee_id: firstDefined(entry?.employee_id, slot?.employee_id, slot?.assigned_employee),
      employee_label: firstDefined(
        entry?.employee_label,
        slot?.employee_label,
        slot?.employee_name
      ),
      assignment_status: firstDefined(entry?.assignment_status, slot?.assignment_status),
      waiter_num: firstDefined(entry?.waiter_num, slot?.waiter_num)
    }))
  )
  const dayItems = asArray(payload.days).flatMap((day) =>
    asArray(day?.slots).map((slot) => ({
      ...slot,
      date: firstDefined(slot?.date, day?.date)
    }))
  )

  return [...slotEntryItems, ...dayItems, ...directItems]
}

const normalizeMonthlyDetail = (payload) => {
  const rawItems = flattenMonthlyDetail(payload)
  const entries = rawItems
    .map((item) => normalizeScheduleEntry(item))
    .filter(Boolean)

  return {
    entries,
    scheduleExists: Boolean(payload?.id) || rawItems.length > 0,
    recognizable: Boolean(payload?.id) || rawItems.length > 0
  }
}

const extractScheduleId = (schedule) =>
  firstDefined(schedule.id, schedule.schedule_id, schedule.monthly_schedule_id)

const extractSchedulePeriod = (schedule) => {
  const explicitYear = Number(firstDefined(schedule?.year, schedule?.schedule_year))
  const explicitMonth = Number(firstDefined(schedule?.month, schedule?.schedule_month))

  if (Number.isInteger(explicitYear) && Number.isInteger(explicitMonth)) {
    return {
      year: explicitYear,
      month: explicitMonth
    }
  }

  const rawPeriod = String(
    firstDefined(schedule?.period, schedule?.start_date, schedule?.date, '')
  )
  const matchedPeriod = rawPeriod.match(/^(\d{4})-(\d{2})/)

  if (!matchedPeriod) {
    return {
      year: null,
      month: null
    }
  }

  return {
    year: Number(matchedPeriod[1]),
    month: Number(matchedPeriod[2])
  }
}

const pickMonthlySchedule = (schedules, monthDate) => {
  if (!Array.isArray(schedules) || schedules.length === 0) {
    return null
  }

  const targetYear = monthDate.getFullYear()
  const targetMonth = monthDate.getMonth() + 1

  const scoredSchedules = schedules
    .map((schedule, index) => {
      const { year, month } = extractSchedulePeriod(schedule)
      const status = String(schedule.status || '').toLowerCase()
      const monthMatches = year === targetYear && month === targetMonth
      const score =
        (monthMatches ? 100 : 0) +
        (status === 'published' ? 20 : 0) +
        (status === 'draft' ? 10 : 0) +
        (schedules.length - index)

      return {
        schedule,
        score
      }
    })
    .sort((left, right) => right.score - left.score)

  return scoredSchedules[0]?.schedule || null
}

const buildScheduleQueryParams = (monthDate, user) => {
  const range = buildMonthRange(monthDate)
  const venueId = firstDefined(user?.venue_id, user?.venue?.id, user?.venue)
  const params = {
    month: range.month,
    year: range.year,
    date_from: range.startDate,
    date_to: range.endDate,
    start_date: range.startDate,
    end_date: range.endDate
  }

  if (venueId !== undefined && venueId !== null && venueId !== '') {
    params.venue = venueId
  }

  return params
}

const shouldTryGetFallback = (error) => FALLBACK_GET_STATUSES.has(error?.response?.status)

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

  return Object.entries(data)
    .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(', ') : value}`)
    .join('; ') || fallbackMessage
}

export const fetchScheduleForMonth = async ({ monthDate = new Date(), user = null } = {}) => {
  const params = buildScheduleQueryParams(monthDate, user)

  try {
    const response = await api.get('/schedule/', { params })
    const normalized = normalizeScheduleCollection(response.data)

    if (normalized.recognizable) {
      return {
        ...normalized,
        source: '/schedule/'
      }
    }
  } catch (error) {
    if (!shouldTryGetFallback(error)) {
      throw new Error(extractErrorMessage(error, 'Не удалось загрузить расписание'))
    }
  }

  try {
    const response = await api.get('/schedule/monthly/', { params })
    const schedules = extractList(response.data)

    if (schedules.length === 0) {
      return {
        entries: [],
        scheduleExists: false,
        source: '/schedule/monthly/'
      }
    }

    const selectedSchedule = pickMonthlySchedule(schedules, monthDate)
    const selectedScheduleId = extractScheduleId(selectedSchedule)

    if (!selectedScheduleId) {
      return {
        entries: [],
        scheduleExists: true,
        source: '/schedule/monthly/'
      }
    }

    const detailResponse = await api.get(`/schedule/monthly/${selectedScheduleId}/`)
    return {
      ...normalizeMonthlyDetail(detailResponse.data),
      source: `/schedule/monthly/${selectedScheduleId}/`
    }
  } catch (error) {
    throw new Error(extractErrorMessage(error, 'Не удалось загрузить расписание'))
  }
}

export const generateSchedule = async ({ user } = {}) => {
  const venueId = firstDefined(user?.venue_id, user?.venue?.id, user?.venue)

  if (venueId === undefined || venueId === null || venueId === '') {
    throw new Error('Не удалось определить объект для генерации расписания')
  }

  try {
    const response = await api.post('/schedule/generate/', { venue: venueId })
    return response.data
  } catch (error) {
    const status = error?.response?.status

    if (status !== 404 && status !== 405) {
      throw new Error(extractErrorMessage(error, 'Не удалось запустить генерацию расписания'))
    }
  }

  try {
    const response = await api.post('/forecast/generate-schedule/', { venue: venueId })
    return response.data
  } catch (error) {
    throw new Error(extractErrorMessage(error, 'Не удалось запустить генерацию расписания'))
  }
}
