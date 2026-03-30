<template>
  <div class="cabinet-page">
    <header class="cabinet-header">
          <transition name="sidebar-fade">
      <div v-if="menuOpen" class="sidebar-overlay" @click="menuOpen = false"></div>
    </transition>

    <transition name="sidebar-slide">
      <aside v-if="menuOpen" class="sidebar-menu">
        <button class="sidebar-close" @click="menuOpen = false" aria-label="Закрыть меню">
          ✕
        </button>

        <button class="sidebar-action-button" @click="activeTab = 'profile'; menuOpen = false">
          Профиль
        </button>

        <button class="sidebar-action-button" @click="activeTab = 'schedule'; menuOpen = false">
          Расписание
        </button>
      </aside>
    </transition>
    </header>

    <main class="cabinet-content">
      <template v-if="activeTab === 'profile'">
        <h1 class="cabinet-title">Личный кабинет</h1>

        <div class="cabinet-card">
          <div class="profile-info">
            <p><span>Логин:</span> {{ user.username }}</p>
            <p><span>Email:</span> {{ user.email }}</p>
            <p><span>Имя:</span> {{ user.first_name }}</p>
            <p><span>Фамилия:</span> {{ user.last_name }}</p>
            <p><span>Телефон:</span> {{ user.phone }}</p>
            <p><span>Роль:</span> {{ roleRu }}</p>
            <p><span>Заведение:</span> {{ user.venue }}</p>
            <p><span>График:</span> {{ user.schedule_pattern }}</p>
            <p><span>Длительность смены:</span> {{ user.shift_duration }}</p>
          </div>

          <div v-if="isManager" class="manager-actions">
            <button class="wide-button">Создать расписание</button>
            <button class="wide-button">Создать роль</button>
          </div>
        </div>
      </template>

      <template v-else>
        <h1 class="cabinet-title">Расписание</h1>

        <div class="cabinet-card">
          <p class="schedule-placeholder">Здесь позже будет расписание</p>
        </div>
      </template>
    </main>
  </div>
</template>

<script>
import '../assets/cabinet.css'

export default {
  name: 'CabinetView',
  data() {
    return {
      menuOpen: false,
      activeTab: 'profile',
      user: {
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
      return this.user.role === 'MANAGER'
    },
    roleRu() {
      const roles = {
        MANAGER: 'Менеджер',
        ADMIN: 'Администратор',
        WAITER: 'Официант',
        EMPLOYEE: 'Сотрудник'
      }
      return roles[this.user.role] || this.user.role || 'Не указана'
    }
  },
  mounted() {
    const savedUser = localStorage.getItem('user')

    if (savedUser) {
      try {
        this.user = JSON.parse(savedUser)
      } catch (e) {
        console.error('Ошибка чтения user из localStorage', e)
      }
    }
  },
  methods: {
    logout() {
      localStorage.removeItem('access')
      localStorage.removeItem('refresh')
      localStorage.removeItem('isAuthenticated')
      localStorage.removeItem('user')
      this.$router.push('/login')
    }
  }
}
</script>