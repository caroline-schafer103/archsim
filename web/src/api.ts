import type { Example, SimConfig, SimResults } from './types'

export async function fetchExamples(): Promise<Example[]> {
  const res = await fetch('/api/examples')
  if (!res.ok) throw new Error(`Couldn't load examples (${res.status})`)
  return res.json()
}

export async function simulate(config: SimConfig, vary: string | null): Promise<SimResults[]> {
  const res = await fetch('/api/simulate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ config, vary }),
  })
  const body = await res.json().catch(() => null)
  if (!res.ok) throw new Error(describeError(body, res.status))
  return body.results
}

interface ValidationIssue {
  loc: (string | number)[]
  msg: string
}

/** Turn FastAPI errors into a readable sentence, e.g. "stages → 1 → workers: ..." */
function describeError(body: unknown, status: number): string {
  const detail = (body as { detail?: unknown } | null)?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return (detail as ValidationIssue[])
      .map((d) => {
        const path = d.loc
          .filter((p) => p !== 'body' && p !== 'config')
          .map((p) => (typeof p === 'number' ? `#${p + 1}` : p))
          .join(' → ')
        return `${path}: ${d.msg}`
      })
      .join('; ')
  }
  return `Simulation failed (${status})`
}
