import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus, { ElMessageBox } from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/workflow-operations', () => ({
  getWorkflowOperationsDashboard: vi.fn(),
  operateWorkflowNode: vi.fn(),
  replayWorkflowOutbox: vi.fn(),
  searchWorkflowTraces: vi.fn(),
  updateWorkflowIncident: vi.fn(),
}))

import {
  getWorkflowOperationsDashboard,
  replayWorkflowOutbox,
  searchWorkflowTraces,
} from '@/api/workflow-operations'
import WorkflowOperationsView from '@/views/WorkflowOperationsView.vue'

describe('Workflow operations view', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.mocked(getWorkflowOperationsDashboard).mockResolvedValue({
      generated_at: '2026-08-12T10:00:00Z',
      stalled_minutes: 30,
      metrics: {
        runs: { active: 3, failed: 1 },
        stalled_run_count: 1,
        suspended_node_count: 1,
        join_wait_count: 2,
        oldest_join_wait_seconds: 900,
        outbox: { pending: 0, retrying: 0, dispatched: 12, failed: 1 },
        outbox_backlog_count: 1,
        oldest_outbox_backlog_seconds: 3600,
        projection_failed_stream_count: 1,
      },
      projection_streams: [
        {
          stream_name: 'workflow_run_events',
          status: 'failed',
          processed_count: 12,
          source_count: 14,
          backlog_count: 2,
          lag_seconds: 65,
          last_success_at: '2026-08-12T09:58:00Z',
          last_error: 'projector stopped',
          sampled_at: '2026-08-12T10:00:00Z',
        },
      ],
      shadow: null,
      issues: [
        {
          category: 'no_route',
          severity: 'error',
          instance_id: 'run-1',
          node_instance_id: null,
          title: '流程无可用路径',
          message: '没有匹配路径',
          age_seconds: 120,
        },
      ],
      failed_outbox: [
        {
          id: 'outbox-1',
          instance_id: 'run-1',
          node_instance_id: 'node-1',
          event_type: 'node_activated',
          status: 'failed',
          attempt_count: 5,
          available_at: '2026-08-12T09:00:00Z',
          last_error: 'delivery failed',
          manual_replay_count: 0,
          last_replayed_at: null,
          last_replayed_by_user_id: null,
          last_replay_reason: null,
          updated_at: '2026-08-12T09:00:00Z',
        },
      ],
      incidents: [],
    })
    vi.mocked(searchWorkflowTraces).mockResolvedValue({ items: [] })
    vi.mocked(replayWorkflowOutbox).mockResolvedValue({
      id: 'outbox-1',
      status: 'retrying',
      manual_replay_count: 1,
    })
  })

  it('shows health metrics, privacy-safe issues, and manually replays failed outbox', async () => {
    vi.spyOn(ElMessageBox, 'prompt').mockResolvedValue({ value: '通知通道恢复后人工重放' } as never)
    const wrapper = mount(WorkflowOperationsView, {
      global: { plugins: [ElementPlus] },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('工作流运维')
    expect(wrapper.text()).toContain('卡死 Run')
    expect(wrapper.text()).toContain('流程无可用路径')
    expect(wrapper.text()).toContain('workflow_run_events')
    expect(wrapper.text()).toContain('delivery failed')
    expect(wrapper.text()).not.toContain('payload')

    const replay = wrapper.findAll('button').find((item) => item.text().includes('重放'))
    expect(replay).toBeTruthy()
    await replay?.trigger('click')
    await flushPromises()

    expect(replayWorkflowOutbox).toHaveBeenCalledWith(
      'outbox-1',
      '通知通道恢复后人工重放',
    )
    expect(getWorkflowOperationsDashboard).toHaveBeenCalledTimes(2)
  })

  it('searches traces by a single exact identifier', async () => {
    const wrapper = mount(WorkflowOperationsView, {
      global: { plugins: [ElementPlus] },
    })
    await flushPromises()
    const input = wrapper.get('[data-testid="workflow-trace-query"]')
    await input.setValue('request-123')
    await wrapper.get('[data-testid="workflow-trace-search"]').trigger('click')
    await flushPromises()

    expect(searchWorkflowTraces).toHaveBeenCalledWith({ request_id: 'request-123' })
  })
})
