<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import CommandBar from '@/components/CommandBar.vue'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'
import type { UserRole } from '@/types/api'

const appStore = useAppStore()
const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()

const roleLabelMap: Record<UserRole, string> = {
  admin: '管理员',
  hr: 'HR',
  employee: '员工',
}

const generalNavigationItems = computed(() => [
  { label: '总览', routeName: 'overview' },
  { label: '任务中心', routeName: 'task-center' },
  { label: '知识库', routeName: 'knowledge-base' },
  { label: '汇报中心', routeName: 'reports' },
  { label: '消息中心', routeName: 'messages' },
])

const specialNavigationItems = computed(() => {
  const items: Array<{ label: string; routeName: string }> = []

  if (authStore.isManagementRole) {
    items.push({ label: '人员管理', routeName: 'people' })
  }

  if (authStore.user?.role === 'admin') {
    items.push({ label: '部门管理', routeName: 'departments' })
  }

  return items
})

const activeMenu = computed(() => {
  if (typeof route.name !== 'string') {
    return 'overview'
  }

  const legacyRouteMap: Record<string, string> = {
    dashboard: 'overview',
    tasks: 'task-center',
    'task-templates': 'task-center',
    approvals: 'reports',
    users: 'people',
    profiles: 'people',
  }

  return legacyRouteMap[route.name] ?? route.name
})
const currentRoleLabel = computed(() => {
  if (!authStore.user) {
    return '访客'
  }

  return roleLabelMap[authStore.user.role]
})

function handleSelect(routeName: string): void {
  void router.push({ name: routeName })
}

function handleLogout(): void {
  authStore.logout()
  void router.push({ name: 'login' })
}
</script>

<template>
  <el-container class="app-shell">
    <el-aside width="240px" class="app-shell__aside">
      <div class="app-shell__brand">
        <h1>{{ appStore.projectName }}</h1>
        <p>{{ appStore.currentPhase }} · 当前重构收口</p>
      </div>

      <el-menu
        :default-active="activeMenu"
        class="app-shell__menu"
        @select="handleSelect"
      >
        <el-menu-item-group title="通用模块">
          <el-menu-item
            v-for="item in generalNavigationItems"
            :key="item.routeName"
            :index="item.routeName"
          >
            {{ item.label }}
          </el-menu-item>
        </el-menu-item-group>

        <el-menu-item-group v-if="specialNavigationItems.length > 0" title="特殊模块">
          <el-menu-item
            v-for="item in specialNavigationItems"
            :key="item.routeName"
            :index="item.routeName"
          >
            {{ item.label }}
          </el-menu-item>
        </el-menu-item-group>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="app-shell__header">
        <div>
          <h2>{{ appStore.headerTitle }}</h2>
          <p>{{ appStore.deliveryStatus }}</p>
        </div>

        <div class="app-shell__user">
          <CommandBar />
          <el-tag type="primary" effect="plain">{{ currentRoleLabel }}</el-tag>
          <span>{{ authStore.user?.email ?? '未登录' }}</span>
          <el-button link type="primary" @click="handleLogout">退出登录</el-button>
        </div>
      </el-header>

      <el-main class="app-shell__main">
        <RouterView />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.app-shell {
  min-height: 100vh;
  background: #f5f7fa;
}

.app-shell__aside {
  border-right: 1px solid #e4e7ed;
  background: #fff;
}

.app-shell__brand {
  padding: 24px;
  border-bottom: 1px solid #ebeef5;
}

.app-shell__brand h1 {
  margin: 0;
  font-size: 22px;
}

.app-shell__brand p {
  margin: 8px 0 0;
  color: #606266;
}

.app-shell__menu {
  border-right: none;
}

.app-shell__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  background: #fff;
  border-bottom: 1px solid #ebeef5;
}

.app-shell__header h2 {
  margin: 0;
  font-size: 24px;
}

.app-shell__header p {
  margin: 8px 0 0;
  color: #606266;
}

.app-shell__user {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #303133;
}

.app-shell__main {
  padding: 24px;
}
</style>
