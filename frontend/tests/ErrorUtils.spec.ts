import { describe, expect, it } from 'vitest'

import { getErrorMessage } from '@/utils/errors'

describe('getErrorMessage', () => {
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
