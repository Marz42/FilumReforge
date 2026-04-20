import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/ai', () => ({
  routeAICommand: vi.fn(),
}))

import { routeAICommand } from '@/api/ai'
import CommandBar from '@/components/CommandBar.vue'

describe('Command bar', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(routeAICommand)
      .mockResolvedValueOnce({
        mode: 'slash_command',
        prompt: '/profile',
        reply_text: '档案摘要：管理员',
        command_name: 'profile',
        tool_results: [],
        knowledge_hits: [],
      })
      .mockResolvedValueOnce({
        mode: 'mention',
        prompt: '入职流程是什么？',
        reply_text: '根据知识库，入职流程需要先提交材料，再开通账号。',
        command_name: null,
        tool_results: [],
        knowledge_hits: [
          {
            document_id: 'doc-1',
            title: '员工入职 SOP',
            slug: 'employee-onboarding-sop',
            category: 'sop',
            status: 'published',
            score: 0.99,
            chunk_index: 0,
            excerpt: '入职流程需要先提交材料，再开通账号。',
          },
        ],
      })
  })

  it('submits slash and mention commands', async () => {
    const wrapper = mount(CommandBar, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          teleport: true,
        },
      },
    })

    const vm = wrapper.vm as unknown as {
      handleSubmit: () => Promise<void>
      inputText: string
      openDialog: (value?: string) => void
      result: {
        reply_text: string
        knowledge_hits: Array<{ title: string }>
      } | null
    }

    vm.openDialog('/profile')
    await flushPromises()

    vm.inputText = '/profile'
    await vm.handleSubmit()
    await flushPromises()

    expect(routeAICommand).toHaveBeenCalledWith('/profile')
    expect(vm.result?.reply_text).toContain('档案摘要：管理员')

    vm.inputText = '@系统 入职流程是什么？'
    await vm.handleSubmit()
    await flushPromises()

    expect(routeAICommand).toHaveBeenCalledWith('@系统 入职流程是什么？')
    expect(vm.result?.knowledge_hits[0]?.title).toBe('员工入职 SOP')
  })
})
