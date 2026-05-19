<script setup lang="ts">
export type PeopleAnchorId = 'account' | 'profile' | 'relations' | 'lifecycle' | 'permissions'

export type PeopleAnchorItem = {
  id: PeopleAnchorId
  label: string
  testId: string
}

defineProps<{
  modelValue: PeopleAnchorId
  items: PeopleAnchorItem[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: PeopleAnchorId]
  navigate: [id: PeopleAnchorId]
}>()

function handleClick(id: PeopleAnchorId): void {
  emit('update:modelValue', id)
  emit('navigate', id)
}
</script>

<template>
  <nav class="people-anchor-nav" aria-label="人员详情导航">
    <button
      v-for="item in items"
      :key="item.id"
      type="button"
      class="people-anchor-nav__item"
      :class="{ 'people-anchor-nav__item--active': modelValue === item.id }"
      :data-testid="item.testId"
      @click="handleClick(item.id)"
    >
      {{ item.label }}
    </button>
  </nav>
</template>

<style scoped>
.people-anchor-nav {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 132px;
  padding-right: 12px;
  border-right: 1px solid var(--filum-border-strong);
}

.people-anchor-nav__item {
  padding: 8px 12px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--filum-text-secondary);
  font-size: 13px;
  text-align: left;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}

.people-anchor-nav__item:hover {
  background: rgba(37, 99, 235, 0.06);
  color: var(--filum-text);
}

.people-anchor-nav__item--active {
  background: rgba(37, 99, 235, 0.1);
  color: var(--el-color-primary);
  font-weight: 600;
}
</style>
