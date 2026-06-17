export function formatUserOptionLabel(user: {
  email: string
  display_name?: string | null
}): string {
  const name = user.display_name?.trim()
  return name ? `${name}（${user.email}）` : user.email
}
