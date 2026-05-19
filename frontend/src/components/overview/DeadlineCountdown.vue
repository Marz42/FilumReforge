<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { getOverview } from '@/api/overview'
import type { OverviewTaskInboxEntry, OverviewTaskTrackingEntry } from '@/types/api'

type DeadlineTask = OverviewTaskInboxEntry | OverviewTaskTrackingEntry

const router = useRouter()
const nearestTask = ref<DeadlineTask | null>(null)
const remainingMs = ref(0)
let tickTimer: ReturnType<typeof setInterval> | null = null

const visible = computed(() => nearestTask.value !== null && remainingMs.value > 0)

const countdownLabel = computed(() => {
  const totalSeconds = Math.max(0, Math.floor(remainingMs.value / 1000))
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
})

function pickNearestDeadline(
  inbox: OverviewTaskInboxEntry[],
  tracking: OverviewTaskTrackingEntry[],
): DeadlineTask | null {
  const now = Date.now()
  const candidates = [...inbox, ...tracking].filter(
    (task) => task.due_date && new Date(task.due_date).getTime() > now,
  )
  candidates.sort(
    (left, right) => new Date(left.due_date!).getTime() - new Date(right.due_date!).getTime(),
  )
  return candidates[0] ?? null
}

function refreshRemaining(): void {
  if (!nearestTask.value?.due_date) {
    remainingMs.value = 0
    return
  }
  remainingMs.value = new Date(nearestTask.value.due_date).getTime() - Date.now()
  if (remainingMs.value <= 0) {
    nearestTask.value = null
  }
}

async function loadNearestDeadline(): Promise<void> {
  try {
    const snapshot = await getOverview()
    nearestTask.value = pickNearestDeadline(snapshot.task_inbox, snapshot.task_tracking)
    refreshRemaining()
  } catch {
    nearestTask.value = null
    remainingMs.value = 0
  }
}

function handleClick(): void {
  if (!nearestTask.value) {
    return
  }
  void router.push({
    name: 'task-center',
    query: {
      filter: 'tracking',
      selected: nearestTask.value.task_id,
    },
  })
}

onMounted(() => {
  void loadNearestDeadline()
  tickTimer = setInterval(() => {
    refreshRemaining()
  }, 1000)
})

onBeforeUnmount(() => {
  if (tickTimer) {
    clearInterval(tickTimer)
  }
})
</script>

<template>
  <button
    v-if="visible && nearestTask"
    type="button"
    class="deadline-countdown"
    data-testid="header-deadline-countdown"
    @click="handleClick"
  >
    距「{{ nearestTask.title }}」截止 {{ countdownLabel }}
  </button>
</template>

<style scoped>
.deadline-countdown {
  max-width: 320px;
  padding: 6px 12px;
  border: 1px solid rgba(91, 110, 245, 0.22);
  border-radius: 999px;
  background: linear-gradient(180deg, #f8faff 0%, #eef2ff 100%);
  color: var(--el-color-primary);
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease;
}

.deadline-countdown:hover {
  border-color: var(--el-color-primary-light-5);
  box-shadow: 0 6px 16px rgba(91, 110, 245, 0.12);
}
</style>
