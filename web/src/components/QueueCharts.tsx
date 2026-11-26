import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipProps,
} from 'recharts'
import { clock, seconds } from '../format'
import type { SimResults } from '../types'

export const SERIES = Array.from({ length: 8 }, (_, i) => `var(--series-${i + 1})`)

interface Props {
  results: SimResults[]
}

/** Queue depth over time: one chart per stage (shared y-scale), one line per run. */
export function QueueCharts({ results }: Props) {
  const config = results[0].config
  const duration = config.workload.duration
  const spikes = config.workload.spikes
  const multiRun = results.length > 1

  // Shared y-scale so stages can be compared honestly.
  const yTicks = niceTicks(Math.max(1, ...results.flatMap((r) => r.stages.flatMap((s) => s.timeseries.map((p) => p.queue_depth)))))
  const yMax = yTicks[yTicks.length - 1]

  return (
    <div className="queue-charts">
      {multiRun && <Legend results={results} />}
      {config.stages.map((stage) => {
        const workerCounts = new Set(results.map((r) => r.config.stages.find((s) => s.name === stage.name)?.workers))
        const workers = workerCounts.size > 1 ? 'workers vary by run' : `${stage.workers} workers${multiRun ? ' in every run' : ''}`

        // All series share the API's resampled time grid, so rows line up by index.
        const base = results[0].stages.find((s) => s.name === stage.name)!.timeseries
        const rows = base.map((p, i) => {
          const row: Record<string, number> = { t: p.time }
          results.forEach((r, k) => {
            row[`r${k}`] = r.stages.find((s) => s.name === stage.name)!.timeseries[i]?.queue_depth ?? 0
          })
          return row
        })

        return (
          <figure className="chart-card" key={stage.name}>
            <figcaption>
              <strong>{stage.name}</strong>
              <span>
                {workers} · {seconds(stage.service_time)} per event
              </span>
            </figcaption>
            <div className="chart-body">
              <ResponsiveContainer width="100%" height={180}>
                <LineChart data={rows} syncId="queues" margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
                  <CartesianGrid vertical={false} stroke="var(--grid)" />
                  {spikes.map((s, i) => (
                    <ReferenceArea
                      key={i}
                      x1={s.start}
                      x2={Math.min(duration, s.start + s.duration)}
                      fill="var(--spike)"
                      fillOpacity={1}
                      ifOverflow="hidden"
                      label={{ value: `${s.multiplier}× traffic`, position: 'insideTop', fill: 'var(--text-muted)', fontSize: 11 }}
                    />
                  ))}
                  <XAxis
                    dataKey="t"
                    type="number"
                    domain={[0, duration]}
                    tickFormatter={clock}
                    stroke="var(--grid)"
                    tick={{ fill: 'var(--text-muted)', fontSize: 11 }}
                    tickLine={false}
                  />
                  <YAxis
                    domain={[0, yMax]}
                    ticks={yTicks}
                    allowDecimals={false}
                    width={44}
                    stroke="var(--grid)"
                    tick={{ fill: 'var(--text-muted)', fontSize: 11 }}
                    tickLine={false}
                    axisLine={false}
                  />
                  <Tooltip
                    content={<ChartTooltip results={results} />}
                    cursor={{ stroke: 'var(--text-muted)', strokeWidth: 1 }}
                    isAnimationActive={false}
                  />
                  {results.map((r, k) => (
                    <Line
                      key={k}
                      dataKey={`r${k}`}
                      name={r.config.name}
                      type="stepAfter"
                      stroke={SERIES[k % SERIES.length]}
                      strokeWidth={2}
                      dot={false}
                      activeDot={{ r: 4, strokeWidth: 2, stroke: 'var(--surface)' }}
                      isAnimationActive={false}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </figure>
        )
      })}
      <p className="chart-note">Events waiting in each stage's queue over simulated time (minutes:seconds). Hover to compare runs.</p>
    </div>
  )
}

export function Legend({ results }: { results: SimResults[] }) {
  return (
    <ul className="legend" aria-label="Runs">
      {results.map((r, k) => (
        <li key={k}>
          <span className="line-key" style={{ background: SERIES[k % SERIES.length] }} />
          {r.config.name}
        </li>
      ))}
    </ul>
  )
}

function ChartTooltip({ active, payload, label, results }: TooltipProps<number, string> & { results: SimResults[] }) {
  if (!active || !payload?.length) return null
  return (
    <div className="tooltip">
      <div className="tooltip-head">t = {clock(Number(label))}</div>
      {payload.map((p) => {
        const k = Number(String(p.dataKey).slice(1))
        return (
          <div className="tooltip-row" key={k}>
            <span className="line-key" style={{ background: SERIES[k % SERIES.length] }} />
            <strong>{Number(p.value).toLocaleString()}</strong>
            <span>{results.length > 1 ? results[k].config.name : 'waiting'}</span>
          </div>
        )
      })}
    </div>
  )
}

/** Evenly spaced, round-numbered ticks covering 0..value: 412 -> [0, 100, ..., 500]. */
function niceTicks(value: number, target = 5): number[] {
  const raw = value / target
  const magnitude = 10 ** Math.floor(Math.log10(raw))
  const step = [1, 2, 2.5, 5, 10].map((s) => s * magnitude).find((s) => s >= raw) ?? 10 * magnitude
  const top = Math.max(step, Math.ceil(value / step) * step)
  return Array.from({ length: Math.round(top / step) + 1 }, (_, i) => i * step)
}
