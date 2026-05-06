<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import type { UserInvitationPreview } from '@/types/api'
import { getErrorMessage } from '@/utils/errors'

const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()

const activeTab = ref<'login' | 'bootstrap' | 'invite'>('login')
const loginSubmitting = ref(false)
const bootstrapSubmitting = ref(false)
const invitationSubmitting = ref(false)
const invitationLoading = ref(false)
const invitationPreview = ref<UserInvitationPreview | null>(null)

const loginForm = reactive({
  email: '',
  password: '',
})

const bootstrapForm = reactive({
  email: '',
  password: '',
  real_name: '系统管理员',
  employee_no: 'EMP-ROOT',
})

const invitationForm = reactive({
  password: '',
  confirmPassword: '',
})

const redirectTarget = computed(() => {
  const redirect = route.query.redirect
  return typeof redirect === 'string' && redirect.length > 0 ? redirect : '/overview'
})
const showBootstrapEntry = computed(() => authStore.bootstrapRequired)
const invitationToken = computed(() => {
  const invite = route.query.invite
  return typeof invite === 'string' && invite.length > 0 ? invite : ''
})
const showInvitationEntry = computed(() => invitationToken.value.length > 0)
const invitationRoleLabel = computed(() => {
  if (!invitationPreview.value) {
    return '—'
  }
  if (invitationPreview.value.role === 'admin') {
    return '管理员'
  }
  if (invitationPreview.value.role === 'hr') {
    return 'HR'
  }
  return '员工'
})

watch(
  () => authStore.bootstrapRequired,
  (required) => {
    if (!required && activeTab.value === 'bootstrap') {
      activeTab.value = 'login'
    }
  },
)

watch(
  invitationToken,
  (token) => {
    if (!token) {
      invitationPreview.value = null
      if (activeTab.value === 'invite') {
        activeTab.value = 'login'
      }
      return
    }

    activeTab.value = 'invite'
    invitationLoading.value = true
    authStore
      .fetchInvitationPreview(token)
      .then((preview) => {
        invitationPreview.value = preview
      })
      .catch((error) => {
        invitationPreview.value = null
        ElMessage.error(getErrorMessage(error))
      })
      .finally(() => {
        invitationLoading.value = false
      })
  },
  { immediate: true },
)

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
    await router.replace('/overview')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    bootstrapSubmitting.value = false
  }
}

async function handleAcceptInvitation(): Promise<void> {
  if (!invitationToken.value) {
    ElMessage.error('缺少邀请令牌')
    return
  }
  if (invitationForm.password !== invitationForm.confirmPassword) {
    ElMessage.error('两次输入的密码不一致')
    return
  }

  invitationSubmitting.value = true

  try {
    await authStore.acceptInvitation({
      token: invitationToken.value,
      password: invitationForm.password,
    })
    ElMessage.success('注册成功')
    await router.replace(redirectTarget.value)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    invitationSubmitting.value = false
  }
}

onMounted(() => {
  if (!authStore.bootstrapStatusLoaded) {
    void authStore.fetchBootstrapStatus().catch(() => undefined)
  }
})
</script>

<template>
  <div class="login-page" data-testid="login-page">
    <el-card class="login-card" shadow="never" data-testid="login-card">
      <template #header>
        <div class="login-card__header">
          <div>
            <h1>Project Filum</h1>
            <p>统一协同与人事工作台</p>
          </div>
          <el-tag type="success" effect="dark">JWT + Refresh</el-tag>
        </div>
      </template>

      <el-alert
        v-if="showBootstrapEntry"
        title="第一次进入系统时，请先初始化管理员账号；在此之前，请确保后端服务和 PostgreSQL 已启动。"
        type="info"
        :closable="false"
        show-icon
      />

      <el-alert
        v-if="showInvitationEntry"
        title="检测到邀请注册链接。请设置登录密码后完成账号激活。"
        type="success"
        :closable="false"
        show-icon
        class="login-page__invite-alert"
      />

      <el-tabs v-model="activeTab" class="login-tabs" data-testid="login-tabs">
        <el-tab-pane label="登录系统" name="login">
          <el-form label-position="top" @submit.prevent="handleLogin">
            <el-form-item label="邮箱">
              <div data-testid="login-email">
                <el-input v-model="loginForm.email" autocomplete="username" />
              </div>
            </el-form-item>
            <el-form-item label="密码">
              <div data-testid="login-password">
                <el-input
                  v-model="loginForm.password"
                  type="password"
                  autocomplete="current-password"
                  show-password
                />
              </div>
            </el-form-item>
            <el-button
              type="primary"
              :loading="loginSubmitting"
              class="login-tabs__action"
              data-testid="login-submit"
              @click="handleLogin"
            >
              登录
            </el-button>
          </el-form>
        </el-tab-pane>

        <el-tab-pane v-if="showBootstrapEntry" label="初始化管理员" name="bootstrap">
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

        <el-tab-pane v-if="showInvitationEntry" label="邀请注册" name="invite">
          <el-skeleton v-if="invitationLoading" :rows="4" animated />
          <template v-else-if="invitationPreview">
            <el-descriptions :column="1" border class="login-tabs__invite-meta">
              <el-descriptions-item label="邀请邮箱">
                {{ invitationPreview.email }}
              </el-descriptions-item>
              <el-descriptions-item label="角色">
                {{ invitationRoleLabel }}
              </el-descriptions-item>
              <el-descriptions-item label="有效期至">
                {{ invitationPreview.expires_at }}
              </el-descriptions-item>
            </el-descriptions>

            <el-form label-position="top" @submit.prevent="handleAcceptInvitation">
              <el-form-item label="设置密码">
                <el-input
                  v-model="invitationForm.password"
                  type="password"
                  autocomplete="new-password"
                  show-password
                />
              </el-form-item>
              <el-form-item label="确认密码">
                <el-input
                  v-model="invitationForm.confirmPassword"
                  type="password"
                  autocomplete="new-password"
                  show-password
                />
              </el-form-item>
              <el-button
                type="primary"
                :loading="invitationSubmitting"
                class="login-tabs__action"
                @click="handleAcceptInvitation"
              >
                完成注册
              </el-button>
            </el-form>
          </template>
          <el-empty v-else description="当前邀请不可用，请联系管理员重新生成邀请链接。" />
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

.login-page__invite-alert {
  margin-top: 16px;
}

.login-tabs__invite-meta {
  margin-bottom: 20px;
}

.login-tabs__action {
  width: 100%;
}
</style>
