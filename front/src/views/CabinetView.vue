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
          <p><strong>Заведение:</strong> {{ user.venue }}</p>
          <p><strong>График:</strong> {{ user.schedule_pattern }}</p>
          <p><strong>Длительность смены:</strong> {{ user.shift_duration }}</p>
        </div>

        <div v-if="isManager" class="manager-actions">
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
              <p class="modal-subtitle">Менеджер</p>
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
                <input v-model.trim="createRoleForm.username" type="text" required :disabled="isCreatingRole" />
              </label>

              <label class="form-field">
                <span>Email *</span>
                <input v-model.trim="createRoleForm.email" type="email" required :disabled="isCreatingRole" />
              </label>

              <label class="form-field">
                <span>Имя *</span>
                <input v-model.trim="createRoleForm.first_name" type="text" required :disabled="isCreatingRole" />
              </label>

              <label class="form-field">
                <span>Фамилия *</span>
                <input v-model.trim="createRoleForm.last_name" type="text" required :disabled="isCreatingRole" />
              </label>

              <label class="form-field">
                <span>Пароль *</span>
                <input v-model="createRoleForm.password" type="password" minlength="8" required :disabled="isCreatingRole" />
              </label>

              <label class="form-field">
                <span>Подтверждение пароля *</span>
                <input v-model="createRoleForm.password_confirmation" type="password" minlength="8" required :disabled="isCreatingRole" />
              </label>

              <label class="form-field">
                <span>Телефон</span>
                <input v-model.trim="createRoleForm.phone" type="tel" :disabled="isCreatingRole" />
              </label>

              <label class="form-field">
                <span>Роль</span>
                <select v-model="createRoleForm.role" :disabled="isCreatingRole">
                  <option value="EMPLOYEE">Официант / сотрудник</option>
                </select>
              </label>

              <label class="form-field">
                <span>Заведение (ID)</span>
                <input v-model.number="createRoleForm.venue" type="number" min="1" :disabled="isCreatingRole" />
              </label>

              <label class="form-field">
                <span>График</span>
                <select v-model="createRoleForm.schedule_pattern" :disabled="isCreatingRole">
                  <option value="4/2">4/2</option>
                  <option value="4/3">4/3</option>
                  <option value="3/2">3/2</option>
                  <option value="2/2">2/2</option>
                </select>
              </label>

              <label class="form-field form-field-full">
                <span>Длительность смены</span>
                <select v-model="createRoleForm.shift_duration" :disabled="isCreatingRole">
                  <option value="14H">14H</option>
                  <option value="8H">8H</option>
                  <option value="CUSTOM">CUSTOM</option>
                </select>
              </label>
            </div>

            <div class="form-actions">
              <button type="button" class="wide-button secondary" @click="closeCreateRoleModal" :disabled="isCreatingRole">
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
import { fetchCurrentUser } from '../services/auth'

const getDefaultCreateRoleForm = () => ({
  username: '',
  password: '',
  password_confirmation: '',
  email: '',
  first_name: '',
  last_name: '',
  phone: '',
  role: 'EMPLOYEE',
  venue: null,
  schedule_pattern: '4/2',
  shift_duration: '14H'
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
      user: savedUser || {
        username: '',
        email: '',
        first_name: '',
        last_name: '',
        phone: '',
        role: '',
        venue: '',
        schedule_pattern: '',
        shift_duration: ''
      }
    }
  },
  computed: {
    isManager() {
      return this.user.role === 'MANAGER' || this.user.role === 'manager'
    },
    roleRu() {
      const role = String(this.user.role || '').toUpperCase()

      const roles = {
        MANAGER: 'Менеджер',
        ADMIN: 'Администратор',
        EMPLOYEE: 'Сотрудник',
        WAITER: 'Официант'
      }

      return roles[role] || this.user.role || 'Не указано'
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
    goToSchedule() {
      this.menuOpen = false
      this.$router.push('/schedule')
    },
    openCreateRoleModal() {
      this.createRoleError = ''
      this.createRoleSuccess = ''
      this.createRoleForm = {
        ...getDefaultCreateRoleForm(),
        venue: typeof this.user.venue === 'number' ? this.user.venue : null
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
      const payload = {
        username: this.createRoleForm.username,
        password: this.createRoleForm.password,
        password_confirmation: this.createRoleForm.password_confirmation,
        email: this.createRoleForm.email,
        first_name: this.createRoleForm.first_name,
        last_name: this.createRoleForm.last_name,
        phone: this.createRoleForm.phone || undefined,
        role: this.createRoleForm.role || 'EMPLOYEE',
        schedule_pattern: this.createRoleForm.schedule_pattern || '4/2',
        shift_duration: this.createRoleForm.shift_duration || '14H'
      }

      if (this.createRoleForm.venue) {
        payload.venue = Number(this.createRoleForm.venue)
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