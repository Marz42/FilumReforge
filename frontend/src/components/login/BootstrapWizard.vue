<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import { getErrorMessage } from '@/utils/errors'
import { formatPasswordValidationMessage, validatePasswordClient } from '@/utils/passwordPolicy'

const authStore = useAuthStore()
const router = useRouter()
const activeStep = ref(0)
const submitting = ref(false)

const form = reactive({
  email: '',
  password: '',
  confirmPassword: '',
  real_name: '系统管理员',
  employee_no: 'EMP-ROOT',
})

function handleNext(): void {
  if (activeStep.value === 0) {
    if (!form.email.trim()) {
      ElMessage.error('请填写管理员邮箱')
      return
    }
  }

  if (activeStep.value === 1) {
    if (form.password !== form.confirmPassword) {
      ElMessage.error('两次输入的密码不一致')
      return
    }
    const validation = validatePasswordClient(form.password)
    if (!validation.valid) {
      ElMessage.error(formatPasswordValidationMessage(validation.reasons))
      return
    }
  }

  if (activeStep.value === 2) {
    if (!form.real_name.trim() || !form.employee_no.trim()) {
      ElMessage.error('请填写姓名与员工编号')
      return
    }
    void handleSubmit()
    return
  }

  activeStep.value += 1
}

function handleBack(): void {
  if (activeStep.value > 0) {
    activeStep.value -= 1
  }
}

async function handleSubmit(): Promise<void> {
  submitting.value = true

  try {
    await authStore.bootstrapAdmin({
      email: form.email.trim(),
      password: form.password,
      real_name: form.real_name.trim(),
      employee_no: form.employee_no.trim(),
    })
    ElMessage.success('管理员初始化成功')
    await router.replace('/overview')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="bootstrap-wizard" data-testid="bootstrap-wizard">
    <div class="bootstrap-wizard__heading">
      <h2>系统初始化</h2>
      <p>首次进入系统，请创建管理员账号与根部门</p>
    </div>

    <el-alert
      title="请确保后端服务与 PostgreSQL 已启动后再继续。"
      type="info"
      :closable="false"
      show-icon
      class="bootstrap-wizard__alert"
    />

    <el-steps :active="activeStep" finish-status="success" align-center class="bootstrap-wizard__steps">
      <el-step title="管理员邮箱" />
      <el-step title="设置密码" />
      <el-step title="基本信息" />
    </el-steps>

    <el-form label-position="top" class="bootstrap-wizard__form" @submit.prevent="handleNext">
      <template v-if="activeStep === 0">
        <el-form-item label="管理员邮箱">
          <el-input v-model="form.email" autocomplete="username" data-testid="bootstrap-email" />
        </el-form-item>
      </template>

      <template v-else-if="activeStep === 1">
        <el-form-item label="密码">
          <el-input
            v-model="form.password"
            type="password"
            autocomplete="new-password"
            show-password
            data-testid="bootstrap-password"
          />
        </el-form-item>
        <el-form-item label="确认密码">
          <el-input
            v-model="form.confirmPassword"
            type="password"
            autocomplete="new-password"
            show-password
            data-testid="bootstrap-confirm-password"
          />
        </el-form-item>
      </template>

      <template v-else>
        <el-form-item label="姓名">
          <el-input v-model="form.real_name" data-testid="bootstrap-real-name" />
        </el-form-item>
        <el-form-item label="员工编号">
          <el-input v-model="form.employee_no" data-testid="bootstrap-employee-no" />
        </el-form-item>
      </template>

      <div class="bootstrap-wizard__actions">
        <el-button v-if="activeStep > 0" :disabled="submitting" @click="handleBack">上一步</el-button>
        <el-button type="primary" :loading="submitting" data-testid="bootstrap-submit" @click="handleNext">
          {{ activeStep === 2 ? '初始化管理员' : '下一步' }}
        </el-button>
      </div>
    </el-form>
  </div>
</template>

<style scoped>
.bootstrap-wizard__heading h2 {
  margin: 0;
  font-size: 22px;
}

.bootstrap-wizard__heading p {
  margin: 8px 0 0;
  color: #606266;
}

.bootstrap-wizard__alert {
  margin-top: 16px;
}

.bootstrap-wizard__steps {
  margin: 24px 0;
}

.bootstrap-wizard__actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
