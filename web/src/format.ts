/** Human-friendly durations: 0.45s, 34.2s, 5m 17s. */
export function seconds(value: number | null | undefined): string {
  if (value == null) return 'never'
  if (Number.isInteger(value) && value < 120) return `${value}s`
  if (value < 1) return `${value.toFixed(2)}s`
  if (value < 120) return `${value.toFixed(1)}s`
  const m = Math.floor(value / 60)
  const s = Math.round(value % 60)
  return s === 60 ? `${m + 1}m 0s` : `${m}m ${s}s`
}

export function percent(value: number): string {
  return `${Math.round(value * 100)}%`
}

export function rate(value: number): string {
  return `${value < 10 ? value.toFixed(2).replace(/\.?0+$/, '') : Math.round(value)}/s`
}

export function count(value: number): string {
  return Math.round(value).toLocaleString()
}

export function decimal(value: number): string {
  return value < 10 ? value.toFixed(1) : Math.round(value).toLocaleString()
}

/** Short x-axis tick: 90 -> "1:30", 600 -> "10:00". */
export function clock(value: number): string {
  const m = Math.floor(value / 60)
  const s = Math.round(value % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}
