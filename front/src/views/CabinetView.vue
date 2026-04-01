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
          <p><strong>Заведение:</strong> {{ user.venue }}</p>
          <p><strong>График:</strong> {{ user.schedule_pattern }}</p>
          <p><strong>Длительность смены:</strong> {{ user.shift_duration }}</p>
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
                  v-model="createRoleForm.password_confirm"
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

              <label v-if="isAdmin" class="form-field">
  <span>Заведение *</span>
  <select v-model="createRoleForm.venue" :disabled="isCreatingRole">
    <option value="" disabled>Выберите заведение</option>
    <option
      v-for="restaurant in restaurants"
      :key="restaurant.id"
      :value="restaurant.id"
    >
      {{ restaurant.name }}
    </option>
  </select>
</label>

<label v-else class="form-field">
  <span>Заведение</span>
  <input
    :value="managerVenueName"
    type="text"
    disabled
  />
</label>

<label class="form-field">
  <span>Заведение</span>
  <input
    v-model.trim="createRoleForm.venue"
    type="number"
    min="1"
    max="100"
    placeholder="1"
    :disabled="isCreatingRole"
  />
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
  password_confirm: '',
  email: '',
  first_name: '',
  last_name: '',
  phone: '',
  role: 'employee',
  venue: '',
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
        shift_duration: '',
        restaurants: []
      }
    }
  },
  computed: {
    isManager() {
      return this.user.role === 'MANAGER' || this.user.role === 'manager'
    },
    canCreateRoles() {
    const role = String(this.user.role || '').toUpperCase()
    return role === 'MANAGER' || role === 'ADMIN'
    },
    isAdmin() {
  return String(this.user.role || '').toUpperCase() === 'ADMIN'
},
managerVenueName() {
  if (!this.user.venue) return 'Не указано'
  if (typeof this.user.venue === 'object') {
    return this.user.venue.name || `ID: ${this.user.venue.id}`
  }
  const match = this.restaurants.find(item => String(item.id) === String(this.user.venue))
  return match ? match.name : `ID: ${this.user.venue}`
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
    },
availableRoleOptions() {
  const role = String(this.user.role || '').toUpperCase()

  if (role === 'MANAGER') {
    return [
      { value: 'employee', label: 'Официант / сотрудник' }
    ]
  }

  if (role === 'ADMIN') {
    return [
      { value: 'employee', label: 'Официант / сотрудник' },
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

    if (String(this.user.role || '').toUpperCase() === 'ADMIN') {
      await this.fetchRestaurants()
    }
  } catch (error) {
    const savedUser = localStorage.getItem('user')

    if (savedUser) {
      try {
        this.user = JSON.parse(savedUser)

        if (String(this.user.role || '').toUpperCase() === 'ADMIN') {
          await this.fetchRestaurants()
        }
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
    handleLogout() {
      this.menuOpen = false
      logoutUser()
      this.$router.replace('/login')
    },
    async fetchRestaurants() {
  try {
    const response = await api.get('/restaurants/')
    this.restaurants = Array.isArray(response.data) ? response.data : []
  } catch (error) {
    console.error('Не удалось загрузить список заведений', error)
    this.restaurants = []
  }
},
openCreateRoleModal() {
  this.createRoleError = ''
  this.createRoleSuccess = ''
  this.createRoleForm = {
    ...getDefaultCreateRoleForm(),
    venue: this.user.venue ? String(this.user.venue) : ''
  }

  const role = String(this.user.role || '').toUpperCase()

  if (role === 'MANAGER') {
    this.createRoleForm.role = 'EMPLOYEE'
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
        password_confirm: this.createRoleForm.password_confirm,
        email: this.createRoleForm.email,
        first_name: this.createRoleForm.first_name,
        last_name: this.createRoleForm.last_name,
        phone: this.createRoleForm.phone || undefined,
        role: this.createRoleForm.role || 'EMPLOYEE',
        schedule_pattern: this.createRoleForm.schedule_pattern || '4/2',
        shift_duration: this.createRoleForm.shift_duration || '14H'
      }

      if (this.createRoleForm.venue !== '' && this.createRoleForm.venue !== null) {
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

      if (this.createRoleForm.password !== this.createRoleForm.password_confirm) {
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