<script setup lang="ts">
import PushSubscriptionCard from '@/components/PushSubscriptionCard.vue'
</script>

<template>
  <el-card shadow="never" class="settings-section filum-panel-card" data-testid="settings-notifications-section">
    <template #header>
      <div class="filum-page-header__copy">
        <span class="filum-page-header__eyebrow">Notifications</span>
        <span class="filum-page-header__title">通知偏好</span>
      </div>
    </template>

    <p class="settings-section__description">
      管理浏览器推送、PWA 安装与本机通知权限。多个浏览器或设备可分别订阅，系统会向当前账号的全部活跃订阅发送推送。
    </p>

    <PushSubscriptionCard />
  </el-card>
</template>

<style scoped>
.settings-section__description {
  margin: 0 0 20px;
  color: var(--filum-text-secondary);
  line-height: 1.7;
}
</style>
