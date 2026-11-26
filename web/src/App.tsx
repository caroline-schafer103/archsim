import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchExamples, simulate } from './api'
import { Editor, type Compare } from './components/Editor'
import { PipelineDiagram } from './components/PipelineDiagram'
import { QueueCharts, SERIES } from './components/QueueCharts'
import { ResultsTable, Summary } from './components/Results'
import type { Example, SimConfig, SimResults } from './types'

// A comparison worth seeing when each example first loads.
const STARTER_COMPARISONS: Record<string, Compare> = {
  'video-upload': { stage: 'transcode', values: '150, 200, 250' },
  'email-notifications': { stage: 'send', values: '60, 70, 80' },
}
const DEFAULT_EXAMPLE = 'video-upload'
const NO_COMPARE: Compare = { stage: '', values: '' }

function varyString(compare: Compare): string | null {
  const values = compare.values
    .split(',')
    .map((v) => v.trim())
    .filter(Boolean)
  return compare.stage && values.length ? `${compare.stage}.workers=${values.join(',')}` : null
}

export default function App() {
  const [examples, setExamples] = useState<Example[]>([])
  const [exampleId, setExampleId] = useState<string>('')
  const [config, setConfig] = useState<SimConfig | null>(null)
  const [compare, setCompare] = useState<Compare>(NO_COMPARE)
  const [results, setResults] = useState<SimResults[] | null>(null)
  const [selectedRun, setSelectedRun] = useState(0)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [stale, setStale] = useState(false)
  const requestId = useRef(0)

  const run = useCallback(async (cfg: SimConfig, cmp: Compare) => {
    const id = ++requestId.current
    setRunning(true)
    setError(null)
    try {
      const res = await simulate(cfg, varyString(cmp))
      if (id !== requestId.current) return // a newer run started
      setResults(res)
      setSelectedRun((current) => (current < res.length ? current : 0))
      setStale(false)
    } catch (e) {
      if (id === requestId.current) setError((e as Error).message)
    } finally {
      if (id === requestId.current) setRunning(false)
    }
  }, [])

  const loadExample = useCallback(
    (example: Example) => {
      const cmp = STARTER_COMPARISONS[example.id] ?? NO_COMPARE
      setExampleId(example.id)
      setConfig(example.config)
      setCompare(cmp)
      setSelectedRun(0)
      void run(example.config, cmp)
    },
    [run],
  )

  useEffect(() => {
    fetchExamples()
      .then((list) => {
        setExamples(list)
        const first = list.find((e) => e.id === DEFAULT_EXAMPLE) ?? list[0]
        if (first) loadExample(first)
      })
      .catch((e: Error) => setError(`${e.message}. Is the API running? Start it with: archsim serve`))
  }, [loadExample])

  // Ctrl/Cmd + Enter runs the simulation from anywhere.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && config) void run(config, compare)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [config, compare, run])

  const updateConfig = (next: SimConfig) => {
    setConfig(next)
    setStale(true)
  }
  const updateCompare = (next: Compare) => {
    setCompare(next)
    setStale(true)
  }

  const example = examples.find((e) => e.id === exampleId)
  const selected = results?.[selectedRun] ?? null

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo" aria-hidden>
            <svg viewBox="0 0 32 32" width="24" height="24">
              <rect width="32" height="32" rx="7" fill="var(--series-1)" />
              <path d="M6 22h4v-6H6zM14 22h4V10h-4zM22 22h4v-9h-4z" fill="#fff" />
            </svg>
          </span>
          <span className="brand-name">ArchSim</span>
          <span className="tagline">Find the bottleneck before your users do</span>
        </div>
        <div className="topbar-actions">
          <label className="example-picker">
            <span>Example</span>
            <select
              value={exampleId}
              onChange={(e) => {
                const ex = examples.find((x) => x.id === e.target.value)
                if (ex) loadExample(ex)
              }}
            >
              {examples.map((e) => (
                <option key={e.id} value={e.id}>
                  {e.title}
                </option>
              ))}
            </select>
          </label>
          <button
            className={`primary${stale ? ' attention' : ''}`}
            disabled={!config || running}
            onClick={() => config && void run(config, compare)}
            title="Ctrl + Enter"
          >
            {running ? 'Running…' : stale ? 'Run again' : 'Run simulation'}
          </button>
        </div>
      </header>

      <div className="layout">
        <aside className="sidebar">{config && <Editor config={config} onChange={updateConfig} compare={compare} onCompareChange={updateCompare} />}</aside>

        <main className="content">
          {example && (
            <div className="intro">
              <h1>{example.title}</h1>
              <p>{example.description}</p>
            </div>
          )}

          {error && (
            <div className="error" role="alert">
              <span className="badge critical">
                <span aria-hidden>✕</span> Error
              </span>{' '}
              {error}
            </div>
          )}

          {config && (
            <section className={`panel${stale || running ? ' dimmed' : ''}`}>
              <div className="panel-head">
                <h2>Architecture</h2>
                {results && results.length > 1 && (
                  <div className="run-picker" role="tablist" aria-label="Show run">
                    {results.map((r, k) => (
                      <button
                        key={k}
                        role="tab"
                        aria-selected={k === selectedRun}
                        className={k === selectedRun ? 'selected' : ''}
                        onClick={() => setSelectedRun(k)}
                      >
                        <span className="line-key" style={{ background: SERIES[k % SERIES.length] }} />
                        {r.config.name}
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <PipelineDiagram config={selected && !stale ? selected.config : config} result={stale ? null : selected} />
              {selected && <Summary result={selected} />}
            </section>
          )}

          {results && (
            <section className={`panel${stale || running ? ' dimmed' : ''}`}>
              <div className="panel-head">
                <h2>Queue depth by stage</h2>
              </div>
              <QueueCharts results={results} />
            </section>
          )}

          {results && (
            <section className={`panel${stale || running ? ' dimmed' : ''}`}>
              <div className="panel-head">
                <h2>{results.length > 1 ? 'Comparison' : 'All metrics'}</h2>
              </div>
              <ResultsTable results={results} />
            </section>
          )}
        </main>
      </div>
    </div>
  )
}
