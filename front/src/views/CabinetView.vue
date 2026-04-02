<template>
  <div class="cabinet-page">
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
          <button class="side-menu-item active" @click="goToProfile">
            Профиль
          </button>
          <button class="side-menu-item" @click="goToSchedule">
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

    <header class="cabinet-header">
      <div class="menu-container">
        <button class="menu-button" @click="openMenu" aria-label="Открыть меню">
          <span></span>
          <span></span>
          <span></span>
        </button>
      </div>
    </header>

    <main class="cabinet-content">
      <section class="profile-card">
        <div class="profile-card-top">
          <div class="profile-heading">
            <p class="profile-subtitle">Личный кабинет</p>
            <h1 class="cabinet-title">Профиль</h1>
          </div>
        </div>

        <div class="profile-info-block">
          <p><strong>Логин:</strong> {{ user.username }}</p>
          <p><strong>Email:</strong> {{ user.email }}</p>
          <p><strong>Имя:</strong> {{ user.first_name }}</p>
          <p><strong>Фамилия:</strong> {{ user.last_name }}</p>
          <p><strong>Телефон:</strong> {{ user.phone || 'Не указан' }}</p>
          <p><strong>Роль:</strong> {{ roleRu }}</p>
          <p><strong>Заведение:</strong> {{ currentVenueLabel }}</p>
        </div>

        <div class="manager-actions">
          <button class="wide-button secondary" @click="openEmployeesModal">
            Посмотреть сотрудников
          </button>

          <button
            v-if="canManagePeople"
            class="wide-button secondary"
            @click="openCreateRoleModal"
          >
            Добавить сотрудника
          </button>
        </div>
      </section>
    </main>

    <transition name="modal-fade">
      <div v-if="showEmployeesModal" class="modal-overlay" @click.self="closeEmployeesModal">
        <div class="modal-card">
          <div class="modal-header">
            <div>
              <p class="modal-subtitle">Команда</p>
              <h2 class="modal-title">Сотрудники</h2>
            </div>
            <button class="modal-close" @click="closeEmployeesModal">×</button>
          </div>

          <div class="role-groups">
            <div class="role-stat-card">
              <span class="role-stat-label">Админы</span>
              <strong class="role-stat-value">{{ groupedEmployees.admin.length }}</strong>
            </div>
            <div class="role-stat-card">
              <span class="role-stat-label">Менеджеры</span>
              <strong class="role-stat-value">{{ groupedEmployees.manager.length }}</strong>
            </div>
            <div class="role-stat-card">
              <span class="role-stat-label">Официанты-стажеры</span>
              <strong class="role-stat-value">{{ groupedEmployees.employee_noob.length }}</strong>
            </div>
            <div class="role-stat-card">
              <span class="role-stat-label">Официанты-профи</span>
              <strong class="role-stat-value">{{ groupedEmployees.employee_pro.length }}</strong>
            </div>
          </div>

          <div v-if="isLoadingEmployees" class="form-alert success">
            Загружаем список сотрудников...
          </div>

          <div v-else-if="employeesError" class="form-alert error">
            {{ employeesError }}
          </div>

          <div v-else class="employee-sections">
            <section
              v-for="section in employeeSections"
              :key="section.key"
              class="employee-section"
            >
              <div class="employee-section-head">
                <h3>{{ section.title }}</h3>
                <span>{{ section.items.length }}</span>
              </div>

              <div v-if="section.items.length === 0" class="employee-empty">
                Нет сотрудников в этой группе
              </div>

              <div v-else class="employee-list">
                <article
                  v-for="employee in section.items"
                  :key="employee.id || employee.username"
                  class="employee-card"
                >
                  <div class="employee-card-head">
                    <strong>{{ getEmployeeFullName(employee) }}</strong>
                    <span class="employee-role-chip">{{ getRoleLabel(employee.role) }}</span>
                  </div>
                  <p>{{ employee.username }}</p>
                  <p>{{ employee.email || 'Email не указан' }}</p>
                  <p>{{ employee.phone || 'Телефон не указан' }}</p>
                  <p>Заведение: {{ getVenueLabel(employee) }}</p>
                </article>
              </div>
            </section>
          </div>
        </div>
      </div>
    </transition>

    <transition name="modal-fade">
      <div v-if="showCreateRoleModal" class="modal-overlay" @click.self="closeCreateRoleModal">
        <div class="modal-card">
          <div class="modal-header">
            <div>
              <p class="modal-subtitle">{{ roleRu }}</p>
              <h2 class="modal-title">Создание сотрудника</h2>
            </div>
            <button class="modal-close" @click="closeCreateRoleModal">×</button>
          </div>

          <form class="role-form" @submit.prevent="submitCreateRole">
            <div v-if="createRoleError" class="form-alert error">
              {{ createRoleError }}
            </div>

            <div v-if="createRoleSuccess" class="form-alert success">
              {{ createRoleSuccess }}
            </div>

            <div v-if="copyNotice" class="copy-notice">
              {{ copyNotice }}
            </div>

            <div class="form-grid">
              <label class="form-field">
                <span>Username *</span>
                <input
                  v-model.trim="createRoleForm.username"
                  type="text"
                  placeholder="nickname"
                  required
                  :disabled="isCreatingRole"
                />
              </label>

              <label class="form-field">
                <span>Email *</span>
                <input
                  v-model.trim="createRoleForm.email"
                  type="email"
                  placeholder="bagbag@gmail.com"
                  required
                  :disabled="isCreatingRole"
                />
              </label>

              <label class="form-field">
                <span>Имя *</span>
                <input
                  v-model.trim="createRoleForm.first_name"
                  type="text"
                  placeholder="имя"
                  required
                  :disabled="isCreatingRole"
                />
              </label>

              <label class="form-field">
                <span>Фамилия *</span>
                <input
                  v-model.trim="createRoleForm.last_name"
                  type="text"
                  placeholder="фамилия"
                  required
                  :disabled="isCreatingRole"
                />
              </label>

              <label class="form-field">
                <span>Пароль *</span>
                <input
                  v-model="createRoleForm.password"
                  type="text"
                  placeholder="********"
                  minlength="8"
                  required
                  :disabled="isCreatingRole"
                />
              </label>

              <label class="form-field">
                <span>Подтверждение пароля *</span>
                <input
                  v-model="createRoleForm.password_confirm"
                  type="text"
                  placeholder="********"
                  minlength="8"
                  required
                  :disabled="isCreatingRole"
                />
              </label>

              <div class="form-field form-field-full">
                <button
                  type="button"
                  class="copy-button copy-button-wide"
                  :disabled="!createRoleForm.username || !createRoleForm.password || isCreatingRole"
                  @click="copyCredentials"
                >
                  Скопировать логин и пароль
                </button>
              </div>

              <label class="form-field">
                <span>Телефон</span>
                <input
                  v-model.trim="createRoleForm.phone"
                  type="tel"
                  placeholder="+79990007766"
                  :disabled="isCreatingRole"
                />
              </label>

              <label class="form-field">
                <span>Роль *</span>
                <select v-model="createRoleForm.role" :disabled="isCreatingRole">
                  <option
                    v-for="option in availableRoleOptions"
                    :key="option.value"
                    :value="option.value"
                  >
                    {{ option.label }}
                  </option>
                </select>
              </label>

              <label
                v-if="currentUserRole === 'manager'"
                class="form-field form-field-full"
              >
                <span>Заведение</span>
                <input
                  :value="currentVenueLabel"
                  type="text"
                  disabled
                />
              </label>

              <label
                v-if="currentUserRole === 'admin'"
                class="form-field form-field-full"
              >
                <span>Заведение</span>
                <select v-model="createRoleForm.venue" :disabled="isCreatingRole">
                  <option disabled value="">Выберите ресторан</option>
                  <option
                    v-for="venue in venues"
                    :key="venue.id"
                    :value="venue.id"
                  >
                    {{ venue.venue_name || venue.name || `Заведение #${venue.id}` }}
                  </option>
                </select>
              </label>
            </div>

            <div class="form-actions">
              <button
                type="button"
                class="wide-button secondary"
                @click="closeCreateRoleModal"
                :disabled="isCreatingRole"
              >
                Отмена
              </button>
              <button type="submit" class="wide-button" :disabled="isCreatingRole">
                {{ isCreatingRole ? 'Создание...' : 'Создать сотрудника' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </transition>
  </div>
</template>

<script>
import '../assets/cabinet.css'
import api from '../api'
import { fetchCurrentUser, logoutUser } from '../services/auth'

const ROLE_LABELS = {
  admin: 'Администратор',
  manager: 'Менеджер',
  employee_noob: 'Официант-стажер',
  employee_pro: 'Официант-профи'
}

const getDefaultCreateRoleForm = () => ({
  username: '',
  password: '',
  password_confirm: '',
  email: '',
  first_name: '',
  last_name: '',
  phone: '',
  role: 'employee_noob',
  venue: '',
  venue_name: ''
})

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

const normalizeRole = (role) => String(role || '').toLowerCase()

const getVenueId = (entity) => {
  const raw = entity?.venue_id ?? entity?.venue?.id ?? entity?.venue
  return raw === undefined || raw === null || raw === '' ? null : Number(raw)
}

export default {
  name: 'CabinetView',
  data() {
    let savedUser = null

    try {
      savedUser = JSON.parse(localStorage.getItem('user') || 'null')
    } catch (error) {
      savedUser = null
    }

    return {
      menuOpen: false,
      showEmployeesModal: false,
      showCreateRoleModal: false,
      isLoadingEmployees: false,
      isCreatingRole: false,
      employeesError: '',
      createRoleError: '',
      createRoleSuccess: '',
      copyNotice: '',
      employees: [],
      venues: [],
      createRoleForm: getDefaultCreateRoleForm(),
      user: savedUser || {
        username: '',
        email: '',
        first_name: '',
        last_name: '',
        phone: '',
        role: '',
        venue: '',
        venue_name: ''
      }
    }
  },
  computed: {
    currentUserRole() {
      return normalizeRole(this.user.role)
    },
    canManagePeople() {
      return this.currentUserRole === 'manager' || this.currentUserRole === 'admin'
    },
    currentVenueId() {
      return getVenueId(this.user)
    },
    currentVenueLabel() {
      return this.getVenueLabel(this.user)
    },
    roleRu() {
      return ROLE_LABELS[this.currentUserRole] || this.user.role || 'Не указано'
    },
    availableRoleOptions() {
      if (this.currentUserRole === 'manager') {
        return [
          { value: 'employee_noob', label: ROLE_LABELS.employee_noob },
          { value: 'employee_pro', label: ROLE_LABELS.employee_pro }
        ]
      }

      if (this.currentUserRole === 'admin') {
        return [
          { value: 'employee_noob', label: ROLE_LABELS.employee_noob },
          { value: 'employee_pro', label: ROLE_LABELS.employee_pro },
          { value: 'manager', label: ROLE_LABELS.manager },
          { value: 'admin', label: ROLE_LABELS.admin }
        ]
      }

      return []
    },
    visibleEmployees() {
      const normalizedEmployees = this.employees.filter((employee) => {
        const role = normalizeRole(employee.role)
        return ['admin', 'manager', 'employee_noob', 'employee_pro'].includes(role)
      })

      if (this.currentUserRole === 'admin') {
        return normalizedEmployees
      }

      if (
        this.currentUserRole === 'manager' ||
        this.currentUserRole === 'employee_noob' ||
        this.currentUserRole === 'employee_pro'
      ) {
        return normalizedEmployees.filter(
          (employee) =>
            normalizeRole(employee.role) === 'admin' ||
            (getVenueId(employee) !== null && getVenueId(employee) === this.currentVenueId)
        )
      }

      return []
    },
    groupedEmployees() {
      const groups = {
        admin: [],
        manager: [],
        employee_noob: [],
        employee_pro: []
      }

      this.visibleEmployees.forEach((employee) => {
        const role = normalizeRole(employee.role)

        if (groups[role]) {
          groups[role].push(employee)
        }
      })

      Object.keys(groups).forEach((key) => {
        groups[key].sort((left, right) =>
          this.getEmployeeFullName(left).localeCompare(this.getEmployeeFullName(right), 'ru')
        )
      })

      return groups
    },
    employeeSections() {
      return [
        { key: 'admin', title: 'Администраторы', items: this.groupedEmployees.admin },
        { key: 'manager', title: 'Менеджеры', items: this.groupedEmployees.manager },
        { key: 'employee_noob', title: 'Официанты-стажеры', items: this.groupedEmployees.employee_noob },
        { key: 'employee_pro', title: 'Официанты-профи', items: this.groupedEmployees.employee_pro }
      ]
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
          console.error('Ошибка чтения user из localStorage', parseError)
        }
      } else {
        console.error('Не удалось получить пользователя с бэка', error)
      }
    }

    if (this.currentUserRole === 'admin') {
      await this.loadVenues()
    }
  },
  beforeUnmount() {
    if (this.copyNoticeTimer) {
      clearTimeout(this.copyNoticeTimer)
    }
  },
  methods: {
    getRoleLabel(role) {
      return ROLE_LABELS[normalizeRole(role)] || role || 'Не указано'
    },
    getEmployeeFullName(employee) {
      const fullName = [employee?.first_name, employee?.last_name].filter(Boolean).join(' ').trim()
      return fullName || employee?.username || 'Без имени'
    },
    getVenueLabel(entity) {
      return (
        entity?.venue_name ||
        entity?.venue?.venue_name ||
        entity?.venue?.name ||
        (getVenueId(entity) !== null ? `Заведение #${getVenueId(entity)}` : 'Не указано')
      )
    },
    async loadVenues() {
      try {
        const response = await api.get('/venues/')
        this.venues = asArray(response.data)
      } catch (error) {
        console.error('Не удалось загрузить заведения', error)
        this.venues = []
      }
    },
    async loadEmployees() {
      this.isLoadingEmployees = true
      this.employeesError = ''

      try {
        const response = await api.get('/users/')
        this.employees = asArray(response.data)
      } catch (error) {
        this.employees = []
        this.employeesError = this.extractErrorMessage(error, 'Не удалось загрузить сотрудников')
      } finally {
        this.isLoadingEmployees = false
      }
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
    goToSchedule() {
      this.menuOpen = false
      this.$router.push('/schedule')
    },
    async handleLogout() {
      this.menuOpen = false
      await logoutUser()
      this.$router.replace('/login')
    },
    async openEmployeesModal() {
      this.showEmployeesModal = true
      await this.loadEmployees()
    },
    closeEmployeesModal() {
      if (this.isLoadingEmployees) {
        return
      }

      this.showEmployeesModal = false
      this.employeesError = ''
    },
    openCreateRoleModal() {
      this.createRoleError = ''
      this.createRoleSuccess = ''
      this.copyNotice = ''

      this.createRoleForm = {
        ...getDefaultCreateRoleForm(),
        venue: this.currentVenueId || '',
        venue_name: this.currentVenueLabel
      }

      if (this.currentUserRole === 'manager') {
        this.createRoleForm.role = 'employee_noob'
      }

      this.showCreateRoleModal = true
    },
    closeCreateRoleModal() {
      if (this.isCreatingRole) {
        return
      }

      this.showCreateRoleModal = false
      this.createRoleError = ''
      this.createRoleSuccess = ''
      this.copyNotice = ''
    },
    buildCreateRolePayload() {
      const payload = {
        username: this.createRoleForm.username,
        password: this.createRoleForm.password,
        password_confirm: this.createRoleForm.password_confirm,
        email: this.createRoleForm.email,
        first_name: this.createRoleForm.first_name,
        last_name: this.createRoleForm.last_name,
        phone: this.createRoleForm.phone || undefined,
        role: this.createRoleForm.role || 'employee_noob'
      }

      if (this.currentUserRole === 'admin') {
        if (this.createRoleForm.venue) {
          payload.venue = Number(this.createRoleForm.venue)
        }
      } else if (this.currentUserRole === 'manager' && this.currentVenueId !== null) {
        payload.venue = this.currentVenueId
      }

      return payload
    },
    extractErrorMessage(error, fallbackMessage = 'Не удалось выполнить запрос') {
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
          .map(([key, value]) => {
            const normalizedValue = Array.isArray(value) ? value.join(', ') : value
            return `${key}: ${normalizedValue}`
          })
          .join('; ') || fallbackMessage
      )
    },
    async copyText(value, successMessage) {
      if (!value) {
        return
      }

      try {
        await navigator.clipboard.writeText(String(value))
        this.showCopyNotice(successMessage)
      } catch (error) {
        this.showCopyNotice('Не удалось скопировать')
      }
    },
    async copyCredentials() {
      const username = this.createRoleForm.username?.trim()
      const password = this.createRoleForm.password

      if (!username || !password) {
        return
      }

      const payload = `Логин: ${username}\nПароль: ${password}`
      await this.copyText(payload, 'Логин и пароль скопированы')
    },
    showCopyNotice(message) {
      this.copyNotice = message

      if (this.copyNoticeTimer) {
        clearTimeout(this.copyNoticeTimer)
      }

      this.copyNoticeTimer = setTimeout(() => {
        this.copyNotice = ''
      }, 1800)
    },
    async submitCreateRole() {
      this.createRoleError = ''
      this.createRoleSuccess = ''

      if (this.createRoleForm.password !== this.createRoleForm.password_confirm) {
        this.createRoleError = 'Пароли должны совпадать'
        return
      }

      this.isCreatingRole = true

      try {
        await api.post('/auth/register/', this.buildCreateRolePayload())
        this.createRoleSuccess = 'Сотрудник успешно создан'

        if (this.showEmployeesModal) {
          await this.loadEmployees()
        }
      } catch (error) {
        this.createRoleError = this.extractErrorMessage(error, 'Не удалось создать сотрудника')
      } finally {
        this.isCreatingRole = false
      }
    }
  }
}
</script>
