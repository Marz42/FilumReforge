import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/documents', () => ({
  archiveDocument: vi.fn(),
  createDocument: vi.fn(),
  getDocument: vi.fn(),
  listDocuments: vi.fn(),
  publishDocument: vi.fn(),
  searchDocuments: vi.fn(),
  updateDocument: vi.fn(),
}))

vi.mock('@/api/knowledge', () => ({
  queryKnowledge: vi.fn(),
}))

vi.mock('@/api/attachments', () => ({
  uploadAttachment: vi.fn(),
}))

import {
  getDocument,
  listDocuments,
  publishDocument,
  searchDocuments,
  updateDocument,
} from '@/api/documents'
import { queryKnowledge } from '@/api/knowledge'
import { useAuthStore } from '@/stores/auth'
import KnowledgeBaseView from '@/views/KnowledgeBaseView.vue'

const documentSummary = {
  id: 'doc-1',
  title: '员工入职 SOP',
  slug: 'employee-onboarding-sop',
  category: 'sop',
  status: 'draft',
  author_id: 'user-1',
  version: 1,
  published_at: null,
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
  author_email: 'admin@example.com',
} as const

const documentDetail = {
  ...documentSummary,
  content_md: '入职流程需要先提交材料，再开通账号。',
  attachments: [],
}

describe('Knowledge base view', () => {
  beforeEach(() => {
    window.localStorage.clear()
    setActivePinia(createPinia())
    vi.clearAllMocks()

    const authStore = useAuthStore()
    authStore.initialized = true
    authStore.accessToken = 'token'
    authStore.user = {
      id: 'user-1',
      email: 'admin@example.com',
      role: 'admin',
      status: 'active',
      last_login_at: null,
      created_at: '2025-01-01T00:00:00Z',
      updated_at: '2025-01-01T00:00:00Z',
    }

    vi.mocked(listDocuments).mockResolvedValue([documentSummary])
    vi.mocked(getDocument).mockResolvedValue(documentDetail)
    vi.mocked(updateDocument).mockResolvedValue({
      ...documentDetail,
      title: '员工入职 SOP（修订）',
    })
    vi.mocked(publishDocument).mockResolvedValue({
      ...documentDetail,
      status: 'published',
      published_at: '2025-01-01T01:00:00Z',
    })
    vi.mocked(searchDocuments).mockResolvedValue({
      query: '入职流程',
      items: [
        {
          document_id: 'doc-1',
          title: '员工入职 SOP',
          slug: 'employee-onboarding-sop',
          category: 'sop',
          status: 'published',
          score: 0.98,
          chunk_index: 0,
          excerpt: '入职流程需要先提交材料，再开通账号。',
        },
      ],
    })
    vi.mocked(queryKnowledge).mockResolvedValue({
      query: '入职流程',
      context: '员工入职 SOP\n入职流程需要先提交材料，再开通账号。',
      hits: [],
    })
  })

  it('renders documents, updates content, and publishes documents', async () => {
    const wrapper = mount(KnowledgeBaseView, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          teleport: true,
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as unknown as {
      form: {
        title: string
      }
      handleSaveDocument: () => Promise<void>
      handleSemanticSearch: () => Promise<void>
      openEditDialog: () => void
      semanticQuery: string
    }

    expect(wrapper.text()).toContain('员工入职 SOP')

    vm.openEditDialog()
    await flushPromises()

    vm.form.title = '员工入职 SOP（修订）'
    await vm.handleSaveDocument()
    await flushPromises()

    expect(updateDocument).toHaveBeenCalled()

    await wrapper.findAll('button').find((button) => button.text() === '发布')?.trigger('click')
    await flushPromises()

    expect(publishDocument).toHaveBeenCalledWith('doc-1')

    vm.semanticQuery = '入职流程'
    await vm.handleSemanticSearch()
    await flushPromises()

    expect(searchDocuments).toHaveBeenCalledWith({
      query: '入职流程',
      limit: 5,
    })
  })
})
