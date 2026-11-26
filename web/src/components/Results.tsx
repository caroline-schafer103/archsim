import { count, decimal, percent, rate, seconds } from '../format'
import type { SimResults } from '../types'
import { SERIES } from './QueueCharts'

/** Headline numbers for one run, plus a plain-English read of the bottleneck. */
export function Summary({ result }: { result: SimResults }) {
  const unfinished = result.generated - result.completed
  const unfinishedShare = result.generated ? unfinished / result.generated : 0
  const recovery = result.spike_recovery
  const worstRecovery = recovery.length ? (recovery.includes(null) ? null : Math.max(...(recovery as number[]))) : undefined
  const b = result.bottleneck

  return (
    <div className="summary">
      <div className="tiles">
        <Tile label="P95 latency" value={seconds(result.p95_latency)} hint={`median ${seconds(result.p50_latency)}`} />
        {worstRecovery !== undefined && (
          <Tile
            label="Spike recovery"
            value={seconds(worstRecovery)}
            hint={worstRecovery === null ? 'still backed up at the end' : 'until queues are back to normal'}
          />
        )}
        <Tile label="Throughput" value={rate(result.throughput)} hint={`${count(result.completed)} of ${count(result.generated)} done`} />
        <Tile label="Bottleneck" value={b ? b.stage : 'None'} hint={b ? `${percent(b.wait_share)} of all waiting` : 'nothing had to wait'} />
      </div>

      {b && result.config.stages.length > 1 && (
        <p className="insight">
          <strong>{b.stage}</strong> is the bottleneck: it's {percent(b.utilization)} busy and accounts for{' '}
          {percent(b.wait_share)} of all time events spend waiting in queues.
        </p>
      )}
      {unfinishedShare > 0.05 && (
        <p className="warning">
          <span className="badge warning">
            <span aria-hidden>!</span> Incomplete
          </span>{' '}
          {count(unfinished)} of {count(result.generated)} events never finished, so latency figures (which only cover
          finished events) understate the real delay.
        </p>
      )}
    </div>
  )
}

function Tile({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="tile">
      <div className="tile-label">{label}</div>
      <div className="tile-value">{value}</div>
      <div className="tile-hint">{hint}</div>
    </div>
  )
}

type Row = [label: string, get: (r: SimResults) => string]

/** Every metric for every run, side by side (also the accessible view of the charts). */
export function ResultsTable({ results }: { results: SimResults[] }) {
  const config = results[0].config
  const sections: [string | null, Row[]][] = [
    [
      null,
      [
        ['P50 latency', (r) => seconds(r.p50_latency)],
        ['P95 latency', (r) => seconds(r.p95_latency)],
        ['P99 latency', (r) => seconds(r.p99_latency)],
        ['Throughput', (r) => rate(r.throughput)],
        ['Completed', (r) => `${count(r.completed)} / ${count(r.generated)}`],
        ...(config.workload.spikes.length
          ? ([['Spike recovery', (r) => r.spike_recovery.map(seconds).join(', ')]] as Row[])
          : []),
        ...(config.stages.length > 1 ? ([['Bottleneck', (r) => r.bottleneck?.stage ?? 'none']] as Row[]) : []),
      ],
    ],
    ...config.stages.map(
      (stage): [string, Row[]] => [
        stage.name,
        [
          ['Workers', (r) => String(st(r, stage.name).workers)],
          ['Capacity', (r) => rate(st(r, stage.name).capacity)],
          ['Busy', (r) => percent(st(r, stage.name).utilization)],
          ['Avg wait', (r) => seconds(st(r, stage.name).avg_wait_time)],
          ['Avg queue', (r) => decimal(st(r, stage.name).avg_queue_depth)],
          ['Peak queue', (r) => count(st(r, stage.name).max_queue_depth)],
        ],
      ],
    ),
  ]

  return (
    <div className="table-scroll">
      <table className="results-table">
        <thead>
          <tr>
            <th scope="col">
              <span className="visually-hidden">Metric</span>
            </th>
            {results.map((r, k) => (
              <th scope="col" key={k}>
                {results.length > 1 && <span className="line-key" style={{ background: SERIES[k % SERIES.length] }} />}
                {results.length > 1 ? r.config.name : 'Result'}
              </th>
            ))}
          </tr>
        </thead>
        {sections.map(([title, rows], i) => (
          <tbody key={i}>
            {title && (
              <tr className="section-row">
                <th scope="rowgroup" colSpan={results.length + 1}>
                  {title}
                </th>
              </tr>
            )}
            {rows.map(([label, get]) => (
              <tr key={label}>
                <th scope="row">{label}</th>
                {results.map((r, k) => (
                  <td key={k}>{get(r)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        ))}
      </table>
    </div>
  )
}

function st(r: SimResults, name: string) {
  return r.stages.find((s) => s.name === name)!
}
