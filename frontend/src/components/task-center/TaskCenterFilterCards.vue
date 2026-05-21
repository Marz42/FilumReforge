<script setup lang="ts">
export type TaskCenterFilter = 'inbox' | 'tracking' | 'history'

const props = defineProps<{
  activeFilter: TaskCenterFilter
  counts: {
    inbox: number
    tracking: number
    history: number
  }
}>()

const emit = defineEmits<{
  change: [filter: TaskCenterFilter]
}>()

const cards: Array<{
  filter: TaskCenterFilter
  title: string
  description: string
  buttonLabel: string
  testId: string
  count: () => number
}> = [
  {
    filter: 'inbox',
    title: '待处理',
    description: '流转到当前用户、需你处理或确认的任务',
    buttonLabel: '待处理',
    testId: 'task-filter-inbox',
    count: () => props.counts.inbox,
  },
  {
    filter: 'tracking',
    title: '任务跟踪',
    description: '你参与但当前未流转到你手上的流程',
    buttonLabel: '任务跟踪',
    testId: 'task-filter-tracking',
    count: () => props.counts.tracking,
  },
  {
    filter: 'history',
    title: '历史任务',
    description: '你参与且流程已全部结束的任务',
    buttonLabel: '历史任务',
    testId: 'task-filter-history',
    count: () => props.counts.history,
  },
]

function handleSelect(filter: TaskCenterFilter): void {
  emit('change', filter)
}
</script>

<template>
  <div class="task-center-filter-cards" data-testid="task-center-filter-cards">
    <article
      v-for="card in cards"
      :key="card.filter"
      class="task-center-filter-cards__card"
      :class="{ 'task-center-filter-cards__card--active': activeFilter === card.filter }"
      @click="handleSelect(card.filter)"
    >
      <div class="task-center-filter-cards__card-head">
        <div>
          <h3 class="task-center-filter-cards__title">{{ card.title }}</h3>
          <p class="task-center-filter-cards__description">{{ card.description }}</p>
        </div>
        <el-badge :value="card.count()" :max="99" type="primary" />
      </div>
      <el-button
        :type="activeFilter === card.filter ? 'primary' : 'default'"
        size="small"
        :data-testid="card.testId"
        @click.stop="handleSelect(card.filter)"
      >
        {{ card.buttonLabel }}
      </el-button>
    </article>
  </div>
</template>

<style scoped>
.task-center-filter-cards {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-top: 16px;
}

.task-center-filter-cards__card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  border: 1px solid var(--filum-border-strong);
  border-radius: 12px;
  background: linear-gradient(180deg, #ffffff 0%, #f8faff 100%);
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease;
}

.task-center-filter-cards__card--active {
  border-color: var(--el-color-primary);
}

.task-center-filter-cards__card:hover {
  border-color: var(--el-color-primary-light-5);
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.06);
}

.task-center-filter-cards__card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.task-center-filter-cards__title {
  margin: 0;
  font-size: 16px;
  color: var(--filum-text);
}

.task-center-filter-cards__description {
  margin: 6px 0 0;
  color: var(--filum-text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

@media (max-width: 960px) {
  .task-center-filter-cards {
    grid-template-columns: 1fr;
  }
}
</style>
