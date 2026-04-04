<template>
  <div class="auth-page">
    <div class="supra-login-card">
      <img :src="logoSupra" alt="Supra" class="auth-brand-logo" />
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
import logoSupra from '../assets/Logo_supra.png'
import { loginUser } from '../services/auth'
import {
  getSystemNotificationPermission,
  isPushNotificationsEnabled,
  requestSystemNotificationPermission,
  setPushNotificationsEnabled,
  supportsSystemNotifications
} from '../services/notifications'

const router = useRouter()
const route = useRoute()

const username = ref('')
const password = ref('')
const errorMessage = ref('')
const loading = ref(false)

const USE_MOCK_AUTH = import.meta.env.VITE_USE_MOCK_AUTH === 'true'
const PUSH_PROMPT_TEXT = '\u0412\u043a\u043b\u044e\u0447\u0438\u0442\u044c push-\u0443\u0432\u0435\u0434\u043e\u043c\u043b\u0435\u043d\u0438\u044f \u0432 \u0431\u0440\u0430\u0443\u0437\u0435\u0440\u0435?'

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
}

const handleBackendLogin = async () => {
  await loginUser({
    username: username.value.trim(),
    password: password.value
  })
}

const promptPushNotificationsAfterLogin = async () => {
  if (!supportsSystemNotifications() || isPushNotificationsEnabled()) {
    return
  }

  const permission = getSystemNotificationPermission()

  if (permission === 'denied') {
    setPushNotificationsEnabled(false)
    return
  }

  const shouldEnable = window.confirm(PUSH_PROMPT_TEXT)

  if (!shouldEnable) {
    setPushNotificationsEnabled(false)
    return
  }

  const nextPermission = await requestSystemNotificationPermission()
  setPushNotificationsEnabled(nextPermission === 'granted')
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

    await promptPushNotificationsAfterLogin()
    await router.push(route.query.redirect || '/cabinet')
  } catch (error) {
    errorMessage.value = error.message || 'Ошибка авторизации'
  } finally {
    loading.value = false
  }
}
</script>
