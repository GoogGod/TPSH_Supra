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
          <button class="wide-button">Создать расписание</button>
          <button class="wide-button secondary">Создать роль</button>
        </div>
      </section>
    </main>
  </div>
</template>

<script>
import '../assets/cabinet.css'
import { fetchCurrentUser } from '../services/auth'

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
    }
  }
}
</script>