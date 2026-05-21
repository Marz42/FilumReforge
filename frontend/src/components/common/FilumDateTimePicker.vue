<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import {
  FIVE_MINUTE_MINUTE_OPTIONS,
  HOUR_OPTIONS,
  mergeDateAndTime,
  parseDateTimeParts,
} from '@/utils/dateTimePicker'

const model = defineModel<Date | null>({ default: null })

const props = withDefaults(
  defineProps<{
    placeholder?: string
    disabled?: boolean
  }>(),
  {
    placeholder: '可选',
    disabled: false,
  },
)

const datePart = ref('')
const hourPart = ref('')
const minutePart = ref('')

const hourOptions = HOUR_OPTIONS
const minuteOptions = FIVE_MINUTE_MINUTE_OPTIONS

function syncFromModel(value: Date | null): void {
  const parts = parseDateTimeParts(value)
  datePart.value = parts.date
  hourPart.value = parts.hour
  minutePart.value = parts.minute
}

function emitMerged(): void {
  model.value = mergeDateAndTime(datePart.value, hourPart.value, minutePart.value)
}

watch(
  () => model.value,
  (value) => {
    syncFromModel(value)
  },
  { immediate: true },
)

watch([datePart, hourPart, minutePart], () => {
  emitMerged()
})

const showTimeSelects = computed(() => Boolean(datePart.value))
</script>

<template>
  <div class="filum-datetime-picker" :class="{ 'is-disabled': disabled }">
    <el-date-picker
      v-model="datePart"
      type="date"
      value-format="YYYY-MM-DD"
      placeholder="选择日期"
      class="filum-datetime-picker__date"
      :disabled="disabled"
      teleported
    />
    <template v-if="showTimeSelects">
      <el-select
        v-model="hourPart"
        class="filum-datetime-picker__hour"
        placeholder="时"
        :disabled="disabled"
        filterable
        teleported
      >
        <el-option v-for="option in hourOptions" :key="option" :label="option" :value="option" />
      </el-select>
      <span class="filum-datetime-picker__colon">:</span>
      <el-select
        v-model="minutePart"
        class="filum-datetime-picker__minute"
        placeholder="分"
        :disabled="disabled"
        filterable
        teleported
      >
        <el-option v-for="option in minuteOptions" :key="option" :label="option" :value="option" />
      </el-select>
    </template>
    <span v-else class="filum-datetime-picker__hint">{{ placeholder }}</span>
  </div>
</template>

<style scoped>
.filum-datetime-picker {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.filum-datetime-picker__date {
  flex: 1;
  min-width: 0;
}

.filum-datetime-picker__hour,
.filum-datetime-picker__minute {
  width: 88px;
}

.filum-datetime-picker__colon {
  color: var(--filum-text-secondary);
  font-size: 14px;
}

.filum-datetime-picker__hint {
  color: var(--filum-text-muted);
  font-size: 13px;
}

.filum-datetime-picker.is-disabled {
  opacity: 0.7;
}
</style>
