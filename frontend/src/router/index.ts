import { createRouter, createWebHistory } from 'vue-router'

import AppShell from '@/components/AppShell.vue'
import SettingsLayout from '@/components/settings/SettingsLayout.vue'
import ProfileSection from '@/components/settings/ProfileSection.vue'
import SecuritySection from '@/components/settings/SecuritySection.vue'
import NotificationsSection from '@/components/settings/NotificationsSection.vue'
import { useAuthStore } from '@/stores/auth'
import HomeView from '@/views/HomeView.vue'
import KnowledgeBaseView from '@/views/KnowledgeBaseView.vue'
import LoginView from '@/views/LoginView.vue'
import type { UserRole } from '@/types/api'
import DepartmentsView from '@/views/DepartmentsView.vue'
import MessagesView from '@/views/MessagesView.vue'
import PeopleManagementView from '@/views/PeopleManagementView.vue'
import ReportsView from '@/views/ReportsView.vue'
import TaskCenterView from '@/views/TaskCenterView.vue'

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
            name: 'overview',
          },
        },
        {
          path: 'overview',
          name: 'overview',
          component: HomeView,
        },
        {
          path: 'dashboard',
          redirect: {
            name: 'overview',
          },
        },
        {
          path: 'people',
          name: 'people',
          component: PeopleManagementView,
          meta: {
            roles: ['admin', 'hr'] satisfies UserRole[],
          },
        },
        {
          path: 'users',
          redirect: {
            name: 'people',
            query: {
              tab: 'users',
            },
          },
          meta: {
            roles: ['admin', 'hr'] satisfies UserRole[],
          },
        },
        {
          path: 'profiles',
          redirect: {
            name: 'people',
            query: {
              tab: 'profiles',
            },
          },
          meta: {
            roles: ['admin', 'hr'] satisfies UserRole[],
          },
        },
        {
          path: 'departments',
          name: 'departments',
          component: DepartmentsView,
          meta: {
            roles: ['admin'] satisfies UserRole[],
          },
        },
        {
          path: 'knowledge-base',
          name: 'knowledge-base',
          component: KnowledgeBaseView,
        },
        {
          path: 'task-center',
          name: 'task-center',
          component: TaskCenterView,
        },
        {
          path: 'tasks',
          redirect: {
            name: 'task-center',
            query: {
              tab: 'tracking',
            },
          },
        },
        {
          path: 'task-templates',
          redirect: {
            name: 'task-center',
            query: {
              tab: 'templates',
            },
          },
        },
        {
          path: 'reports',
          name: 'reports',
          component: ReportsView,
        },
        {
          path: 'approvals',
          redirect: {
            name: 'reports',
          },
        },
        {
          path: 'messages',
          name: 'messages',
          component: MessagesView,
        },
        {
          path: 'settings',
          component: SettingsLayout,
          children: [
            {
              path: '',
              redirect: {
                name: 'settings-profile',
              },
            },
            {
              path: 'profile',
              name: 'settings-profile',
              component: ProfileSection,
            },
            {
              path: 'security',
              name: 'settings-security',
              component: SecuritySection,
            },
            {
              path: 'notifications',
              name: 'settings-notifications',
              component: NotificationsSection,
            },
          ],
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
      name: 'overview',
    }
  }

  if (to.meta.roles && authStore.user && !to.meta.roles.includes(authStore.user.role)) {
    return {
      name: 'overview',
    }
  }

  return true
})

export default router
