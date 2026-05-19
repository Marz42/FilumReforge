<script setup lang="ts">
import { computed, onMounted, provide, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Bell, Operation } from '@element-plus/icons-vue'

import CommandBar from '@/components/CommandBar.vue'
import DeadlineCountdown from '@/components/overview/DeadlineCountdown.vue'
import NotificationDrawer from '@/components/shell/NotificationDrawer.vue'
import { useMessagesInbox } from '@/composables/useMessagesInbox'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'
import type { UserRole } from '@/types/api'

defineProps<{
  isMobileViewport: boolean
}>()

const emit = defineEmits<{
  openMobileNav: []
  logout: []
}>()

const appStore = useAppStore()
const authStore = useAuthStore()
const route = useRoute()
const inbox = useMessagesInbox()

provide('messagesInbox', inbox)

const { unreadCount, refreshUnreadCount, startPolling } = inbox

const notificationDrawerOpen = computed({
  get: () => appStore.notificationDrawerOpen,
  set: (value: boolean) => {
    if (value) {
      appStore.notificationDrawerOpen = true
      return
    }
    appStore.closeNotificationDrawer()
  },
})

const roleLabelMap: Record<UserRole, string> = {
  admin: '管理员',
  hr: 'HR',
  employee: '员工',
}

function currentRoleLabel(): string {
  if (!authStore.user) {
    return '访客'
  }
  return roleLabelMap[authStore.user.role]
}

watch(
  () => route.fullPath,
  () => {
    if (route.name === 'messages' && route.query.drawer === '1') {
      appStore.openNotificationDrawer()
    }
  },
  { immediate: true },
)

onMounted(() => {
  void refreshUnreadCount()
  startPolling()
})
</script>

<template>
  <el-header class="app-header">
    <div class="app-header__copy">
      <el-button
        v-if="isMobileViewport"
        circle
        class="app-header__menu-button"
        data-testid="mobile-nav-trigger"
        @click="emit('openMobileNav')"
      >
        <el-icon><Operation /></el-icon>
      </el-button>
      <h2>{{ appStore.headerTitle }}</h2>
      <p>{{ appStore.deliveryStatus }}</p>
    </div>

    <div class="app-header__actions">
      <DeadlineCountdown />
      <CommandBar />
      <el-badge :value="unreadCount" :hidden="unreadCount === 0" :max="99">
        <el-button circle data-testid="header-notification-bell" @click="appStore.openNotificationDrawer()">
          <el-icon><Bell /></el-icon>
        </el-button>
      </el-badge>
      <NotificationDrawer
        v-model="notificationDrawerOpen"
        :initial-message-id="appStore.notificationDrawerMessageId"
      />
      <el-tag type="primary" effect="plain" round>{{ currentRoleLabel() }}</el-tag>
      <span class="app-header__email">{{ authStore.user?.email ?? '未登录' }}</span>
      <el-button link type="primary" class="app-header__logout" @click="emit('logout')">退出登录</el-button>
    </div>
  </el-header>
</template>

<style scoped>
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 0 28px;
  height: 64px !important;
  background: var(--filum-surface);
  border-bottom: 1px solid var(--filum-border);
  box-shadow: var(--filum-shadow-shell);
}

.app-header__copy {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.app-header__menu-button {
  display: none;
  align-self: flex-start;
  border-color: rgba(91, 110, 245, 0.16);
  background: var(--filum-surface-muted);
  color: var(--el-color-primary);
}

.app-header__copy h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--filum-text);
}

.app-header__copy p {
  margin: 3px 0 0;
  font-size: 12px;
  color: var(--filum-text-muted);
}

.app-header__actions {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
  color: var(--filum-text);
}

.app-header__email {
  max-width: 240px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
  color: var(--filum-text-secondary);
}

.app-header__logout {
  font-weight: 600;
}

@media (max-width: 1080px) {
  .app-header {
    padding: 0 20px;
  }

  .app-header__actions {
    gap: 10px;
  }

  .app-header__email {
    max-width: 180px;
  }
}

@media (max-width: 860px) {
  .app-header__menu-button {
    display: inline-flex;
  }

  .app-header {
    align-items: flex-start;
    flex-direction: column;
    justify-content: center;
    height: auto !important;
    padding: 18px 20px;
  }

  .app-header__actions {
    flex-wrap: wrap;
  }

  .app-header__email {
    max-width: 100%;
  }
}
</style>
