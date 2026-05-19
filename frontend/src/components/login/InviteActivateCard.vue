<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import type { UserInvitationPreview } from '@/types/api'
import { getErrorMessage } from '@/utils/errors'
import { formatPasswordValidationMessage, validatePasswordClient } from '@/utils/passwordPolicy'

const props = defineProps<{
  token: string
  redirectTarget: string
}>()

const authStore = useAuthStore()
const router = useRouter()
const loading = ref(false)
const submitting = ref(false)
const preview = ref<UserInvitationPreview | null>(null)

const form = reactive({
  password: '',
  confirmPassword: '',
})

const roleLabel = computed(() => {
  if (!preview.value) {
    return '—'
  }
  if (preview.value.role === 'admin') {
    return '管理员'
  }
  if (preview.value.role === 'hr') {
    return 'HR'
  }
  return '员工'
})

watch(
  () => props.token,
  (token) => {
    if (!token) {
      preview.value = null
      return
    }

    loading.value = true
    authStore
      .fetchInvitationPreview(token)
      .then((result) => {
        preview.value = result
      })
      .catch((error) => {
        preview.value = null
        ElMessage.error(getErrorMessage(error))
      })
      .finally(() => {
        loading.value = false
      })
  },
  { immediate: true },
)

async function handleSubmit(): Promise<void> {
  if (!props.token) {
    ElMessage.error('缺少邀请令牌')
    return
  }

  if (form.password !== form.confirmPassword) {
    ElMessage.error('两次输入的密码不一致')
    return
  }

  const validation = validatePasswordClient(form.password)
  if (!validation.valid) {
    ElMessage.error(formatPasswordValidationMessage(validation.reasons))
    return
  }

  submitting.value = true

  try {
    await authStore.acceptInvitation({
      token: props.token,
      password: form.password,
    })
    ElMessage.success('注册成功')
    await router.replace(props.redirectTarget)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="invite-activate" data-testid="login-invite-activate">
    <div class="invite-activate__heading">
      <h2>欢迎加入，请设置密码</h2>
      <p>完成密码设置后即可激活账号并自动登录</p>
    </div>

    <el-skeleton v-if="loading" :rows="4" animated />

    <template v-else-if="preview">
      <el-descriptions :column="1" border class="invite-activate__meta">
        <el-descriptions-item label="邀请邮箱">
          {{ preview.email }}
        </el-descriptions-item>
        <el-descriptions-item label="角色">
          {{ roleLabel }}
        </el-descriptions-item>
        <el-descriptions-item label="有效期至">
          {{ preview.expires_at }}
        </el-descriptions-item>
      </el-descriptions>

      <el-form label-position="top" @submit.prevent="handleSubmit">
        <el-form-item label="设置密码">
          <el-input
            v-model="form.password"
            type="password"
            autocomplete="new-password"
            show-password
            data-testid="invite-password"
          />
        </el-form-item>
        <el-form-item label="确认密码">
          <el-input
            v-model="form.confirmPassword"
            type="password"
            autocomplete="new-password"
            show-password
            data-testid="invite-confirm-password"
          />
        </el-form-item>
        <el-button
          type="primary"
          :loading="submitting"
          class="invite-activate__action"
          data-testid="invite-submit"
          @click="handleSubmit"
        >
          完成注册
        </el-button>
      </el-form>
    </template>

    <el-empty v-else description="当前邀请不可用，请联系管理员重新生成邀请链接。" />
  </div>
</template>

<style scoped>
.invite-activate__heading h2 {
  margin: 0;
  font-size: 22px;
}

.invite-activate__heading p {
  margin: 8px 0 0;
  color: #606266;
}

.invite-activate__meta {
  margin-bottom: 20px;
}

.invite-activate__action {
  width: 100%;
}
</style>
