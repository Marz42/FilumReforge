<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { useAttachmentPreview } from '@/composables/useAttachmentPreview'

const {
  visible,
  loading,
  errorMessage,
  activeAttachment,
  previewContent,
  closeAttachmentPreview,
} = useAttachmentPreview()

const activeXlsxSheet = ref('')

const dialogTitle = computed(() => activeAttachment.value?.original_filename ?? '附件预览')

const xlsxSheets = computed(() =>
  previewContent.value?.kind === 'xlsx' ? previewContent.value.sheets : [],
)

const activeXlsxSheetContent = computed(() => {
  if (previewContent.value?.kind !== 'xlsx') {
    return null
  }
  const sheet = previewContent.value.sheets.find((item) => item.name === activeXlsxSheet.value)
  return sheet ?? previewContent.value.sheets[0] ?? null
})

watch(
  () => previewContent.value,
  (content) => {
    if (content?.kind === 'xlsx') {
      activeXlsxSheet.value = content.sheets[0]?.name ?? ''
    } else {
      activeXlsxSheet.value = ''
    }
  },
)
</script>

<template>
  <el-dialog
    v-model="visible"
    :title="dialogTitle"
    width="860px"
    align-center
    append-to-body
    destroy-on-close
    class="attachment-preview-dialog"
    data-testid="attachment-preview-dialog"
    @closed="closeAttachmentPreview"
  >
    <div v-if="loading" class="attachment-preview-dialog__loading" data-testid="attachment-preview-loading">
      正在加载预览…
    </div>
    <el-alert
      v-else-if="errorMessage"
      type="error"
      :closable="false"
      :title="errorMessage"
      data-testid="attachment-preview-error"
    />
    <div v-else-if="previewContent" class="attachment-preview-dialog__body">
      <img
        v-if="previewContent.kind === 'image'"
        :src="previewContent.url"
        :alt="dialogTitle"
        class="attachment-preview-dialog__image"
        data-testid="attachment-preview-image"
      />
      <iframe
        v-else-if="previewContent.kind === 'pdf'"
        :src="previewContent.url"
        class="attachment-preview-dialog__pdf"
        title="PDF 预览"
        data-testid="attachment-preview-pdf"
      />
      <pre
        v-else-if="previewContent.kind === 'text'"
        class="attachment-preview-dialog__text"
        data-testid="attachment-preview-text"
      >{{ previewContent.text }}</pre>
      <div
        v-else-if="previewContent.kind === 'markdown' || previewContent.kind === 'docx'"
        class="attachment-preview-dialog__rich"
        data-testid="attachment-preview-rich"
        v-html="previewContent.kind === 'markdown' ? previewContent.html : previewContent.html"
      />
      <div v-else-if="previewContent.kind === 'xlsx'" class="attachment-preview-dialog__xlsx">
        <el-tabs v-if="xlsxSheets.length > 1" v-model="activeXlsxSheet" class="attachment-preview-dialog__xlsx-tabs">
          <el-tab-pane
            v-for="sheet in xlsxSheets"
            :key="sheet.name"
            :label="sheet.name"
            :name="sheet.name"
          />
        </el-tabs>
        <el-alert
          v-if="activeXlsxSheetContent?.truncated"
          class="attachment-preview-dialog__xlsx-warning"
          type="info"
          :closable="false"
          title="表格较大，预览仅展示前 500 行、100 列。"
        />
        <div
          class="attachment-preview-dialog__xlsx-table"
          data-testid="attachment-preview-xlsx"
        >
          <table v-if="activeXlsxSheetContent?.rows.length">
            <tbody>
              <tr v-for="(row, rowIndex) in activeXlsxSheetContent.rows" :key="rowIndex">
                <td v-for="(cell, cellIndex) in row" :key="cellIndex">{{ cell }}</td>
              </tr>
            </tbody>
          </table>
          <el-empty v-else description="工作表为空" :image-size="72" />
        </div>
      </div>
      <audio
        v-else-if="previewContent.kind === 'audio'"
        controls
        :src="previewContent.url"
        class="attachment-preview-dialog__audio"
        data-testid="attachment-preview-audio"
      />
    </div>
    <template #footer>
      <el-button @click="closeAttachmentPreview">关闭</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.attachment-preview-dialog__loading {
  padding: 48px 0;
  text-align: center;
  color: var(--el-text-color-secondary);
}

.attachment-preview-dialog__body {
  max-height: min(70vh, 720px);
  overflow: auto;
}

.attachment-preview-dialog__image {
  display: block;
  max-width: 100%;
  margin: 0 auto;
}

.attachment-preview-dialog__pdf {
  width: 100%;
  min-height: 480px;
  border: none;
}

.attachment-preview-dialog__text {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 13px;
  line-height: 1.6;
}

.attachment-preview-dialog__rich :deep(h1),
.attachment-preview-dialog__rich :deep(h2),
.attachment-preview-dialog__rich :deep(h3),
.attachment-preview-dialog__rich :deep(p),
.attachment-preview-dialog__rich :deep(ul),
.attachment-preview-dialog__rich :deep(ol) {
  margin: 0 0 12px;
}

.attachment-preview-dialog__rich :deep(table) {
  width: 100%;
  border-collapse: collapse;
}

.attachment-preview-dialog__rich :deep(th),
.attachment-preview-dialog__rich :deep(td) {
  border: 1px solid var(--el-border-color);
  padding: 6px 8px;
}

.attachment-preview-dialog__xlsx-table :deep(table) {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.attachment-preview-dialog__xlsx-warning {
  margin-bottom: 12px;
}

.attachment-preview-dialog__xlsx-table :deep(th),
.attachment-preview-dialog__xlsx-table :deep(td) {
  border: 1px solid var(--el-border-color);
  padding: 6px 8px;
  white-space: nowrap;
}

.attachment-preview-dialog__audio {
  display: block;
  width: 100%;
}
</style>
