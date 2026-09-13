import { describe, expect, it, vi } from 'vitest'
import { CanceledError } from 'axios'
import { ElMessage } from 'element-plus'

import { getErrorMessage, showError } from '@/utils/errors'

describe('getErrorMessage', () => {
  it('silences only cancellation while preserving real errors and fallback copy', () => {
    const message = vi.spyOn(ElMessage, 'error').mockReturnValue({ close: vi.fn() })
    try {
      showError(new CanceledError('Session changed'))
      expect(message).not.toHaveBeenCalled()
      showError(new Error('真实网络错误'))
      expect(message).toHaveBeenLastCalledWith('真实网络错误')
      showError(new Error('detail'), '原有提示')
      expect(message).toHaveBeenLastCalledWith('原有提示')
    } finally { message.mockRestore() }
  })
  it('prefers request id from response payload', () => {
    const message = getErrorMessage({
      isAxiosError: true,
      message: 'Request failed with status code 500',
      response: {
        data: {
          detail: '服务器内部错误，请记录请求编号并反馈给开发者。',
          request_id: 'req-payload-1',
        },
        headers: {},
      },
    })

    expect(message).toBe('服务器内部错误，请记录请求编号并反馈给开发者。（请求编号：req-payload-1）')
  })

  it('falls back to request id from response headers', () => {
    const message = getErrorMessage({
      isAxiosError: true,
      message: 'Request failed with status code 500',
      response: {
        data: {
          detail: '服务器内部错误，请记录请求编号并反馈给开发者。',
        },
        headers: {
          'x-request-id': 'req-header-1',
        },
      },
    })

    expect(message).toBe('服务器内部错误，请记录请求编号并反馈给开发者。（请求编号：req-header-1）')
  })
})
