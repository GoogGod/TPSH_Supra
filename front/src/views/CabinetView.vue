<template>
  <div class="cabinet-page">
    <header class="cabinet-header">
      <button class="menu-button" @click="menuOpen = !menuOpen">☰</button>

      <transition name="fade">
        <div v-if="menuOpen" class="dropdown-menu">
          <button class="dropdown-item" @click="activeTab = 'profile'; menuOpen = false">
            Профиль
          </button>
          <button class="dropdown-item" @click="activeTab = 'schedule'; menuOpen = false">
            Расписание
          </button>
        </div>
      </transition>
    </header>

    <main class="cabinet-content">
      <template v-if="activeTab === 'profile'">
        <h1 class="cabinet-title">Профиль</h1>

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
      </template>

      <template v-else>
        <h1 class="cabinet-title">Расписание</h1>
        <p class="schedule-placeholder">Здесь позже будет расписание</p>
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
        username: 'IVANOV',
        email: 'IVANOV@MAIL.RU',
        first_name: 'Иван',
        last_name: 'Иванов',
        phone: '+79001234567',
        role: 'EMPLOYEE',
        venue: 1,
        schedule_pattern: '4/2',
        shift_duration: '14H'
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
        WAITER: 'Официант'
      }
      return roles[this.user.role] || this.user.role
    }
  }
}
</script>