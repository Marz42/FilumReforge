import { createRouter, createWebHistory } from 'vue-router'

import AppShell from '@/components/AppShell.vue'
import { useAuthStore } from '@/stores/auth'
import LoginView from '@/views/LoginView.vue'
import type { UserRole } from '@/types/api'

const SettingsLayout = () => import('@/components/settings/SettingsLayout.vue')
const ProfileSection = () => import('@/components/settings/ProfileSection.vue')
const SecuritySection = () => import('@/components/settings/SecuritySection.vue')
const NotificationsSection = () => import('@/components/settings/NotificationsSection.vue')
const HomeView = () => import('@/views/HomeView.vue')
const KnowledgeBaseView = () => import('@/views/KnowledgeBaseView.vue')
const DepartmentsView = () => import('@/views/DepartmentsView.vue')
const MessagesView = () => import('@/views/MessagesView.vue')
const PeopleManagementView = () => import('@/views/PeopleManagementView.vue')
const ReportsView = () => import('@/views/ReportsView.vue')
const TaskCenterView = () => import('@/views/TaskCenterView.vue')
const TaskTemplatesView = () => import('@/views/TaskTemplatesView.vue')
const GraphTemplateDesignerView = () => import('@/views/GraphTemplateDesignerView.vue')

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
          path: 'task-center/stats',
          redirect: {
            name: 'task-center',
            query: {
              filter: 'stats',
            },
          },
        },
        {
          path: 'tasks',
          redirect: {
            name: 'task-center',
            query: {
              filter: 'tracking',
            },
          },
        },
        {
          path: 'task-templates',
          name: 'task-templates',
          component: TaskTemplatesView,
        },
        {
          path: 'task-templates/:id/edit',
          name: 'task-template-designer',
          component: GraphTemplateDesignerView,
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
