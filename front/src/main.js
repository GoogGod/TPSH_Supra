import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import './assets/supra-style.css' // Добавь это здесь!

const app = createApp(App)
app.use(router)
app.mount('#app')