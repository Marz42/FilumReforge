<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, type UploadFile } from 'element-plus'

import { uploadAttachment } from '@/api/attachments'
import {
  archiveDocument,
  createDocument,
  getDocument,
  listDocuments,
  publishDocument,
  searchDocuments,
  updateDocument,
} from '@/api/documents'
import { queryKnowledge } from '@/api/knowledge'
import { useAuthStore } from '@/stores/auth'
import type {
  Document,
  DocumentCategory,
  DocumentSearchHit,
  DocumentStatus,
  DocumentSummary,
  KnowledgeQueryResult,
} from '@/types/api'
import { getErrorMessage } from '@/utils/errors'
import { formatDateTime } from '@/utils/formatters'

const authStore = useAuthStore()
const loading = ref(false)
const dialogVisible = ref(false)
const saving = ref(false)
const attachmentUploading = ref(false)
const documents = ref<DocumentSummary[]>([])
const selectedDocument = ref<Document | null>(null)
const selectedDocumentId = ref('')
const semanticHits = ref<DocumentSearchHit[]>([])
const knowledgeResult = ref<KnowledgeQueryResult | null>(null)
const listQuery = ref('')
const semanticQuery = ref('')
const ragQuery = ref('')
const selectedAttachmentFile = ref<File | null>(null)

const categoryLabelMap: Record<DocumentCategory, string> = {
  policy: '制度',
  sop: 'SOP',
  announcement: '公告',
  faq: 'FAQ',
  other: '其他',
}

const statusTagTypeMap: Record<DocumentStatus, '' | 'info' | 'success' | 'warning'> = {
  draft: 'info',
  published: 'success',
  archived: 'warning',
}

const form = reactive({
  documentId: '',
  title: '',
  slug: '',
  category: 'sop' as DocumentCategory,
  status: 'draft' as DocumentStatus,
  content_md: '',
})

const isEditing = computed(() => Boolean(form.documentId))

function categoryLabel(category: DocumentCategory): string {
  return categoryLabelMap[category]
}

function resetForm(): void {
  form.documentId = ''
  form.title = ''
  form.slug = ''
  form.category = 'sop'
  form.status = 'draft'
  form.content_md = ''
}

async function loadDocuments(query?: string): Promise<void> {
  loading.value = true
  try {
    documents.value = await listDocuments(query ? { query } : {})
    const fallbackId = documents.value[0]?.id ?? ''
    if (!documents.value.some((item) => item.id === selectedDocumentId.value)) {
      selectedDocumentId.value = fallbackId
    }

    if (selectedDocumentId.value) {
      selectedDocument.value = await getDocument(selectedDocumentId.value)
    } else {
      selectedDocument.value = null
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

async function handleDocumentSelect(documentId: string): Promise<void> {
  selectedDocumentId.value = documentId
  try {
    selectedDocument.value = await getDocument(documentId)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  }
}

function openCreateDialog(): void {
  resetForm()
  dialogVisible.value = true
}

function openEditDialog(): void {
  if (!selectedDocument.value) {
    ElMessage.warning('请先选择知识文档')
    return
  }

  form.documentId = selectedDocument.value.id
  form.title = selectedDocument.value.title
  form.slug = selectedDocument.value.slug
  form.category = selectedDocument.value.category
  form.status = selectedDocument.value.status
  form.content_md = selectedDocument.value.content_md
  dialogVisible.value = true
}

async function handleSaveDocument(): Promise<void> {
  saving.value = true
  try {
    const wasEditing = isEditing.value
    const payload = {
      title: form.title.trim(),
      slug: form.slug.trim() || null,
      category: form.category,
      content_md: form.content_md.trim(),
    }

    const document = isEditing.value
      ? await updateDocument(form.documentId, payload)
      : await createDocument({
          ...payload,
          status: form.status,
        })

    dialogVisible.value = false
    resetForm()
    await loadDocuments(listQuery.value.trim() || undefined)
    await handleDocumentSelect(document.id)
    ElMessage.success(wasEditing ? '知识文档已更新' : '知识文档已创建')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    saving.value = false
  }
}

async function handlePublishDocument(): Promise<void> {
  if (!selectedDocument.value) {
    ElMessage.warning('请先选择知识文档')
    return
  }

  try {
    selectedDocument.value = await publishDocument(selectedDocument.value.id)
    await loadDocuments(listQuery.value.trim() || undefined)
    ElMessage.success('知识文档已发布')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  }
}

async function handleArchiveDocument(): Promise<void> {
  if (!selectedDocument.value) {
    ElMessage.warning('请先选择知识文档')
    return
  }

  try {
    selectedDocument.value = await archiveDocument(selectedDocument.value.id)
    await loadDocuments(listQuery.value.trim() || undefined)
    ElMessage.success('知识文档已归档')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  }
}

function handleAttachmentChange(uploadFile: UploadFile): void {
  selectedAttachmentFile.value = uploadFile.raw ?? null
}

async function handleUploadAttachment(): Promise<void> {
  if (!selectedDocument.value || !selectedAttachmentFile.value) {
    ElMessage.warning('请选择文档和附件')
    return
  }

  attachmentUploading.value = true
  try {
    await uploadAttachment({
      target_type: 'document',
      target_id: selectedDocument.value.id,
      file: selectedAttachmentFile.value,
      visibility: 'internal',
      relation: 'reference',
    })
    selectedAttachmentFile.value = null
    selectedDocument.value = await getDocument(selectedDocument.value.id)
    ElMessage.success('文档附件已上传')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    attachmentUploading.value = false
  }
}

async function handleSemanticSearch(): Promise<void> {
  if (!semanticQuery.value.trim()) {
    ElMessage.warning('请输入检索关键词')
    return
  }

  try {
    const response = await searchDocuments({
      query: semanticQuery.value.trim(),
      limit: 5,
    })
    semanticHits.value = response.items
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  }
}

async function handleKnowledgeQuery(): Promise<void> {
  if (!ragQuery.value.trim()) {
    ElMessage.warning('请输入知识问题')
    return
  }

  try {
    knowledgeResult.value = await queryKnowledge({
      query: ragQuery.value.trim(),
      limit: 4,
    })
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  }
}

onMounted(() => {
  void loadDocuments()
})

defineExpose({
  form,
  handleSaveDocument,
  handleSemanticSearch,
  openEditDialog,
  semanticQuery,
})
</script>

<template>
  <div class="knowledge-page">
    <el-row :gutter="20">
      <el-col :xs="24" :xl="8">
        <el-card shadow="never" v-loading="loading">
          <template #header>
            <div class="knowledge-page__card-header">
              <span>知识库文档</span>
              <el-button
                v-if="authStore.isManagementRole"
                size="small"
                type="primary"
                @click="openCreateDialog"
              >
                新建文档
              </el-button>
            </div>
          </template>

          <div class="knowledge-page__toolbar">
            <el-input
              id="knowledge-list-query"
              v-model="listQuery"
              clearable
              placeholder="按标题 / slug / 内容过滤"
            />
            <el-button @click="loadDocuments(listQuery.trim() || undefined)">筛选</el-button>
          </div>

          <el-table
            :data="documents"
            highlight-current-row
            @row-click="(row: DocumentSummary) => handleDocumentSelect(row.id)"
          >
            <el-table-column prop="title" label="标题" min-width="180" />
            <el-table-column label="分类" width="100">
              <template #default="{ row }: { row: DocumentSummary }">
                {{ categoryLabel(row.category) }}
              </template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }: { row: DocumentSummary }">
                <el-tag :type="statusTagTypeMap[row.status]" effect="plain">
                  {{ row.status }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <el-col :xs="24" :xl="16">
        <el-card shadow="never" class="knowledge-page__detail">
          <template #header>
            <div class="knowledge-page__card-header">
              <span>{{ selectedDocument?.title ?? '文档详情' }}</span>
              <el-space v-if="selectedDocument && authStore.isManagementRole">
                <el-button size="small" @click="openEditDialog">编辑</el-button>
                <el-button
                  v-if="selectedDocument.status !== 'published'"
                  size="small"
                  type="success"
                  @click="handlePublishDocument"
                >
                  发布
                </el-button>
                <el-button
                  v-if="selectedDocument.status !== 'archived'"
                  size="small"
                  type="warning"
                  @click="handleArchiveDocument"
                >
                  归档
                </el-button>
              </el-space>
            </div>
          </template>

          <template v-if="selectedDocument">
            <el-descriptions :column="2" border>
              <el-descriptions-item label="Slug">{{ selectedDocument.slug }}</el-descriptions-item>
              <el-descriptions-item label="分类">
                {{ categoryLabel(selectedDocument.category) }}
              </el-descriptions-item>
              <el-descriptions-item label="状态">{{ selectedDocument.status }}</el-descriptions-item>
              <el-descriptions-item label="版本">v{{ selectedDocument.version }}</el-descriptions-item>
              <el-descriptions-item label="作者">
                {{ selectedDocument.author_email ?? selectedDocument.author_id }}
              </el-descriptions-item>
              <el-descriptions-item label="更新时间">
                {{ formatDateTime(selectedDocument.updated_at) }}
              </el-descriptions-item>
            </el-descriptions>

            <el-divider>正文</el-divider>
            <pre class="knowledge-page__markdown">{{ selectedDocument.content_md }}</pre>

            <el-divider>附件</el-divider>
            <el-empty
              v-if="selectedDocument.attachments.length === 0"
              description="暂无文档附件"
            />
            <el-space v-else wrap>
              <el-link
                v-for="attachment in selectedDocument.attachments"
                :key="attachment.id"
                :href="attachment.download_url ?? undefined"
                target="_blank"
                type="primary"
              >
                {{ attachment.original_filename }}
              </el-link>
            </el-space>

            <div
              v-if="authStore.isManagementRole"
              class="knowledge-page__attachment-upload"
            >
              <el-upload :auto-upload="false" :limit="1" :on-change="handleAttachmentChange">
                <template #trigger>
                  <el-button plain>选择附件</el-button>
                </template>
              </el-upload>
              <el-button
                type="primary"
                :loading="attachmentUploading"
                @click="handleUploadAttachment"
              >
                上传附件
              </el-button>
            </div>
          </template>

          <el-empty v-else description="请选择左侧文档查看详情" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20">
      <el-col :xs="24" :xl="12">
        <el-card shadow="never">
          <template #header>
            <span>语义检索</span>
          </template>

          <div class="knowledge-page__toolbar">
            <el-input
              id="knowledge-semantic-query"
              v-model="semanticQuery"
              clearable
              placeholder="例如：入职流程 / 采购审批"
            />
            <el-button type="primary" @click="handleSemanticSearch">检索</el-button>
          </div>

          <el-empty v-if="semanticHits.length === 0" description="暂无检索结果" />
          <el-timeline v-else>
            <el-timeline-item
              v-for="item in semanticHits"
              :key="`${item.document_id}-${item.chunk_index}`"
            >
              <strong>{{ item.title }}</strong>
              <p>{{ item.excerpt }}</p>
            </el-timeline-item>
          </el-timeline>
        </el-card>
      </el-col>

      <el-col :xs="24" :xl="12">
        <el-card shadow="never">
          <template #header>
            <span>RAG 问答上下文</span>
          </template>

          <div class="knowledge-page__toolbar">
            <el-input
              v-model="ragQuery"
              clearable
              placeholder="例如：@系统 入职需要准备什么材料？"
            />
            <el-button type="primary" @click="handleKnowledgeQuery">生成上下文</el-button>
          </div>

          <el-empty v-if="!knowledgeResult" description="尚未生成上下文" />
          <template v-else>
            <pre class="knowledge-page__markdown">{{ knowledgeResult.context }}</pre>
            <el-divider>命中文档</el-divider>
            <el-space wrap>
              <el-tag
                v-for="item in knowledgeResult.hits"
                :key="`${item.document_id}-${item.chunk_index}`"
                effect="plain"
              >
                {{ item.title }}
              </el-tag>
            </el-space>
          </template>
        </el-card>
      </el-col>
    </el-row>

    <el-dialog
      v-model="dialogVisible"
      :title="isEditing ? '编辑知识文档' : '新建知识文档'"
      width="720px"
    >
      <el-form label-position="top">
        <el-form-item label="标题">
          <el-input id="knowledge-form-title" v-model="form.title" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="Slug">
              <el-input v-model="form.slug" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="分类">
              <el-select v-model="form.category">
                <el-option
                  v-for="item in Object.entries(categoryLabelMap)"
                  :key="item[0]"
                  :label="item[1]"
                  :value="item[0]"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item v-if="!isEditing" label="初始状态">
          <el-radio-group v-model="form.status">
            <el-radio-button label="draft">draft</el-radio-button>
            <el-radio-button label="published">published</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="Markdown 正文">
          <el-input v-model="form.content_md" type="textarea" :rows="12" resize="vertical" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button
          data-testid="knowledge-save-button"
          type="primary"
          :loading="saving"
          @click="handleSaveDocument"
        >
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.knowledge-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.knowledge-page__card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.knowledge-page__toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.knowledge-page__detail {
  min-height: 100%;
}

.knowledge-page__markdown {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  line-height: 1.7;
}

.knowledge-page__attachment-upload {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 16px;
}
</style>
