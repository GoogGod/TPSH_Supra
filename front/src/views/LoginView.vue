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
        <input v-model="username" type="text" required placeholder="username" />
      </div>

      <div class="input-group">
        <label>Пароль</label>
        <input v-model="password" type="password" required placeholder="******" />
      </div>

      <button type="submit" class="login-button">Войти</button>
    </form>
  </div>
</div>


</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
// ИМПОРТИРУЕМ НАШ НОВЫЙ СТИЛЬ SUPRA
import '../assets/supra-style.css' 

const router = useRouter()
const username = ref('')
const password = ref('')
const errorMessage = ref('')

const handleLogin = () => {
  if (username.value === 'admin' && password.value === '123') {
    localStorage.setItem('userRole', 'admin')
    localStorage.setItem('isAuthenticated', 'true')
    router.push('/schedule')
  } else {
    errorMessage.value = 'Ошибка: Неверный логин или пароль'
  }
}
</script>