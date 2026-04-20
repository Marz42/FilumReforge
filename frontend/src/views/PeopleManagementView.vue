<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import ProfilesView from '@/views/ProfilesView.vue'
import UsersView from '@/views/UsersView.vue'

type PeopleTab = 'profiles' | 'users'

const route = useRoute()
const router = useRouter()

const activeTab = computed<PeopleTab>(() => {
  return route.query.tab === 'users' ? 'users' : 'profiles'
})

const currentView = computed(() => {
  return activeTab.value === 'users' ? UsersView : ProfilesView
})

function handleTabChange(value: string): void {
  const nextTab: PeopleTab = value === 'users' ? 'users' : 'profiles'
  void router.replace({
    name: 'people',
    query: {
      tab: nextTab,
    },
  })
}
</script>

<template>
  <div class="people-management-view">
    <el-card shadow="never">
      <el-tabs :model-value="activeTab" @update:model-value="handleTabChange">
        <el-tab-pane label="档案管理" name="profiles" />
        <el-tab-pane label="用户账号" name="users" />
      </el-tabs>
    </el-card>

    <component :is="currentView" />
  </div>
</template>

<style scoped>
.people-management-view {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
</style>
