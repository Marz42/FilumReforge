<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import { getErrorMessage } from '@/utils/errors'

const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()

const activeTab = ref<'login' | 'bootstrap'>('login')
const loginSubmitting = ref(false)
const bootstrapSubmitting = ref(false)

const loginForm = reactive({
  email: 'admin@example.com',
  password: 'StrongPassword123!',
})

const bootstrapForm = reactive({
  email: 'admin@example.com',
  password: 'StrongPassword123!',
  real_name: '系统管理员',
  employee_no: 'EMP-ROOT',
})

const redirectTarget = computed(() => {
  const redirect = route.query.redirect
  return typeof redirect === 'string' && redirect.length > 0 ? redirect : '/dashboard'
})

async function handleLogin(): Promise<void> {
  loginSubmitting.value = true

  try {
    await authStore.login(loginForm)
    ElMessage.success('登录成功')
    await router.replace(redirectTarget.value)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loginSubmitting.value = false
  }
}

async function handleBootstrap(): Promise<void> {
  bootstrapSubmitting.value = true

  try {
    await authStore.bootstrapAdmin(bootstrapForm)
    ElMessage.success('管理员初始化成功')
    await router.replace('/dashboard')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    bootstrapSubmitting.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <el-card class="login-card" shadow="never">
      <template #header>
        <div class="login-card__header">
          <div>
            <h1>Project Filum</h1>
            <p>Phase 1 · 系统核心业务底座</p>
          </div>
          <el-tag type="success" effect="dark">JWT + Refresh</el-tag>
        </div>
      </template>

      <el-alert
        title="第一次进入系统时，请先初始化管理员账号。初始化完成后直接使用登录页进入后台。"
        type="info"
        :closable="false"
        show-icon
      />

      <el-tabs v-model="activeTab" class="login-tabs">
        <el-tab-pane label="登录系统" name="login">
          <el-form label-position="top" @submit.prevent="handleLogin">
            <el-form-item label="邮箱">
              <el-input v-model="loginForm.email" autocomplete="username" />
            </el-form-item>
            <el-form-item label="密码">
              <el-input
                v-model="loginForm.password"
                type="password"
                autocomplete="current-password"
                show-password
              />
            </el-form-item>
            <el-button
              type="primary"
              :loading="loginSubmitting"
              class="login-tabs__action"
              @click="handleLogin"
            >
              登录
            </el-button>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="初始化管理员" name="bootstrap">
          <el-form label-position="top" @submit.prevent="handleBootstrap">
            <el-form-item label="管理员邮箱">
              <el-input v-model="bootstrapForm.email" autocomplete="username" />
            </el-form-item>
            <el-form-item label="密码">
              <el-input
                v-model="bootstrapForm.password"
                type="password"
                autocomplete="new-password"
                show-password
              />
            </el-form-item>
            <el-form-item label="姓名">
              <el-input v-model="bootstrapForm.real_name" />
            </el-form-item>
            <el-form-item label="员工编号">
              <el-input v-model="bootstrapForm.employee_no" />
            </el-form-item>
            <el-button
              type="primary"
              :loading="bootstrapSubmitting"
              class="login-tabs__action"
              @click="handleBootstrap"
            >
              初始化管理员
            </el-button>
          </el-form>
        </el-tab-pane>
      </el-tabs>
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

.login-card {
  width: 100%;
  max-width: 560px;
}

.login-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.login-card__header h1 {
  margin: 0;
  font-size: 28px;
}

.login-card__header p {
  margin: 8px 0 0;
  color: #606266;
}

.login-tabs {
  margin-top: 20px;
}

.login-tabs__action {
  width: 100%;
}
</style>
