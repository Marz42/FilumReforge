<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch, type Component } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Briefcase,
  Collection,
  DocumentCopy,
  House,
  Memo,
  OfficeBuilding,
  Setting,
  User,
} from '@element-plus/icons-vue'

import AppHeader from '@/components/shell/AppHeader.vue'
import GlobalMemoFloat from '@/components/shell/GlobalMemoFloat.vue'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'

const appStore = useAppStore()
const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()
const isMobileViewport = ref(false)
const isMobileNavOpen = ref(false)

type NavigationItem = {
  label: string
  routeName: string
  icon: Component
}

const generalNavigationItems = computed<NavigationItem[]>(() => [
  { label: '总览', routeName: 'overview', icon: House },
  { label: '任务中心', routeName: 'task-center', icon: Briefcase },
  { label: '知识库', routeName: 'knowledge-base', icon: Collection },
  { label: '汇报中心', routeName: 'reports', icon: Memo },
  { label: '设置', routeName: 'settings-profile', icon: Setting },
])

const specialNavigationItems = computed(() => {
  const items: NavigationItem[] = []

  if (authStore.isManagementRole) {
    items.push({ label: '人员管理', routeName: 'people', icon: User })
    items.push({ label: '任务模板', routeName: 'task-templates', icon: DocumentCopy })
  }

  if (authStore.user?.role === 'admin') {
    items.push({ label: '部门管理', routeName: 'departments', icon: OfficeBuilding })
  }

  return items
})

const activeMenu = computed(() => {
  if (typeof route.name !== 'string') {
    return 'overview'
  }

  if (route.name.startsWith('settings-')) {
    return 'settings-profile'
  }

  const legacyRouteMap: Record<string, string> = {
    dashboard: 'overview',
    tasks: 'task-center',
    approvals: 'reports',
    users: 'people',
    profiles: 'people',
  }

  return legacyRouteMap[route.name] ?? route.name
})

function handleSelect(routeName: string): void {
  isMobileNavOpen.value = false
  void router.push({ name: routeName })
}

function syncViewport(): void {
  const nextIsMobile = window.innerWidth <= 860
  isMobileViewport.value = nextIsMobile
  if (!nextIsMobile) {
    isMobileNavOpen.value = false
  }
}

function openMobileNav(): void {
  isMobileNavOpen.value = true
}

function closeMobileNav(): void {
  isMobileNavOpen.value = false
}

async function handleLogout(): Promise<void> {
  await authStore.logout()
  void router.push({ name: 'login' })
}

watch(
  () => route.fullPath,
  () => {
    isMobileNavOpen.value = false
  },
)

onMounted(() => {
  syncViewport()
  window.addEventListener('resize', syncViewport)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', syncViewport)
})
</script>

<template>
  <el-container class="app-shell">
    <el-aside v-if="!isMobileViewport" width="240px" class="app-shell__aside">
      <div class="app-shell__brand">
        <h1>{{ appStore.projectName }}</h1>
        <p>{{ appStore.currentPhase }}</p>
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
            class="app-shell__menu-item"
          >
            <el-icon class="app-shell__menu-icon"><component :is="item.icon" /></el-icon>
            <span>{{ item.label }}</span>
          </el-menu-item>
        </el-menu-item-group>

        <el-menu-item-group v-if="specialNavigationItems.length > 0" title="特殊模块">
          <el-menu-item
            v-for="item in specialNavigationItems"
            :key="item.routeName"
            :index="item.routeName"
            class="app-shell__menu-item"
          >
            <el-icon class="app-shell__menu-icon"><component :is="item.icon" /></el-icon>
            <span>{{ item.label }}</span>
          </el-menu-item>
        </el-menu-item-group>
      </el-menu>
    </el-aside>

    <el-container direction="vertical" class="app-shell__content">
      <AppHeader
        :is-mobile-viewport="isMobileViewport"
        @open-mobile-nav="openMobileNav"
        @logout="handleLogout"
      />

      <el-main class="app-shell__main">
        <RouterView v-slot="{ Component }">
          <Transition name="page-fade" mode="out-in">
            <component :is="Component" class="app-shell__view" />
          </Transition>
        </RouterView>
      </el-main>
    </el-container>

    <GlobalMemoFloat v-if="authStore.isAuthenticated" />
  </el-container>

  <el-drawer
    v-model="isMobileNavOpen"
    :with-header="false"
    size="240px"
    direction="ltr"
    append-to-body
    destroy-on-close
    class="app-shell__drawer"
    @close="closeMobileNav"
  >
    <div class="app-shell__brand app-shell__brand--drawer">
      <h1>{{ appStore.projectName }}</h1>
      <p>{{ appStore.currentPhase }}</p>
    </div>

    <el-menu
      :default-active="activeMenu"
      class="app-shell__menu app-shell__menu--drawer"
      @select="handleSelect"
    >
      <el-menu-item-group title="通用模块">
        <el-menu-item
          v-for="item in generalNavigationItems"
          :key="item.routeName"
          :index="item.routeName"
          class="app-shell__menu-item"
        >
          <el-icon class="app-shell__menu-icon"><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </el-menu-item>
      </el-menu-item-group>

      <el-menu-item-group v-if="specialNavigationItems.length > 0" title="特殊模块">
        <el-menu-item
          v-for="item in specialNavigationItems"
          :key="item.routeName"
          :index="item.routeName"
          class="app-shell__menu-item"
        >
          <el-icon class="app-shell__menu-icon"><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </el-menu-item>
      </el-menu-item-group>
    </el-menu>
  </el-drawer>
</template>

<style scoped>
.app-shell {
  min-height: 100vh;
  background: var(--filum-bg);
}

.app-shell__content {
  flex: 1;
  min-width: 0;
}

.app-shell__aside {
  background: linear-gradient(180deg, #1e2235 0%, #252a40 100%);
  border-right: none;
  box-shadow: 2px 0 12px rgba(0, 0, 0, 0.08);
}

.app-shell__brand {
  padding: 28px 20px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.app-shell__brand h1 {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: #fff;
  letter-spacing: 0.01em;
}

.app-shell__brand p {
  margin: 6px 0 0;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.45);
}

.app-shell__menu {
  border-right: none;
  background: transparent;
  padding: 12px;
  --el-menu-bg-color: transparent;
  --el-menu-text-color: rgba(255, 255, 255, 0.6);
  --el-menu-hover-bg-color: rgba(255, 255, 255, 0.08);
  --el-menu-active-color: #fff;
  --el-menu-item-height: 42px;
}

.app-shell__menu :deep(.el-menu-item-group__title) {
  padding: 12px 12px 8px;
  color: rgba(255, 255, 255, 0.35);
  font-size: 11px;
  line-height: 1;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.app-shell__menu :deep(.el-menu-item) {
  margin-bottom: 6px;
  border-radius: 10px;
  font-weight: 500;
}

.app-shell__menu :deep(.el-menu-item.is-active) {
  background: rgba(255, 255, 255, 0.14);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.08);
}

.app-shell__menu-item {
  display: flex;
  align-items: center;
  gap: 10px;
}

.app-shell__menu-icon {
  font-size: 16px;
}

.app-shell__main {
  flex: 1;
  min-width: 0;
  padding: 24px 28px;
}

.app-shell__drawer :deep(.el-drawer) {
  background: linear-gradient(180deg, #1e2235 0%, #252a40 100%);
}

.app-shell__drawer :deep(.el-drawer__body) {
  padding: 0;
}

.app-shell__brand--drawer {
  padding-right: 24px;
}

.app-shell__menu--drawer {
  min-height: calc(100vh - 92px);
}

.app-shell__view {
  min-height: 100%;
}

.page-fade-enter-active,
.page-fade-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.page-fade-enter-from {
  opacity: 0;
  transform: translateY(6px);
}

.page-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

@media (max-width: 1080px) {
  .app-shell__main {
    padding: 20px;
  }
}
</style>
