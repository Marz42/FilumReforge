<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

import {
  createPushSubscription,
  listPushSubscriptions,
  revokePushSubscription,
} from '@/api/push'
import type { PushSubscription } from '@/types/api'
import {
  type BeforeInstallPromptEvent,
  encodeSubscriptionKey,
  getNotificationPermission,
  getWebPushPublicKey,
  isPushSupported,
  registerPwaServiceWorker,
  requestNotificationPermission,
  urlBase64ToUint8Array,
} from '@/utils/pwa'
import { getErrorMessage } from '@/utils/errors'

const loading = ref(false)
const subscriptions = ref<PushSubscription[]>([])
const permission = ref<NotificationPermission>(getNotificationPermission())
const installPrompt = ref<BeforeInstallPromptEvent | null>(null)

const permissionLabelMap: Record<NotificationPermission, string> = {
  default: '未请求',
  denied: '已拒绝',
  granted: '已授权',
}

const activeSubscription = computed(
  () => subscriptions.value.find((item) => item.status === 'active') ?? null,
)
const canInstall = computed(() => installPrompt.value !== null)
const browserSupported = computed(() => isPushSupported())
const publicKeyConfigured = computed(() => Boolean(getWebPushPublicKey()))

function handleBeforeInstallPrompt(event: Event): void {
  event.preventDefault()
  installPrompt.value = event as BeforeInstallPromptEvent
}

async function loadSubscriptions(): Promise<void> {
  loading.value = true
  try {
    subscriptions.value = await listPushSubscriptions()
    permission.value = getNotificationPermission()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

async function handleInstall(): Promise<void> {
  if (!installPrompt.value) {
    ElMessage.info('当前浏览器暂未提供安装入口')
    return
  }

  await installPrompt.value.prompt()
  await installPrompt.value.userChoice
  installPrompt.value = null
}

async function handleSubscribe(): Promise<void> {
  if (!browserSupported.value) {
    ElMessage.warning('当前浏览器不支持 Service Worker 或 Push API')
    return
  }
  if (!publicKeyConfigured.value) {
    ElMessage.warning('缺少 VITE_WEB_PUSH_PUBLIC_KEY，无法创建浏览器订阅')
    return
  }

  let nextPermission = getNotificationPermission()
  if (nextPermission === 'default') {
    nextPermission = await requestNotificationPermission()
  }
  permission.value = nextPermission

  if (nextPermission !== 'granted') {
    ElMessage.warning('浏览器推送权限未授权')
    return
  }

  loading.value = true
  try {
    const registration = await registerPwaServiceWorker()
    if (!registration) {
      throw new Error('Service worker 注册失败')
    }

    let browserSubscription = await registration.pushManager.getSubscription()
    if (!browserSubscription) {
      browserSubscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(getWebPushPublicKey()),
      })
    }

    const jsonValue = browserSubscription.toJSON()
    await createPushSubscription({
      endpoint: browserSubscription.endpoint,
      p256dh_key: jsonValue.keys?.p256dh ?? encodeSubscriptionKey(browserSubscription.getKey('p256dh')),
      auth_key: jsonValue.keys?.auth ?? encodeSubscriptionKey(browserSubscription.getKey('auth')),
      user_agent: navigator.userAgent,
    })

    ElMessage.success('浏览器推送订阅已启用')
    await loadSubscriptions()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

async function handleUnsubscribe(): Promise<void> {
  loading.value = true
  try {
    const registration = await registerPwaServiceWorker()
    const browserSubscription = registration
      ? await registration.pushManager.getSubscription()
      : null

    if (browserSubscription) {
      await browserSubscription.unsubscribe()
    }

    await Promise.all(
      subscriptions.value
        .filter((item) => item.status === 'active')
        .map((item) => revokePushSubscription(item.id)),
    )
    ElMessage.success('浏览器推送订阅已关闭')
    await loadSubscriptions()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
  void loadSubscriptions()
})

onUnmounted(() => {
  window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
})
</script>

<template>
  <el-card shadow="never" v-loading="loading">
    <template #header>
      <div class="push-card__header">
        <span>浏览器推送与 PWA</span>
        <el-space>
          <el-button size="small" plain :disabled="!canInstall" @click="handleInstall">
            安装应用
          </el-button>
          <el-button
            v-if="activeSubscription"
            size="small"
            type="danger"
            plain
            @click="handleUnsubscribe"
          >
            关闭推送
          </el-button>
          <el-button
            v-else
            size="small"
            type="primary"
            @click="handleSubscribe"
          >
            启用推送
          </el-button>
        </el-space>
      </div>
    </template>

    <el-descriptions :column="1" border>
      <el-descriptions-item label="浏览器支持">
        {{ browserSupported ? '支持' : '不支持' }}
      </el-descriptions-item>
      <el-descriptions-item label="推送权限">
        {{ permissionLabelMap[permission] }}
      </el-descriptions-item>
      <el-descriptions-item label="VAPID 公钥">
        {{ publicKeyConfigured ? '已配置' : '未配置' }}
      </el-descriptions-item>
      <el-descriptions-item label="当前订阅">
        {{ activeSubscription?.endpoint ?? '暂无活跃订阅' }}
      </el-descriptions-item>
    </el-descriptions>

    <el-alert
      v-if="permission === 'denied'"
      title="浏览器消息推送已被拒绝，请在浏览器设置中重新授权。"
      type="warning"
      show-icon
      :closable="false"
      class="push-card__alert"
    />

    <el-alert
      title="当前已接入的浏览器通知场景：任务指派、任务转派、任务抄送、逾期提醒、审批待办与审批提醒。需要先完成订阅，且后端 VAPID 配置与 worker 正常运行。"
      type="info"
      show-icon
      :closable="false"
      class="push-card__alert"
    />
  </el-card>
</template>

<style scoped>
.push-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.push-card__alert {
  margin-top: 16px;
}
</style>
