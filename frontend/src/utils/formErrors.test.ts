import axios from 'axios'
import { describe, expect, it } from 'vitest'

import { extractValidationDetail } from '@/utils/formErrors'
import { getErrorMessage } from '@/utils/errors'

describe('extractValidationDetail', () => {
  it('parses FastAPI 422 validation arrays', () => {
    const error = new axios.AxiosError(
      'Request failed',
      '422',
      undefined,
      undefined,
      {
        status: 422,
        statusText: 'Unprocessable Entity',
        headers: {},
        config: { headers: new axios.AxiosHeaders() },
        data: {
          detail: [
            {
              loc: ['body', 'password'],
              msg: 'Value error, 密码至少需要包含大写字母、小写字母、数字、符号中的三类。',
              type: 'value_error',
            },
          ],
        },
      },
    )

    expect(extractValidationDetail(error)).toBe('密码至少需要包含大写字母、小写字母、数字、符号中的三类。')
  })

  it('returns null for non-validation errors', () => {
    const error = new axios.AxiosError(
      'Unauthorized',
      '401',
      undefined,
      undefined,
      {
        status: 401,
        statusText: 'Unauthorized',
        headers: {},
        config: { headers: new axios.AxiosHeaders() },
        data: { detail: 'unauthorized' },
      },
    )

    expect(extractValidationDetail(error)).toBeNull()
  })
})

describe('getErrorMessage', () => {
  it('prefers validation detail over generic axios messages', () => {
    const error = new axios.AxiosError(
      'Request failed with status code 422',
      '422',
      undefined,
      undefined,
      {
        status: 422,
        statusText: 'Unprocessable Entity',
        headers: {},
        config: { headers: new axios.AxiosHeaders() },
        data: {
          detail: [
            {
              loc: ['body', 'password'],
              msg: 'Value error, 密码至少需要包含大写字母、小写字母、数字、符号中的三类。',
              type: 'value_error',
            },
          ],
        },
      },
    )

    expect(getErrorMessage(error)).toBe('密码至少需要包含大写字母、小写字母、数字、符号中的三类。')
  })

  it('falls back when 422 payload is empty', () => {
    const error = new axios.AxiosError(
      'Request failed with status code 422',
      '422',
      undefined,
      undefined,
      {
        status: 422,
        statusText: 'Unprocessable Entity',
        headers: {},
        config: { headers: new axios.AxiosHeaders() },
        data: { detail: [] },
      },
    )

    expect(getErrorMessage(error)).toContain('密码不符合安全策略')
  })
})
