import { createMemoryHistory, createRouter, type RouteRecordRaw } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import { mount, type ComponentMountingOptions, type VueWrapper } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import type { Component } from 'vue'

type MountAppOptions = ComponentMountingOptions<Component> & {
  routes?: RouteRecordRaw[]
  initialPath?: string
}

/**
 * W13-C: shared mount helper for router + Pinia + Element Plus.
 * Suites should prefer this over ad-hoc plugin wiring.
 */
export async function mountApp(
  component: Component,
  options: MountAppOptions = {},
): Promise<{ wrapper: VueWrapper; router: ReturnType<typeof createRouter> }> {
  const pinia = createPinia()
  setActivePinia(pinia)

  const routes = options.routes ?? [
    {
      path: '/',
      name: 'home',
      component,
    },
  ]
  const router = createRouter({
    history: createMemoryHistory(),
    routes,
  })
  await router.push(options.initialPath ?? '/')
  await router.isReady()

  const { routes: _routes, initialPath: _initialPath, global, ...rest } = options
  const wrapper = mount(component, {
    ...rest,
    global: {
      ...global,
      plugins: [ElementPlus, pinia, router, ...((global?.plugins as unknown[]) ?? [])],
    },
  })

  return { wrapper, router }
}
