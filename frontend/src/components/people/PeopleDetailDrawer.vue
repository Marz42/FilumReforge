<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'

import PeopleAnchorNav, { type PeopleAnchorId, type PeopleAnchorItem } from '@/components/people/PeopleAnchorNav.vue'

interface Props {
  modelValue: boolean
  activeAnchor: PeopleAnchorId
  loading?: boolean
  personLabel: string
  personEmail: string
  statusLabel: string
  statusTagType: '' | 'success' | 'info' | 'warning' | 'danger'
  canCreateProfile?: boolean
  anchorItems: PeopleAnchorItem[]
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
  canCreateProfile: false,
})

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'update:activeAnchor': [value: PeopleAnchorId]
  'create-profile': []
  'scroll-to-account': []
}>()

const scrollContainer = ref<HTMLElement | null>(null)
let observer: IntersectionObserver | null = null

function closeDrawer(): void {
  emit('update:modelValue', false)
}

function scrollToAnchor(anchor: PeopleAnchorId): void {
  const container = scrollContainer.value
  if (!container) {
    return
  }

  const target = container.querySelector<HTMLElement>(`[data-people-section="${anchor}"]`)
  if (!target || typeof target.scrollIntoView !== 'function') {
    return
  }

  target.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function handleAnchorNavigate(anchor: PeopleAnchorId): void {
  emit('update:activeAnchor', anchor)
  void nextTick(() => {
    scrollToAnchor(anchor)
  })
}

function setupObserver(): void {
  if (typeof IntersectionObserver === 'undefined') {
    return
  }

  observer?.disconnect()
  const container = scrollContainer.value
  if (!container) {
    return
  }

  const sections = container.querySelectorAll<HTMLElement>('[data-people-section]')
  if (sections.length === 0) {
    return
  }

  observer = new IntersectionObserver(
    (entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio)
      const topEntry = visible[0]
      if (!topEntry) {
        return
      }
      const anchor = topEntry.target.getAttribute('data-people-section') as PeopleAnchorId | null
      if (anchor && anchor !== props.activeAnchor) {
        emit('update:activeAnchor', anchor)
      }
    },
    {
      root: container,
      threshold: [0.2, 0.45, 0.7],
      rootMargin: '-8px 0px -55% 0px',
    },
  )

  sections.forEach((section) => observer?.observe(section))
}

watch(
  () => props.modelValue,
  (visible) => {
    if (visible) {
      void nextTick(() => {
        setupObserver()
        scrollToAnchor(props.activeAnchor)
      })
      return
    }
    observer?.disconnect()
  },
)

watch(
  () => props.activeAnchor,
  (anchor) => {
    if (!props.modelValue) {
      return
    }
    void nextTick(() => {
      scrollToAnchor(anchor)
    })
  },
)

watch(
  () => props.loading,
  (loading) => {
    if (!loading && props.modelValue) {
      void nextTick(setupObserver)
    }
  },
)

onBeforeUnmount(() => {
  observer?.disconnect()
})
</script>

<template>
  <el-drawer
    :model-value="modelValue"
    :size="960"
    destroy-on-close
    append-to-body
    class="people-detail-drawer"
    data-testid="people-detail-drawer"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <template #header>
      <div class="people-detail-drawer__header">
        <div class="people-detail-drawer__identity">
          <div class="people-detail-drawer__avatar">{{ personLabel.slice(0, 1) }}</div>
          <div>
            <div class="people-detail-drawer__name">{{ personLabel }}</div>
            <div class="people-detail-drawer__email">{{ personEmail }}</div>
          </div>
        </div>
        <div class="people-detail-drawer__header-actions">
          <el-tag :type="statusTagType" effect="plain">{{ statusLabel }}</el-tag>
          <el-button
            data-testid="people-reset-password"
            @click="emit('scroll-to-account')"
          >
            重置密码
          </el-button>
          <el-button v-if="canCreateProfile" type="primary" @click="emit('create-profile')">
            补建档案
          </el-button>
        </div>
      </div>
    </template>

    <div v-loading="loading" class="people-detail-drawer__layout">
      <PeopleAnchorNav
        :model-value="activeAnchor"
        :items="anchorItems"
        @update:model-value="emit('update:activeAnchor', $event)"
        @navigate="handleAnchorNavigate"
      />

      <div ref="scrollContainer" class="people-detail-drawer__body">
        <slot />
      </div>
    </div>
  </el-drawer>
</template>

<style scoped>
.people-detail-drawer__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.people-detail-drawer__identity {
  display: flex;
  align-items: center;
  gap: 14px;
}

.people-detail-drawer__avatar {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: linear-gradient(180deg, #dbeafe 0%, #eff6ff 100%);
  color: #1d4ed8;
  font-weight: 700;
  font-size: 18px;
}

.people-detail-drawer__name {
  font-size: 18px;
  font-weight: 600;
}

.people-detail-drawer__email {
  margin-top: 4px;
  color: var(--filum-text-secondary);
  font-size: 13px;
}

.people-detail-drawer__header-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.people-detail-drawer__layout {
  display: grid;
  grid-template-columns: 148px minmax(0, 1fr);
  gap: 20px;
  min-height: calc(100vh - 180px);
}

.people-detail-drawer__body {
  min-width: 0;
  max-height: calc(100vh - 180px);
  overflow: auto;
  padding-right: 4px;
}

:deep(.people-detail-section) {
  scroll-margin-top: 12px;
  margin-bottom: 28px;
}

:deep(.people-detail-section__title) {
  margin: 0 0 14px;
  font-size: 16px;
  font-weight: 600;
}
</style>

<style>
.people-detail-drawer.el-drawer {
  width: min(960px, 85vw) !important;
}
</style>
