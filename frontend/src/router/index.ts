import { createRouter, createWebHistory } from 'vue-router'

import AppShell from '@/components/AppShell.vue'
import { useAuthStore } from '@/stores/auth'
import HomeView from '@/views/HomeView.vue'
import LoginView from '@/views/LoginView.vue'
import type { UserRole } from '@/types/api'
import DepartmentsView from '@/views/DepartmentsView.vue'
import ProfilesView from '@/views/ProfilesView.vue'
import TasksView from '@/views/TasksView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: LoginView,
      meta: {
        guestOnly: true,
      },
    },
    {
      path: '/',
      component: AppShell,
      meta: {
        requiresAuth: true,
      },
      children: [
        {
          path: '',
          redirect: {
            name: 'dashboard',
          },
        },
        {
          path: 'dashboard',
          name: 'dashboard',
          component: HomeView,
        },
        {
          path: 'departments',
          name: 'departments',
          component: DepartmentsView,
          meta: {
            roles: ['admin', 'hr'] satisfies UserRole[],
          },
        },
        {
          path: 'profiles',
          name: 'profiles',
          component: ProfilesView,
          meta: {
            roles: ['admin', 'hr'] satisfies UserRole[],
          },
        },
        {
          path: 'tasks',
          name: 'tasks',
          component: TasksView,
        },
      ],
    },
  ],
})

router.beforeEach(async (to) => {
  const authStore = useAuthStore()

  if (!authStore.initialized) {
    await authStore.restoreSession()
  }

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    return {
      name: 'login',
      query: {
        redirect: to.fullPath,
      },
    }
  }

  if (to.meta.guestOnly && authStore.isAuthenticated) {
    return {
      name: 'dashboard',
    }
  }

  if (to.meta.roles && authStore.user && !to.meta.roles.includes(authStore.user.role)) {
    return {
      name: 'dashboard',
    }
  }

  return true
})

export default router
