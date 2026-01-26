/**
 * Timezone-aware date/time formatting utilities
 *
 * All functions format dates in Eastern time (America/New_York)
 * with automatic daylight saving time handling.
 *
 * Backend sends timestamps as UTC without timezone indicator (e.g., "2025-01-15T10:45:00").
 * We must treat these as UTC before converting to Eastern time.
 */

const TIMEZONE = 'America/New_York'

/**
 * Parse a timestamp string as UTC.
 * Backend sends ISO strings without 'Z' suffix, so we need to ensure
 * JavaScript interprets them as UTC, not local time.
 *
 * Special handling for date-only strings (YYYY-MM-DD):
 * These are treated as local dates, not UTC midnight, to prevent
 * the date shifting when converted to Eastern time.
 */
function parseAsUTC(timestamp: string | Date): Date {
  if (timestamp instanceof Date) return timestamp

  // Date-only strings (YYYY-MM-DD) should be treated as local dates
  // to prevent timezone conversion from shifting the displayed day
  if (/^\d{4}-\d{2}-\d{2}$/.test(timestamp)) {
    // Parse as local date by adding T12:00:00 (noon local time)
    // This ensures the date stays the same regardless of timezone
    const [year, month, day] = timestamp.split('-').map(Number)
    return new Date(year, month - 1, day, 12, 0, 0)
  }

  // If the string doesn't have timezone info, treat it as UTC
  if (!timestamp.endsWith('Z') && !timestamp.includes('+') && !timestamp.includes('-', 10)) {
    return new Date(timestamp + 'Z')
  }
  return new Date(timestamp)
}

/**
 * Format a timestamp as full datetime: "Jan 15, 2025, 2:30 PM"
 */
export function formatDateTime(timestamp: string | Date | null | undefined): string {
  if (!timestamp) return ''
  const date = parseAsUTC(timestamp)
  return date.toLocaleString('en-US', {
    timeZone: TIMEZONE,
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

/**
 * Format a timestamp as date only: "Jan 15, 2025"
 */
export function formatDate(timestamp: string | Date | null | undefined): string {
  if (!timestamp) return ''
  const date = parseAsUTC(timestamp)
  return date.toLocaleDateString('en-US', {
    timeZone: TIMEZONE,
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

/**
 * Format a timestamp as time only: "2:30 PM"
 */
export function formatTime(timestamp: string | Date | null | undefined): string {
  if (!timestamp) return ''
  const date = parseAsUTC(timestamp)
  return date.toLocaleTimeString('en-US', {
    timeZone: TIMEZONE,
    hour: 'numeric',
    minute: '2-digit',
  })
}

/**
 * Format a timestamp as short datetime (no year): "Jan 15, 2:30 PM"
 */
export function formatShortDateTime(timestamp: string | Date | null | undefined): string {
  if (!timestamp) return ''
  const date = parseAsUTC(timestamp)
  return date.toLocaleString('en-US', {
    timeZone: TIMEZONE,
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

/**
 * Format a timestamp as relative time: "Just now", "5 mins ago", "2 hours ago"
 * Falls back to date format for older timestamps (>7 days)
 */
export function formatRelativeTime(timestamp: string | Date | null | undefined): string {
  if (!timestamp) return ''
  const date = parseAsUTC(timestamp)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins} min${diffMins === 1 ? '' : 's'} ago`
  if (diffHours < 24) return `${diffHours} hour${diffHours === 1 ? '' : 's'} ago`
  if (diffDays < 7) return `${diffDays} day${diffDays === 1 ? '' : 's'} ago`
  return formatDate(date)
}

/**
 * Get ISO date string (YYYY-MM-DD) in Eastern timezone
 * Useful for inputs, filenames, and date keys
 */
export function formatISODate(timestamp?: string | Date | null): string {
  const date = timestamp ? parseAsUTC(timestamp) : new Date()
  // Get date components in Eastern timezone
  const formatter = new Intl.DateTimeFormat('en-CA', {
    timeZone: TIMEZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
  return formatter.format(date)
}

/**
 * Format a timestamp for chart axis labels
 * Short format optimized for graphs: "2:30 PM" or "Jan 15"
 */
export function formatChartTime(timestamp: string | Date | null | undefined, showDate = false): string {
  if (!timestamp) return ''
  const date = parseAsUTC(timestamp)
  if (showDate) {
    return date.toLocaleDateString('en-US', {
      timeZone: TIMEZONE,
      month: 'short',
      day: 'numeric',
    })
  }
  return date.toLocaleTimeString('en-US', {
    timeZone: TIMEZONE,
    hour: 'numeric',
    minute: '2-digit',
  })
}
