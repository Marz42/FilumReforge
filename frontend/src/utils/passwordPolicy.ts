export const PASSWORD_MIN_LENGTH = 8
export const PASSWORD_MAX_LENGTH = 128

export const PASSWORD_POLICY_FALLBACK =
  '密码不符合安全策略，请检查长度、大小写与数字要求'

export type PasswordValidationResult = {
  valid: boolean
  reasons: string[]
}

function hasLowercase(value: string): boolean {
  return /[a-z]/.test(value)
}

function hasUppercase(value: string): boolean {
  return /[A-Z]/.test(value)
}

function hasDigit(value: string): boolean {
  return /\d/.test(value)
}

function hasSymbol(value: string): boolean {
  return /[^A-Za-z0-9]/.test(value)
}

export function validatePasswordClient(value: string): PasswordValidationResult {
  const reasons: string[] = []

  if (value.length < PASSWORD_MIN_LENGTH) {
    reasons.push(`密码长度至少 ${PASSWORD_MIN_LENGTH} 个字符`)
  }
  if (value.length > PASSWORD_MAX_LENGTH) {
    reasons.push(`密码长度不能超过 ${PASSWORD_MAX_LENGTH} 个字符`)
  }

  const categories = [
    { met: hasLowercase(value), label: '小写字母' },
    { met: hasUppercase(value), label: '大写字母' },
    { met: hasDigit(value), label: '数字' },
    { met: hasSymbol(value), label: '符号' },
  ]
  const metCount = categories.filter((category) => category.met).length

  if (metCount < 3) {
    const missing = categories.filter((category) => !category.met).map((category) => category.label)
    reasons.push(`密码至少需要包含大写字母、小写字母、数字、符号中的三类（当前缺少：${missing.join('、')}）`)
  }

  return {
    valid: reasons.length === 0,
    reasons,
  }
}

export function formatPasswordValidationMessage(reasons: string[]): string {
  if (reasons.length === 0) {
    return PASSWORD_POLICY_FALLBACK
  }
  return reasons.join('；')
}
