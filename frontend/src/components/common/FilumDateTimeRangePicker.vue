<script setup lang="ts">
import { computed } from 'vue'

import FilumDateTimePicker from '@/components/common/FilumDateTimePicker.vue'

const model = defineModel<[Date, Date] | null>({ default: null })

const startValue = computed({
  get: () => model.value?.[0] ?? null,
  set: (value: Date | null) => {
    const end = model.value?.[1] ?? null
    if (!value && !end) {
      model.value = null
      return
    }
    model.value = [value ?? end!, end ?? value!]
  },
})

const endValue = computed({
  get: () => model.value?.[1] ?? null,
  set: (value: Date | null) => {
    const start = model.value?.[0] ?? null
    if (!value && !start) {
      model.value = null
      return
    }
    model.value = [start ?? value!, value ?? start!]
  },
})
</script>

<template>
  <div class="filum-datetime-range-picker">
    <FilumDateTimePicker v-model="startValue" placeholder="开始时间" />
    <span class="filum-datetime-range-picker__sep">至</span>
    <FilumDateTimePicker v-model="endValue" placeholder="结束时间" />
  </div>
</template>

<style scoped>
.filum-datetime-range-picker {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.filum-datetime-range-picker__sep {
  color: var(--filum-text-secondary);
  font-size: 13px;
  flex-shrink: 0;
}
</style>
