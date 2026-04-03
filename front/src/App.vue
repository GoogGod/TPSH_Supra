<template>
  <router-view />
  <a
    v-if="showAdminShortcut"
    class="admin-shortcut"
    href="/admin/"
    target="_blank"
    rel="noopener noreferrer"
    title="Открыть Django Admin"
  >
    Django Admin
  </a>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { isAuthenticated, getUserRole } from './services/auth'

const router = useRouter()
const loggedIn = ref(isAuthenticated())
const role = ref(getUserRole())

const syncAuthState = () => {
  loggedIn.value = isAuthenticated()
  role.value = getUserRole()
}

const showAdminShortcut = computed(() => {
  return loggedIn.value && role.value === 'admin'
})

let removeAfterEachHook

onMounted(() => {
  removeAfterEachHook = router.afterEach(() => {
    syncAuthState()
  })

  window.addEventListener('storage', syncAuthState)
})

onUnmounted(() => {
  if (removeAfterEachHook) {
    removeAfterEachHook()
  }
  window.removeEventListener('storage', syncAuthState)
})
</script>

<style scoped>
.admin-shortcut {
  position: fixed;
  right: 16px;
  bottom: 16px;
  z-index: 2000;
  padding: 10px 14px;
  border-radius: 999px;
  border: 1px solid rgba(16, 25, 93, 0.2);
  background: #10195d;
  color: #fff;
  text-decoration: none;
  font-size: 13px;
  font-weight: 600;
  box-shadow: 0 8px 24px rgba(16, 25, 93, 0.25);
}

.admin-shortcut:hover {
  background: #1a2787;
}
</style>
