import { createRouter, createWebHistory } from 'vue-router'
import LoginView from '../views/LoginView.vue'
import CabinetView from '../views/CabinetView.vue'
import ForeCastView from '../views/ForeCastView.vue'
import NotFoundView from '../views/NotFoundView.vue'
import { isAuthenticated } from '../services/auth'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: LoginView,
    meta: {
      guestOnly: true
    }
  },
  {
    path: '/cabinet',
    name: 'cabinet',
    component: CabinetView,
    meta: {
      requiresAuth: true
    }
  },
  {
    path: '/schedule',
    name: 'schedule',
    component: ForeCastView,
    meta: {
      requiresAuth: true
    }
  },
  {
    path: '/',
    redirect: '/login'
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: NotFoundView
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to) => {
  const loggedIn = isAuthenticated()

  if (to.meta.requiresAuth && !loggedIn) {
    return {
      path: '/login',
      query: { redirect: to.fullPath }
    }
  }

  if (to.meta.guestOnly && loggedIn) {
    return '/cabinet'
  }

  return true
})

export default router
