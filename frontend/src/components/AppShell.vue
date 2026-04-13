<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

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

const navigationItems = computed(() => {
  const items = [
    { label: '仪表盘', routeName: 'dashboard' },
    { label: '任务中心', routeName: 'tasks' },
  ]

  if (authStore.isManagementRole) {
    items.splice(1, 0, { label: '部门管理', routeName: 'departments' })
    items.splice(2, 0, { label: '档案管理', routeName: 'profiles' })
  }

  return items
})

const activeMenu = computed(() => (typeof route.name === 'string' ? route.name : 'dashboard'))
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
        <p>{{ appStore.currentPhase }} · Foundation</p>
      </div>

      <el-menu
        :default-active="activeMenu"
        class="app-shell__menu"
        @select="handleSelect"
      >
        <el-menu-item
          v-for="item in navigationItems"
          :key="item.routeName"
          :index="item.routeName"
        >
          {{ item.label }}
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="app-shell__header">
        <div>
          <h2>{{ appStore.headerTitle }}</h2>
          <p>{{ appStore.deliveryStatus }}</p>
        </div>

        <div class="app-shell__user">
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
