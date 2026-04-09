export function formatDateTime(value) {
  if (!value) {
    return "Not available"
  }

  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return "Not available"
  }

  return parsed.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  })
}

export function getAuthUserInfo(user) {
  if (!user) {
    return {
      displayName: "Guest User",
      username: "guest",
      email: "Not available",
      initials: "GU",
      joinedAt: "Not available",
      lastLoginAt: "Not available",
      provider: "email",
      userId: "Not available",
      emailConfirmed: false,
    }
  }

  const metadata = user.user_metadata || {}
  const rawName =
    metadata.full_name ||
    metadata.name ||
    metadata.user_name ||
    metadata.preferred_username ||
    ""
  const fallbackUsername = user.email ? user.email.split("@")[0] : "user"
  const username = metadata.preferred_username || metadata.user_name || fallbackUsername
  const displayName = rawName || username || "User"
  const initials = displayName
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() || "")
    .join("") || "U"

  return {
    displayName,
    username,
    email: user.email || "Not available",
    initials,
    joinedAt: formatDateTime(user.created_at),
    lastLoginAt: formatDateTime(user.last_sign_in_at),
    provider: user.app_metadata?.provider || "email",
    userId: user.id || "Not available",
    emailConfirmed: Boolean(user.email_confirmed_at),
  }
}