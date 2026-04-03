import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { ensureAuth } from './services/auth.js'

const bootstrap = async () => {
  await ensureAuth()
  createApp(App).use(router).mount('#app')

  if ('serviceWorker' in navigator) {
    if (import.meta.env.PROD) {
      window.addEventListener('load', () => {
        navigator.serviceWorker.register(`${import.meta.env.BASE_URL}sw.js`).catch(() => {})
      })
    } else {
      // В dev не держим SW, иначе он кэширует старые роуты/бандлы и мешает отладке.
      navigator.serviceWorker.getRegistrations().then((registrations) => {
        registrations.forEach((registration) => {
          registration.unregister().catch(() => {})
        })
      })
      if ('caches' in window) {
        caches.keys().then((keys) => {
          keys.forEach((key) => caches.delete(key).catch(() => {}))
        })
      }
    }
  }
}

bootstrap() 
