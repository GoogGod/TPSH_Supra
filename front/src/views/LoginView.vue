<template>
  <div class="auth-page">
    <img src="/src/assets/S_height.png" alt="logo" class="top-right-image" />

    <div class="supra-login-card">
      <h1>Авторизация</h1>

      <form @submit.prevent="handleLogin">
        <div v-if="errorMessage" class="error-message">
          {{ errorMessage }}
        </div>

        <div class="input-group">
          <label>Имя пользователя</label>
          <input
            v-model="username"
            type="text"
            required
            placeholder="username"
            :disabled="loading"
          />
        </div>

        <div class="input-group">
          <label>Пароль</label>
          <input
            v-model="password"
            type="password"
            required
            placeholder="******"
            :disabled="loading"
          />
        </div>

        <button type="submit" class="login-button" :disabled="loading">
          {{ loading ? 'Вход...' : 'Войти' }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import '../assets/supra-style.css'
import { fetchCurrentUser } from '../services/auth'

const router = useRouter()
const route = useRoute()

const username = ref('')
const password = ref('')
const errorMessage = ref('')
const loading = ref(false)

// true = проверка без backend
const USE_MOCK_AUTH = true

// Мок-пользователи для проверки логики ролей без backend

if (localStorage.getItem('access')) {
  router.replace('/cabinet')
}

const mockUsers = [
  {
    username: 'manager',
    password: '123456',
    user: {
      username: 'manager',
      email: 'manager@mail.ru',
      first_name: 'Иван',
      last_name: 'Петров',
      phone: '+79990001122',
      role: 'MANAGER',
      venue: 'Ресторан №1',
      schedule_pattern: '5/2',
      shift_duration: '12 часов'
    }
  },
  {
    username: 'waiter',
    password: '123456',
    user: {
      username: 'waiter',
      email: 'waiter@mail.ru',
      first_name: 'Алексей',
      last_name: 'Сидоров',
      phone: '+79990003344',
      role: 'WAITER',
      venue: 'Ресторан №1',
      schedule_pattern: '2/2',
      shift_duration: '12 часов'
    }
  }
]

const handleMockLogin = async () => {
  const foundUser = mockUsers.find(
    item =>
      item.username === username.value.trim() &&
      item.password === password.value.trim()
  )

  if (!foundUser) {
    throw new Error('Ошибка: Неверный логин или пароль')
  }

  localStorage.setItem('access', 'mock_access_token')
  localStorage.setItem('refresh', 'mock_refresh_token')
  localStorage.setItem('isAuthenticated', 'true')
  localStorage.setItem('user', JSON.stringify(foundUser.user))

  await router.push(route.query.redirect || '/cabinet')
}

const handleBackendLogin = async () => {
  const response = await fetch('http://localhost:8000/api/v1/auth/login/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      username: username.value,
      password: password.value,
    }),
  })

  const data = await response.json()

  if (!response.ok) {
    throw new Error(
      data.detail ||
      data.message ||
      'Ошибка: Неверный логин или пароль'
    )
  }

  if (!data.access || !data.refresh) {
    throw new Error('Бэкенд не вернул access и refresh токены')
  }

  localStorage.setItem('access', data.access)
  localStorage.setItem('refresh', data.refresh)
  localStorage.setItem('isAuthenticated', 'true')

  if (data.user) {
    localStorage.setItem('user', JSON.stringify(data.user))
  } else {
    const freshUser = await fetchCurrentUser()
    localStorage.setItem('user', JSON.stringify(freshUser))
  }

  await router.push(route.query.redirect || '/cabinet')
}

const handleLogin = async () => {
  errorMessage.value = ''
  loading.value = true

  try {
    if (USE_MOCK_AUTH) {
      await handleMockLogin()
    } else {
      await handleBackendLogin()
    }
  } catch (error) {
    errorMessage.value = error.message || 'Ошибка авторизации'
  } finally {
    loading.value = false
  }
}
</script>