import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import './styles/theme.css'

import App from './App.vue'
import router from './router'
import { setUnauthorizedHandler } from './api/session'
import { useAuthStore } from './stores/auth'
import { registerPwaServiceWorker } from './utils/pwa'

const app = createApp(App)
const pinia = createPinia()
const authStore = useAuthStore(pinia)

setUnauthorizedHandler(() => {
  authStore.clearSession()
  void router.push({ name: 'login' })
})

await authStore.restoreSession()
await authStore.fetchBootstrapStatus().catch(() => undefined)

app.use(pinia)
app.use(ElementPlus)
app.use(router)

void registerPwaServiceWorker()

app.mount('#app')
