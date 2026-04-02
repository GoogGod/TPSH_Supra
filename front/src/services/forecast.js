import api from '../api'

const asArray = (payload) => {
  if (Array.isArray(payload)) {
    return payload
  }

  if (Array.isArray(payload?.results)) {
    return payload.results
  }

  if (Array.isArray(payload?.items)) {
    return payload.items
  }

  if (Array.isArray(payload?.data)) {
    return payload.data
  }

  return []
}

const normalizeErrorMessage = (error, fallbackMessage = 'Не удалось загрузить данные') => {
  const data = error?.response?.data

  if (!data) {
    return error?.message || fallbackMessage
  }

  if (typeof data === 'string') {
    return data
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

export const uploadHistoricalForecastData = async (records) => {
  const items = asArray(records).filter(Boolean)

  if (!items.length) {
    throw new Error('Нет данных для загрузки')
  }

  const payloadVariants = [
    items,
    { data: items },
    { items },
    { records: items },
    { loads: items }
  ]

  let lastError = null

  for (const payload of payloadVariants) {
    try {
      const response = await api.post('/forecast/load-data/', payload)
      return response.data
    } catch (error) {
      lastError = error
      const status = Number(error?.response?.status)

      if (![400, 415, 422].includes(status)) {
        break
      }
    }
  }

  throw new Error(normalizeErrorMessage(lastError, 'Не удалось загрузить исторические данные'))
}
