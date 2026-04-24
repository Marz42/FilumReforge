<script setup lang="ts">
import PushSubscriptionCard from '@/components/PushSubscriptionCard.vue'
</script>

<template>
  <div class="settings-view">
    <el-row :gutter="20">
      <el-col :xs="24" :xl="18">
        <el-card shadow="never" class="settings-view__intro">
          <template #header>
            <span>设置</span>
          </template>

          <p class="settings-view__description">
            当前集中管理浏览器推送、PWA 安装与本机通知权限。多个浏览器或设备可分别订阅，系统会向当前账号的全部活跃订阅发送推送。
          </p>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="settings-view__section">
      <el-col :xs="24" :xl="18">
        <PushSubscriptionCard />
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.settings-view__intro,
.settings-view__section {
  margin-bottom: 20px;
}

.settings-view__description {
  margin: 0;
  color: #606266;
  line-height: 1.7;
}
</style>