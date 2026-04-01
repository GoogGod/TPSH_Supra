import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { ensureAuth } from './services/auth.js'

const bootstrap = async () => {
  await ensureAuth()
  createApp(App).use(router).mount('#app')
}

bootstrap() 