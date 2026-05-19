<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'

import BootstrapWizard from '@/components/login/BootstrapWizard.vue'
import InviteActivateCard from '@/components/login/InviteActivateCard.vue'
import LoginForm from '@/components/login/LoginForm.vue'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const route = useRoute()

const redirectTarget = computed(() => {
  const redirect = route.query.redirect
  return typeof redirect === 'string' && redirect.length > 0 ? redirect : '/overview'
})

const invitationToken = computed(() => {
  const invite = route.query.invite
  return typeof invite === 'string' && invite.length > 0 ? invite : ''
})

type LoginScenario = 'loading' | 'invite' | 'bootstrap' | 'login'

const scenario = computed<LoginScenario>(() => {
  if (invitationToken.value) {
    return 'invite'
  }
  if (!authStore.bootstrapStatusLoaded) {
    return 'loading'
  }
  if (authStore.bootstrapRequired) {
    return 'bootstrap'
  }
  return 'login'
})

onMounted(() => {
  if (!authStore.bootstrapStatusLoaded) {
    void authStore.fetchBootstrapStatus().catch(() => undefined)
  }
})
</script>

<template>
  <div class="login-page" data-testid="login-page">
    <el-card class="login-page__card" shadow="never" data-testid="login-card">
      <template #header>
        <div class="login-page__header">
          <div>
            <h1>Project Filum</h1>
            <p>统一协同与人事工作台</p>
          </div>
          <el-tag type="success" effect="dark">JWT + Refresh</el-tag>
        </div>
      </template>

      <div v-if="scenario === 'loading'" class="login-page__loading" data-testid="login-loading">
        <el-skeleton :rows="5" animated />
      </div>

      <InviteActivateCard
        v-else-if="scenario === 'invite'"
        :token="invitationToken"
        :redirect-target="redirectTarget"
      />

      <BootstrapWizard v-else-if="scenario === 'bootstrap'" />

      <LoginForm v-else :redirect-target="redirectTarget" />
    </el-card>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: linear-gradient(135deg, #eff6ff 0%, #f5f7fa 100%);
}

.login-page__card {
  width: 100%;
  max-width: 560px;
}

.login-page__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.login-page__header h1 {
  margin: 0;
  font-size: 28px;
}

.login-page__header p {
  margin: 8px 0 0;
  color: #606266;
}

.login-page__loading {
  padding: 8px 0;
}
</style>
