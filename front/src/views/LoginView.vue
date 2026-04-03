<template>
  <div class="auth-page">
    <img src="/src/assets/S_height.png" alt="Supra" class="top-right-image" />

    <div class="supra-login-card">
      <h1>Авторизация</h1>

      <div class="auth-form-container">
        <form class="auth-form-box" @submit.prevent="handleLogin">
          <div v-if="errorMessage" class="error-message">
            {{ errorMessage }}
          </div>

          <div class="input-group">
            <label for="username">Имя пользователя</label>
            <input
              id="username"
              v-model="username"
              type="text"
              required
              placeholder="username"
              autocomplete="username"
              :disabled="loading"
            />
          </div>

          <div class="input-group">
            <label for="password">Пароль</label>
            <input
              id="password"
              v-model="password"
              type="password"
              required
              placeholder="******"
              autocomplete="current-password"
              :disabled="loading"
            />
          </div>

          <button type="submit" class="login-button" :disabled="loading">
            {{ loading ? 'Вход...' : 'Войти' }}
          </button>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import '../assets/supra-style.css'
import { loginUser } from '../services/auth'

const router = useRouter()
const route = useRoute()

const username = ref('')
const password = ref('')
const errorMessage = ref('')
const loading = ref(false)

const USE_MOCK_AUTH = import.meta.env.VITE_USE_MOCK_AUTH === 'true'

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
      role: 'manager',
      venue: 1
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
      role: 'employee_noob',
      venue: 1
    }
  },
  {
    username: 'admin',
    password: '123456',
    user: {
      username: 'admin',
      email: 'admin@mail.ru',
      first_name: 'Алексей',
      last_name: 'Сидоров',
      phone: '+79990003344',
      role: 'ADMIN',
      venue: 1
    }
  }
]

const handleMockLogin = async () => {
  const foundUser = mockUsers.find(
    (item) =>
      item.username === username.value.trim() &&
      item.password === password.value.trim()
  )

  if (!foundUser) {
    throw new Error('Ошибка: неверный логин или пароль')
  }

  localStorage.setItem('access', 'mock_access_token')
  localStorage.setItem('refresh', 'mock_refresh_token')
  localStorage.setItem('isAuthenticated', 'true')
  localStorage.setItem('user', JSON.stringify(foundUser.user))

  await router.push(route.query.redirect || '/cabinet')
}

const handleBackendLogin = async () => {
  await loginUser({
    username: username.value.trim(),
    password: password.value
  })

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
