<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

type SettingsSection = 'profile' | 'security' | 'notifications'

const route = useRoute()
const router = useRouter()

const activeSection = computed<SettingsSection>(() => {
  if (route.name === 'settings-security') {
    return 'security'
  }
  if (route.name === 'settings-notifications') {
    return 'notifications'
  }
  return 'profile'
})

function navigate(section: SettingsSection): void {
  router.push({ name: `settings-${section}` })
}
</script>

<template>
  <div class="settings-layout filum-page" data-testid="settings-layout">
    <el-row :gutter="20">
      <el-col :xs="24" :md="6" :xl="5">
        <el-card shadow="never" class="settings-layout__nav filum-panel-card">
          <el-menu :default-active="activeSection" class="settings-layout__menu">
            <el-menu-item index="profile" data-testid="settings-nav-profile" @click="navigate('profile')">
              个人资料
            </el-menu-item>
            <el-menu-item index="security" data-testid="settings-nav-security" @click="navigate('security')">
              安全与密码
            </el-menu-item>
            <el-menu-item
              index="notifications"
              data-testid="settings-nav-notifications"
              @click="navigate('notifications')"
            >
              通知偏好
            </el-menu-item>
          </el-menu>
        </el-card>
      </el-col>

      <el-col :xs="24" :md="18" :xl="19">
        <router-view />
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.settings-layout__nav {
  margin-bottom: 20px;
}

.settings-layout__menu {
  border-right: none;
}
</style>
