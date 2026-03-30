import { createRouter, createWebHistory } from 'vue-router'
import LoginView from '../views/LoginView.vue'
import CabinetView from '../views/CabinetView.vue'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: LoginView,
    meta: { guestOnly: true }
  },
  {
    path: '/cabinet',
    name: 'cabinet',
    component: CabinetView,
    meta: { requiresAuth: true }
  },
  {
    path: '/',
    redirect: '/login'
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/login'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const isAuthenticated = localStorage.getItem('isAuthenticated') === 'true'
  const accessToken = localStorage.getItem('access')
  const user = localStorage.getItem('user')

  const isAuth = isAuthenticated && !!accessToken && !!user

  if (to.meta.requiresAuth && !isAuth) {
    return next('/login')
  }

  if (to.meta.guestOnly && isAuth) {
    return next('/cabinet')
  }

  next()
})

export default router