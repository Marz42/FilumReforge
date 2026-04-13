import 'vue-router'

import type { UserRole } from '@/types/api'

declare module 'vue-router' {
  interface RouteMeta {
    requiresAuth?: boolean
    guestOnly?: boolean
    roles?: UserRole[]
  }
}
