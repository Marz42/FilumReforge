<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import {
  cloneRecord,
  extraRecordKeys,
  formatRecordValue,
  listedDefinitionKeys,
  parseRecordObject,
  parseRecordValue,
  type RecordFieldDefinition,
} from '@/utils/recordFields'

const props = withDefaults(
  defineProps<{
    modelValue: Record<string, unknown>
    definitions?: RecordFieldDefinition[]
    storageTarget?: string
    addLabel?: string
    advancedLabel?: string
  }>(),
  {
    definitions: () => [],
    addLabel: '添加字段',
    advancedLabel: '高级 JSON',
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: Record<string, unknown>]
}>()

const advancedOpen = ref(false)
const advancedText = ref('{}')
const extraDraftKey = ref('')
const extraDraftValue = ref('')

const activeDefinitions = computed(() =>
  props.definitions.filter((item) => item.is_active !== false).filter((item) => {
    if (!props.storageTarget) {
      return true
    }
    return item.storage_target === props.storageTarget
  }),
)

const extraKeys = computed(() => extraRecordKeys(props.modelValue, props.definitions, props.storageTarget))

watch(
  () => props.modelValue,
  (value) => {
    if (advancedOpen.value) {
      advancedText.value = JSON.stringify(value, null, 2)
    }
  },
  { deep: true },
)

function emitRecord(next: Record<string, unknown>): void {
  emit('update:modelValue', next)
}

function updateDefinedField(fieldKey: string, fieldType: string, text: string): void {
  emitRecord({
    ...cloneRecord(props.modelValue),
    [fieldKey]: parseRecordValue(text, fieldType),
  })
}

function updateExtraValue(fieldKey: string, text: string): void {
  emitRecord({
    ...cloneRecord(props.modelValue),
    [fieldKey]: parseRecordValue(text),
  })
}

function removeExtraKey(fieldKey: string): void {
  const next = cloneRecord(props.modelValue)
  delete next[fieldKey]
  emitRecord(next)
}

function addExtraField(): void {
  const key = extraDraftKey.value.trim()
  if (!key) {
    ElMessage.warning('请填写字段名')
    return
  }
  const known = new Set([
    ...listedDefinitionKeys(props.definitions, props.storageTarget),
    ...Object.keys(props.modelValue),
  ])
  if (known.has(key)) {
    ElMessage.warning('字段已存在')
    return
  }
  emitRecord({
    ...cloneRecord(props.modelValue),
    [key]: parseRecordValue(extraDraftValue.value),
  })
  extraDraftKey.value = ''
  extraDraftValue.value = ''
}

function openAdvanced(): void {
  advancedOpen.value = true
  advancedText.value = JSON.stringify(props.modelValue, null, 2)
}

function applyAdvanced(): void {
  try {
    emitRecord(parseRecordObject(advancedText.value))
    ElMessage.success('已应用 JSON')
  } catch {
    ElMessage.error('需要是合法 JSON 对象')
  }
}
</script>

<template>
  <div class="record-fields-editor">
    <div
      v-for="definition in activeDefinitions"
      :key="definition.field_key"
      class="record-fields-editor__field"
    >
      <label class="record-fields-editor__label">{{ definition.label }}</label>
      <el-date-picker
        v-if="definition.field_type === 'date'"
        :model-value="formatRecordValue(modelValue[definition.field_key])"
        type="date"
        value-format="YYYY-MM-DD"
        @update:model-value="(value) => updateDefinedField(definition.field_key, definition.field_type, String(value ?? ''))"
      />
      <el-input
        v-else-if="definition.field_type === 'text'"
        :model-value="formatRecordValue(modelValue[definition.field_key])"
        type="textarea"
        :rows="3"
        @update:model-value="(value) => updateDefinedField(definition.field_key, definition.field_type, value)"
      />
      <el-input
        v-else
        :model-value="formatRecordValue(modelValue[definition.field_key])"
        :type="definition.field_type === 'number' ? 'number' : 'text'"
        @update:model-value="(value) => updateDefinedField(definition.field_key, definition.field_type, value)"
      />
    </div>

    <div v-if="extraKeys.length" class="record-fields-editor__extras">
      <div v-for="key in extraKeys" :key="key" class="record-fields-editor__extra-row">
        <el-input :model-value="key" disabled />
        <el-input
          :model-value="formatRecordValue(modelValue[key])"
          type="textarea"
          :rows="2"
          @update:model-value="(value) => updateExtraValue(key, value)"
        />
        <el-button link type="danger" @click="removeExtraKey(key)">删除</el-button>
      </div>
    </div>

    <div class="record-fields-editor__add">
      <el-input v-model="extraDraftKey" placeholder="字段名" />
      <el-input v-model="extraDraftValue" placeholder="值（文本或 JSON）" />
      <el-button @click="addExtraField">{{ addLabel }}</el-button>
    </div>

    <div class="record-fields-editor__advanced">
      <el-button link type="primary" data-testid="record-fields-advanced-toggle" @click="openAdvanced">
        {{ advancedLabel }}
      </el-button>
      <template v-if="advancedOpen">
        <el-input v-model="advancedText" type="textarea" :rows="8" data-testid="record-fields-advanced-json" />
        <el-button data-testid="record-fields-advanced-apply" @click="applyAdvanced">应用 JSON</el-button>
      </template>
    </div>
  </div>
</template>

<style scoped>
.record-fields-editor {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
}

.record-fields-editor__field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.record-fields-editor__label {
  color: var(--el-text-color-regular);
  font-size: 13px;
}

.record-fields-editor__extras,
.record-fields-editor__add {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.record-fields-editor__extra-row,
.record-fields-editor__add {
  display: grid;
  grid-template-columns: minmax(120px, 160px) 1fr auto;
  gap: 8px;
  align-items: start;
}

.record-fields-editor__advanced {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
}
</style>
