<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { changePassword } from '@/api/auth'
import { getErrorMessage } from '@/utils/errors'
import { formatPasswordValidationMessage, validatePasswordClient } from '@/utils/passwordPolicy'

const submitting = ref(false)

const form = reactive({
  currentPassword: '',
  newPassword: '',
  confirmPassword: '',
})

async function handleSubmit(): Promise<void> {
  if (form.newPassword !== form.confirmPassword) {
    ElMessage.error('两次输入的新密码不一致')
    return
  }

  const validation = validatePasswordClient(form.newPassword)
  if (!validation.valid) {
    ElMessage.error(formatPasswordValidationMessage(validation.reasons))
    return
  }

  submitting.value = true

  try {
    await changePassword({
      current_password: form.currentPassword,
      new_password: form.newPassword,
    })
    ElMessage.success('密码已更新，请使用新密码重新登录')
    form.currentPassword = ''
    form.newPassword = ''
    form.confirmPassword = ''
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-card shadow="never" class="settings-section filum-panel-card" data-testid="settings-security-section">
    <template #header>
      <div class="filum-page-header__copy">
        <span class="filum-page-header__eyebrow">Security</span>
        <span class="filum-page-header__title">安全与密码</span>
      </div>
    </template>

    <p class="settings-section__description">修改登录密码。新密码需满足安全策略（长度、大小写、数字与符号）。</p>

    <el-form
      label-position="top"
      class="settings-section__form"
      data-testid="settings-change-password-form"
      @submit.prevent="handleSubmit"
    >
      <el-form-item label="当前密码">
        <div data-testid="settings-current-password">
          <el-input
            v-model="form.currentPassword"
            type="password"
            autocomplete="current-password"
            show-password
          />
        </div>
      </el-form-item>
      <el-form-item label="新密码">
        <div data-testid="settings-new-password">
          <el-input
            v-model="form.newPassword"
            type="password"
            autocomplete="new-password"
            show-password
          />
        </div>
      </el-form-item>
      <el-form-item label="确认新密码">
        <div data-testid="settings-confirm-password">
          <el-input
            v-model="form.confirmPassword"
            type="password"
            autocomplete="new-password"
            show-password
          />
        </div>
      </el-form-item>
      <el-button type="primary" :loading="submitting" data-testid="settings-submit-password" @click="handleSubmit">
        更新密码
      </el-button>
    </el-form>
  </el-card>
</template>

<style scoped>
.settings-section__description {
  margin: 0 0 20px;
  color: var(--filum-text-secondary);
  line-height: 1.7;
}

.settings-section__form {
  max-width: 420px;
}
</style>
