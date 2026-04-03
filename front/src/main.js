import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { ensureAuth } from './services/auth.js'

const bootstrap = async () => {
  await ensureAuth()
  createApp(App).use(router).mount('#app')

  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register(`${import.meta.env.BASE_URL}sw.js`).catch(() => {})
    })
  }
}

bootstrap() 
