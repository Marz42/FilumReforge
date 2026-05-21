export const HOUR_OPTIONS = Array.from({ length: 24 }, (_, hour) =>
  String(hour).padStart(2, '0'),
)

export const FIVE_MINUTE_MINUTE_OPTIONS = Array.from({ length: 12 }, (_, index) =>
  String(index * 5).padStart(2, '0'),
)

export function roundToFiveMinutes(date: Date): Date {
  const rounded = new Date(date)
  const minutes = rounded.getMinutes()
  const remainder = minutes % 5
  if (remainder !== 0) {
    rounded.setMinutes(minutes + (5 - remainder))
  }
  rounded.setSeconds(0, 0)
  return rounded
}

export function parseDateTimeParts(value: Date | null): {
  date: string
  hour: string
  minute: string
} {
  if (!value) {
    return { date: '', hour: '', minute: '' }
  }
  const rounded = roundToFiveMinutes(value)
  const year = rounded.getFullYear()
  const month = String(rounded.getMonth() + 1).padStart(2, '0')
  const day = String(rounded.getDate()).padStart(2, '0')
  return {
    date: `${year}-${month}-${day}`,
    hour: String(rounded.getHours()).padStart(2, '0'),
    minute: String(rounded.getMinutes()).padStart(2, '0'),
  }
}

export function mergeDateAndTime(
  datePart: string,
  hourPart: string,
  minutePart: string,
): Date | null {
  if (!datePart || !hourPart || !minutePart) {
    return null
  }
  const merged = new Date(`${datePart}T${hourPart}:${minutePart}:00`)
  if (Number.isNaN(merged.getTime())) {
    return null
  }
  return roundToFiveMinutes(merged)
}
