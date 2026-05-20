import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { useAppStore } from '@/stores/app'

describe('App store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('opens and closes the notification drawer with optional message id', () => {
    const appStore = useAppStore()

    expect(appStore.notificationDrawerOpen).toBe(false)
    expect(appStore.notificationDrawerMessageId).toBe('')

    appStore.openNotificationDrawer('message-42')
    expect(appStore.notificationDrawerOpen).toBe(true)
    expect(appStore.notificationDrawerMessageId).toBe('message-42')

    appStore.closeNotificationDrawer()
    expect(appStore.notificationDrawerOpen).toBe(false)
    expect(appStore.notificationDrawerMessageId).toBe('')
  })
})
