<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

import {
  createPushSubscription,
  getPushSubscriptionConfig,
  listPushSubscriptions,
  revokePushSubscription,
  sendPushTestNotification,
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
import { CanceledError } from 'axios'
import { useLatestRequest } from '@/composables/useLatestRequest'
import { showError } from '@/utils/errors'

const loading = ref(false)
const busy = ref(false)
const currentEndpoint = ref('')
const subscriptions = ref<PushSubscription[]>([])
const permission = ref<NotificationPermission>(getNotificationPermission())
const installPrompt = ref<BeforeInstallPromptEvent | null>(null)
const runtimePublicKey = ref('')
const runtimePushEnabled = ref(false)
const runtimeConfigLoaded = ref(false)

const permissionLabelMap: Record<NotificationPermission, string> = {
  default: '未请求',
  denied: '已拒绝',
  granted: '已授权',
}

const activeSubscription = computed(
  () => subscriptions.value.find((item) => item.status === 'active' && item.endpoint === currentEndpoint.value) ?? null,
)
const canInstall = computed(() => installPrompt.value !== null)
const browserSupported = computed(() => isPushSupported())
const resolvedPublicKey = computed(() => runtimePublicKey.value || getWebPushPublicKey())
const publicKeyConfigured = computed(() => Boolean(resolvedPublicKey.value))
const pushReady = computed(
  () => runtimeConfigLoaded.value && runtimePushEnabled.value && publicKeyConfigured.value,
)

function handleBeforeInstallPrompt(event: Event): void {
  event.preventDefault()
  installPrompt.value = event as BeforeInstallPromptEvent
}

const otherDeviceCount = computed(() => subscriptions.value.filter((item) => item.status === 'active' && item.endpoint !== currentEndpoint.value).length)
const reads = useLatestRequest(() => { subscriptions.value = []; currentEndpoint.value = ''; runtimeConfigLoaded.value = false; loading.value = false })
const operations = useLatestRequest(() => { busy.value = false })

async function loadData(): Promise<void> {
  const request = reads.start()
  loading.value = true
  try {
    const [nextSubscriptions, pushConfig, registration] = await Promise.all([
      listPushSubscriptions(),
      getPushSubscriptionConfig().catch(() => ({ public_key: null, is_enabled: false })),
      browserSupported.value ? registerPwaServiceWorker() : Promise.resolve(null),
    ])
    const local = registration ? await registration.pushManager.getSubscription() : null
    if (!request.isCurrent()) return
    subscriptions.value = nextSubscriptions
    currentEndpoint.value = local?.endpoint ?? ''
    runtimePublicKey.value = pushConfig.public_key?.trim() ?? ''
    runtimePushEnabled.value = pushConfig.is_enabled
    runtimeConfigLoaded.value = true
    permission.value = getNotificationPermission()
  } catch (error) {
    if (request.isCurrent()) showError(error)
  } finally {
    if (request.isCurrent()) loading.value = false
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
  if (busy.value || loading.value) return
  if (!browserSupported.value || !pushReady.value) {
    ElMessage.warning('浏览器推送暂不可用，站内消息仍可正常使用')
    return
  }
  const operation = operations.start()
  const current = () => { if (!operation.isCurrent()) throw new CanceledError('Session changed') }
  let created: globalThis.PushSubscription | null = null
  busy.value = true
  try {
    let nextPermission = getNotificationPermission()
    if (nextPermission === 'default') nextPermission = await requestNotificationPermission()
    current()
    permission.value = nextPermission
    if (nextPermission !== 'granted') { ElMessage.warning('浏览器推送权限未授权'); return }
    const registration = await registerPwaServiceWorker()
    current()
    if (!registration) throw new Error('浏览器通知服务尚未就绪，请稍后重试')
    let local = await registration.pushManager.getSubscription()
    current()
    if (local && !subscriptions.value.some((item) => item.endpoint === local!.endpoint)) {
      // Never transfer another account's endpoint on the server.
      await local.unsubscribe()
      current()
      if (await registration.pushManager.getSubscription()) throw new Error('旧浏览器订阅尚未关闭，请重试')
      local = null
    }
    if (!local) {
      local = await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlBase64ToUint8Array(resolvedPublicKey.value) })
      created = local
    }
    current()
    const json = local.toJSON()
    await createPushSubscription({ endpoint: local.endpoint,
      p256dh_key: json.keys?.p256dh ?? encodeSubscriptionKey(local.getKey('p256dh')),
      auth_key: json.keys?.auth ?? encodeSubscriptionKey(local.getKey('auth')),
      user_agent: navigator.userAgent })
    current()
    created = null
    ElMessage.success('本浏览器推送已启用')
    await loadData()
  } catch (error) {
    if (created) await created.unsubscribe().catch(() => undefined)
    if (operation.isCurrent()) showError(error)
  } finally { if (operation.isCurrent()) busy.value = false }
}

async function handleUnsubscribe(): Promise<void> {
  if (busy.value || loading.value) return
  const subscription = activeSubscription.value
  if (!subscription) return
  const operation = operations.start()
  busy.value = true
  try {
    // Server revocation first: even if browser cleanup fails, delivery stops for this device.
    await revokePushSubscription(subscription.id)
    if (!operation.isCurrent()) return
    const registration = await registerPwaServiceWorker()
    const local = registration ? await registration.pushManager.getSubscription() : null
    if (!operation.isCurrent()) return
    if (local?.endpoint === subscription.endpoint) {
      await local.unsubscribe()
      if (await registration!.pushManager.getSubscription()) throw new Error('服务端推送已停止，但浏览器订阅未能清理，请重试')
    }
    if (!operation.isCurrent()) return
    ElMessage.success('本浏览器推送已关闭，其他设备不受影响')
    await loadData()
  } catch (error) {
    if (operation.isCurrent()) { showError(error); await loadData() }
  } finally { if (operation.isCurrent()) busy.value = false }
}

async function handleSendTestPush(): Promise<void> {
  if (busy.value || loading.value || !activeSubscription.value || !pushReady.value) return
  const operation = operations.start()
  busy.value = true
  try {
    const result = await sendPushTestNotification()
    if (!operation.isCurrent()) return
    if (result.status === 'failed') ElMessage.error(result.detail)
    else ElMessage.info(result.detail)
  } catch (error) { if (operation.isCurrent()) showError(error) }
  finally { if (operation.isCurrent()) busy.value = false }
}

onMounted(() => {
  window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
  void loadData()
})

onUnmounted(() => {
  window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
})
</script>

<template>
  <el-card shadow="never" v-loading="loading || busy">
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
            plain
            :disabled="busy || loading || !pushReady"
            data-testid="push-test"
            @click="handleSendTestPush"
          >
            发送测试推送
          </el-button>
          <el-button
            v-if="activeSubscription"
            size="small"
            type="danger"
            plain
            :disabled="busy || loading"
            data-testid="push-disable"
            @click="handleUnsubscribe"
          >
            关闭推送
          </el-button>
          <el-button
            v-else
            size="small"
            type="primary"
            :disabled="busy || loading || !pushReady || !browserSupported"
            data-testid="push-enable"
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
      <el-descriptions-item label="通知服务">
        {{ pushReady ? '可用' : '暂不可用' }}
      </el-descriptions-item>
      <el-descriptions-item label="当前订阅">
        {{ activeSubscription ? '本浏览器已启用' : '本浏览器未启用' }}
        <span v-if="otherDeviceCount">；其他设备 {{ otherDeviceCount }} 个已启用</span>
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
      v-if="runtimeConfigLoaded && !runtimePushEnabled"
      title="浏览器推送暂不可用，请联系管理员。站内消息仍可正常使用。"
      type="warning"
      show-icon
      :closable="false"
      class="push-card__alert"
    />

    <el-alert
      title="当前已接入的浏览器通知场景：任务指派、任务转派、任务抄送、逾期提醒、审批待办与审批提醒。启用后可在此浏览器接收提醒。"
      type="info"
      show-icon
      :closable="false"
      class="push-card__alert"
    />

    <el-alert
      v-if="activeSubscription"
      title="测试消息会发往此账号已启用推送的设备；提交请求不代表设备已收到，请检查实际通知。"
      type="success"
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
