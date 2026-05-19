<script setup lang="ts">
import { computed } from 'vue'

import { useAuthStore } from '@/stores/auth'
import type { UserRole, UserStatus } from '@/types/api'

const authStore = useAuthStore()

const roleLabelMap: Record<UserRole, string> = {
  admin: '管理员',
  hr: 'HR',
  employee: '员工',
}

const statusLabelMap: Record<UserStatus, string> = {
  active: '已启用',
  inactive: '未激活',
  suspended: '已停用',
  offboarded: '已离职',
}

const profileItems = computed(() => {
  const user = authStore.user
  if (!user) {
    return []
  }

  return [
    { label: '邮箱', value: user.email },
    { label: '角色', value: roleLabelMap[user.role] },
    { label: '账号状态', value: statusLabelMap[user.status] },
    { label: '最近登录', value: user.last_login_at ?? '—' },
  ]
})
</script>

<template>
  <el-card shadow="never" class="settings-section filum-panel-card" data-testid="settings-profile-section">
    <template #header>
      <div class="filum-page-header__copy">
        <span class="filum-page-header__eyebrow">Profile</span>
        <span class="filum-page-header__title">个人资料</span>
      </div>
    </template>

    <p class="settings-section__description">当前登录账号的基础信息（只读）。如需修改组织档案，请联系 HR。</p>

    <el-descriptions v-if="profileItems.length" :column="1" border>
      <el-descriptions-item v-for="item in profileItems" :key="item.label" :label="item.label">
        {{ item.value }}
      </el-descriptions-item>
    </el-descriptions>
    <el-empty v-else description="未加载用户信息" />
  </el-card>
</template>

<style scoped>
.settings-section__description {
  margin: 0 0 20px;
  color: var(--filum-text-secondary);
  line-height: 1.7;
}
</style>
