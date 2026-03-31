import { createRouter, createWebHistory } from 'vue-router'
import LoginView from '../views/LoginView.vue'
import CabinetView from '../views/CabinetView.vue'
import ForeCastView from '../views/ForeCastView.vue'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: LoginView
  },
  {
    path: '/cabinet',
    name: 'cabinet',
    component: CabinetView
  },
  {
    path: '/schedule',
    name: 'schedule',
    component: ForeCastView
  },
  {
    path: '/',
    redirect: '/login'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router