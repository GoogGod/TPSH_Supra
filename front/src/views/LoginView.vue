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
import { useRouter } from 'vue-router'
import '../assets/supra-style.css'

const router = useRouter()

const username = ref('')
const password = ref('')
const errorMessage = ref('')
const loading = ref(false)

const handleLogin = async () => {
  errorMessage.value = ''
  loading.value = true

  try {
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

    router.push('/schedule')
  } catch (error) {
    errorMessage.value = error.message || 'Ошибка авторизации'
  } finally {
    loading.value = false
  }
}
</script>