import { Fragment } from 'react'
import { percent, rate, seconds } from '../format'
import type { SimConfig, SimResults } from '../types'

interface Props {
  config: SimConfig
  result: SimResults | null // the run to annotate the diagram with
}

/** Arrivals -> stage -> stage -> done, annotated with how each stage is doing. */
export function PipelineDiagram({ config, result }: Props) {
  const { workload } = config
  const peak = Math.max(1, ...workload.spikes.map((s) => s.multiplier))

  return (
    <div className="pipeline" role="list" aria-label="Pipeline">
      <div className="node endpoint" role="listitem">
        <div className="node-label">Arrivals</div>
        <div className="node-value">{rate(workload.rate)}</div>
        <div className="node-meta">
          {workload.arrivals === 'poisson' ? 'random' : 'evenly spaced'}
          {peak > 1 && ` · peaks at ${rate(workload.rate * peak)}`}
        </div>
      </div>

      {config.stages.map((stage) => {
        const stats = result?.stages.find((s) => s.name === stage.name)
        const isBottleneck = result?.bottleneck?.stage === stage.name
        const capacity = stage.workers / stage.service_time
        return (
          <Fragment key={stage.name}>
            <Arrow />
            <div className={`node stage${isBottleneck ? ' bottleneck' : ''}`} role="listitem">
              <div className="node-head">
                <div className="node-label">{stage.name}</div>
                {isBottleneck && (
                  <span className="badge serious">
                    <span aria-hidden>▲</span> Bottleneck
                  </span>
                )}
              </div>
              <div className="node-meta">
                {stage.workers} workers × {seconds(stage.service_time)} each
              </div>
              <div className="node-value">
                {rate(capacity)} <span className="node-unit">capacity</span>
              </div>
              {stats && (
                <div className="node-stats">
                  <Meter label="Busy" value={stats.utilization} />
                  <div className="stat-line">
                    <span>Avg wait</span>
                    <strong>{seconds(stats.avg_wait_time)}</strong>
                  </div>
                  <div className="stat-line">
                    <span>Peak queue</span>
                    <strong>{stats.max_queue_depth.toLocaleString()}</strong>
                  </div>
                </div>
              )}
            </div>
          </Fragment>
        )
      })}

      <Arrow />
      <div className="node endpoint" role="listitem">
        <div className="node-label">Done</div>
        <div className="node-value">{result ? rate(result.throughput) : '—'}</div>
        <div className="node-meta">{result ? `P95 ${seconds(result.p95_latency)} end to end` : 'run to see results'}</div>
      </div>
    </div>
  )
}

function Arrow() {
  return (
    <div className="arrow" aria-hidden>
      <svg viewBox="0 0 24 12" width="24" height="12">
        <path d="M0 6h20M15 1l6 5-6 5" fill="none" stroke="currentColor" strokeWidth="1.5" />
      </svg>
    </div>
  )
}

function Meter({ label, value }: { label: string; value: number }) {
  return (
    <div className="meter">
      <div className="stat-line">
        <span>{label}</span>
        <strong>{percent(value)}</strong>
      </div>
      <div className="meter-track" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(value * 100)} aria-label={label}>
        <div className="meter-fill" style={{ width: `${Math.min(100, value * 100)}%` }} />
      </div>
    </div>
  )
}
