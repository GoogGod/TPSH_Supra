import { createRouter, createWebHistory } from 'vue-router'
import LoginView from '../views/LoginView.vue'
import CabinetView from '../views/CabinetView.vue'

const routes = [
  {
    path: '/',
    name: 'login',
    component: LoginView
  },
  {
    path: '/cabinet',
    name: 'cabinet',
    component: CabinetView
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router