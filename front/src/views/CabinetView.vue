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
          <button class="side-menu-close" @click="closeMenu">✕</button>
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
          <p><strong>Телефон:</strong> {{ user.phone }}</p>
          <p><strong>Роль:</strong> {{ roleRu }}</p>
          <p><strong>Заведение:</strong> {{ user.venue_name || user.venue }}</p>
        </div>

        <div v-if="canCreateRoles" class="manager-actions">
          <button class="wide-button secondary" @click="openCreateRoleModal">
            Создать роль
          </button>
        </div>
      </section>
    </main>

    <transition name="modal-fade">
      <div v-if="showCreateRoleModal" class="modal-overlay" @click.self="closeCreateRoleModal">
        <div class="modal-card">
          <div class="modal-header">
            <div>
              <p class="modal-subtitle">{{ roleRu }}</p>
              <h2 class="modal-title">Создание сотрудника</h2>
            </div>
            <button class="modal-close" @click="closeCreateRoleModal">✕</button>
          </div>

          <form class="role-form" @submit.prevent="submitCreateRole">
            <div v-if="createRoleError" class="form-alert error">
              {{ createRoleError }}
            </div>

            <div v-if="createRoleSuccess" class="form-alert success">
              {{ createRoleSuccess }}
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
                  type="password"
                  placeholder="********"
                  minlength="8"
                  required
                  :disabled="isCreatingRole"
                />
              </label>

              <label class="form-field">
                <span>Подтверждение пароля *</span>
                <input
                  v-model="createRoleForm.password_confirmation"
                  type="password"
                  placeholder="********"
                  minlength="8"
                  required
                  :disabled="isCreatingRole"
                />
              </label>

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
                v-if="String(user.role || '').toLowerCase() === 'manager'"
                class="form-field form-field-full"
              >
                <span>Заведение</span>
                <input
                  :value="user.venue_name || createRoleForm.venue_name"
                  type="text"
                  disabled
                />
              </label>

              <label
                v-if="String(user.role || '').toLowerCase() === 'admin'"
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
                    {{ venue.venue_name }}
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

const getDefaultCreateRoleForm = () => ({
  username: '',
  password: '',
  password_confirmation: '',
  email: '',
  first_name: '',
  last_name: '',
  phone: '',
  role: 'employee_noob',
  venue: '',
  venue_name: ''
})

export default {
  name: 'CabinetView',
  data() {
    let savedUser = null

    try {
      savedUser = JSON.parse(localStorage.getItem('user') || 'null')
    } catch (e) {
      savedUser = null
    }

    return {
      menuOpen: false,
      activeTab: 'profile',
      showCreateRoleModal: false,
      isCreatingRole: false,
      createRoleError: '',
      createRoleSuccess: '',
      createRoleForm: getDefaultCreateRoleForm(),
      venues: [],
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
    isManager() {
      return String(this.user.role || '').toLowerCase() === 'manager'
    },
    canCreateRoles() {
      const role = String(this.user.role || '').toLowerCase()
      return role === 'manager' || role === 'admin'
    },
    roleRu() {
      const role = String(this.user.role || '').toLowerCase()

      const roles = {
        manager: 'Менеджер',
        admin: 'Администратор',
        employee_noob: 'Официант-новичок',
        employee_pro: 'Официант-профи'
      }

      return roles[role] || this.user.role || 'Не указано'
    },
    availableRoleOptions() {
      const role = String(this.user.role || '').toLowerCase()

      if (role === 'manager') {
        return [
          { value: 'employee_noob', label: 'Официант-новичок' },
          { value: 'employee_pro', label: 'Официант-профи' }
        ]
      }

      if (role === 'admin') {
        return [
          { value: 'employee_noob', label: 'Официант-новичок' },
          { value: 'employee_pro', label: 'Официант-профи' },
          { value: 'manager', label: 'Менеджер' },
          { value: 'admin', label: 'Администратор' }
        ]
      }

      return []
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
        } catch (e) {
          console.error('Ошибка чтения user из localStorage', e)
        }
      } else {
        console.error('Не удалось получить пользователя с бэка', error)
      }
    }

    const role = String(this.user.role || '').toLowerCase()
    if (role === 'admin') {
      await this.loadVenues()
    }
  },
  methods: {
    async loadVenues() {
      try {
        const response = await api.get('/api/v1/venues/')
        this.venues = response.data || []
      } catch (error) {
        console.error('Не удалось загрузить заведения', error)
        this.venues = []
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
    handleLogout() {
      this.menuOpen = false
      logoutUser()
      this.$router.replace('/login')
    },
    openCreateRoleModal() {
      this.createRoleError = ''
      this.createRoleSuccess = ''

      const currentUserRole = String(this.user.role || '').toLowerCase()

      this.createRoleForm = {
        ...getDefaultCreateRoleForm(),
        venue: this.user.venue || '',
        venue_name: this.user.venue_name || ''
      }

      if (currentUserRole === 'manager') {
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
    },
    buildCreateRolePayload() {
      const currentUserRole = String(this.user.role || '').toLowerCase()

      const payload = {
        username: this.createRoleForm.username,
        password: this.createRoleForm.password,
        password_confirmation: this.createRoleForm.password_confirmation,
        email: this.createRoleForm.email,
        first_name: this.createRoleForm.first_name,
        last_name: this.createRoleForm.last_name,
        phone: this.createRoleForm.phone || undefined,
        role: this.createRoleForm.role || 'employee_noob'
      }

      if (currentUserRole === 'admin') {
        if (this.createRoleForm.venue) {
          payload.venue = Number(this.createRoleForm.venue)
        }
      } else if (currentUserRole === 'manager') {
        payload.venue = Number(this.user.venue)
      }

      return payload
    },
    extractErrorMessage(error) {
      const data = error?.response?.data

      if (!data) {
        return error?.message || 'Не удалось создать сотрудника'
      }

      if (typeof data === 'string') {
        return data
      }

      if (data.detail) {
        return Array.isArray(data.detail) ? data.detail.join(', ') : data.detail
      }

      return Object.entries(data)
        .map(([key, value]) => {
          const normalizedValue = Array.isArray(value) ? value.join(', ') : value
          return `${key}: ${normalizedValue}`
        })
        .join('; ')
    },
    async submitCreateRole() {
      this.createRoleError = ''
      this.createRoleSuccess = ''

      if (this.createRoleForm.password !== this.createRoleForm.password_confirmation) {
        this.createRoleError = 'Пароли должны совпадать'
        return
      }

      this.isCreatingRole = true

      try {
        await api.post('/auth/register/', this.buildCreateRolePayload())
        this.createRoleSuccess = 'Сотрудник успешно создан'
        this.createRoleForm = getDefaultCreateRoleForm()
      } catch (error) {
        this.createRoleError = this.extractErrorMessage(error)
      } finally {
        this.isCreatingRole = false
      }
    }
  }
}
</script>