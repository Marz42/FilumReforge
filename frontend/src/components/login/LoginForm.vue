<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import { getErrorMessage } from '@/utils/errors'

const props = defineProps<{
  redirectTarget: string
}>()

const authStore = useAuthStore()
const router = useRouter()
const submitting = ref(false)

const form = reactive({
  email: '',
  password: '',
})

async function handleSubmit(): Promise<void> {
  submitting.value = true

  try {
    await authStore.login(form)
    ElMessage.success('登录成功')
    await router.replace(props.redirectTarget)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="login-form" data-testid="login-form">
    <div class="login-form__heading">
      <h2>登录系统</h2>
      <p>使用邮箱与密码进入工作台</p>
    </div>

    <el-form label-position="top" @submit.prevent="handleSubmit">
      <el-form-item label="邮箱">
        <div data-testid="login-email">
          <el-input v-model="form.email" autocomplete="username" />
        </div>
      </el-form-item>
      <el-form-item label="密码">
        <div data-testid="login-password">
          <el-input
            v-model="form.password"
            type="password"
            autocomplete="current-password"
            show-password
          />
        </div>
      </el-form-item>
      <el-button
        type="primary"
        :loading="submitting"
        class="login-form__action"
        data-testid="login-submit"
        @click="handleSubmit"
      >
        登录
      </el-button>
    </el-form>

    <p class="login-form__footer">本系统采用邀请制，请联系 HR 获取账号</p>
  </div>
</template>

<style scoped>
.login-form__heading h2 {
  margin: 0;
  font-size: 22px;
}

.login-form__heading p {
  margin: 8px 0 0;
  color: #606266;
}

.login-form__action {
  width: 100%;
}

.login-form__footer {
  margin: 20px 0 0;
  font-size: 13px;
  line-height: 1.6;
  color: #909399;
  text-align: center;
}
</style>
