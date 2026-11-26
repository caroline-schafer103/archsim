import { useEffect, useState } from 'react'
import type { ArrivalPattern, ServicePattern, SimConfig, Spike, Stage } from '../types'

export interface Compare {
  stage: string // '' = no comparison
  values: string // e.g. "150, 200, 250"
}

interface Props {
  config: SimConfig
  onChange: (config: SimConfig) => void
  compare: Compare
  onCompareChange: (compare: Compare) => void
}

export function Editor({ config, onChange, compare, onCompareChange }: Props) {
  const { workload, stages } = config

  const setWorkload = (patch: Partial<SimConfig['workload']>) =>
    onChange({ ...config, workload: { ...workload, ...patch } })

  const setStage = (i: number, patch: Partial<Stage>) => {
    const next = stages.map((s, j) => (j === i ? { ...s, ...patch } : s))
    // Keep the comparison pointed at a renamed stage.
    if (patch.name !== undefined && compare.stage === stages[i].name) {
      onCompareChange({ ...compare, stage: patch.name })
    }
    onChange({ ...config, stages: next })
  }

  const moveStage = (i: number, delta: number) => {
    const next = [...stages]
    const [s] = next.splice(i, 1)
    next.splice(i + delta, 0, s)
    onChange({ ...config, stages: next })
  }

  const removeStage = (i: number) => {
    if (compare.stage === stages[i].name) onCompareChange({ ...compare, stage: '' })
    onChange({ ...config, stages: stages.filter((_, j) => j !== i) })
  }

  const addStage = () => {
    const names = new Set(stages.map((s) => s.name))
    let n = stages.length + 1
    while (names.has(`stage-${n}`)) n++
    onChange({
      ...config,
      stages: [...stages, { name: `stage-${n}`, workers: 10, service_time: 1, service: 'exponential' }],
    })
  }

  const setSpike = (i: number, patch: Partial<Spike>) =>
    setWorkload({ spikes: workload.spikes.map((s, j) => (j === i ? { ...s, ...patch } : s)) })

  return (
    <div className="editor">
      <section>
        <h3>Workload</h3>
        <div className="field-grid">
          <NumberField label="Arrival rate" unit="/s" value={workload.rate} positive onChange={(rate) => setWorkload({ rate })} />
          <NumberField label="Duration" unit="s" value={workload.duration} positive onChange={(duration) => setWorkload({ duration })} />
          <label className="field">
            <span>Arrivals</span>
            <select value={workload.arrivals} onChange={(e) => setWorkload({ arrivals: e.target.value as ArrivalPattern })}>
              <option value="poisson">Random (Poisson)</option>
              <option value="constant">Evenly spaced</option>
            </select>
          </label>
          <NumberField
            label="Seed"
            value={workload.seed}
            optional
            integer
            placeholder="random"
            onChange={(seed) => setWorkload({ seed })}
          />
        </div>

        <div className="subsection">
          <div className="subsection-head">
            <h4>Traffic spikes</h4>
            <button
              className="link"
              onClick={() =>
                setWorkload({
                  spikes: [...workload.spikes, { start: Math.round(workload.duration / 3), duration: 60, multiplier: 2 }],
                })
              }
            >
              + Add spike
            </button>
          </div>
          {workload.spikes.length === 0 && <p className="hint">None. Add one to see how the system recovers from a burst.</p>}
          {workload.spikes.map((spike, i) => (
            <div className="row-card spike" key={i}>
              <NumberField label="Start" unit="s" value={spike.start} min={0} onChange={(start) => setSpike(i, { start })} />
              <NumberField label="Length" unit="s" value={spike.duration} positive onChange={(duration) => setSpike(i, { duration })} />
              <NumberField label="Traffic" unit="×" value={spike.multiplier} positive onChange={(multiplier) => setSpike(i, { multiplier })} />
              <button
                className="icon"
                aria-label="Remove spike"
                title="Remove spike"
                onClick={() => setWorkload({ spikes: workload.spikes.filter((_, j) => j !== i) })}
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      </section>

      <section>
        <div className="subsection-head">
          <h3>Stages</h3>
          <button className="link" onClick={addStage}>
            + Add stage
          </button>
        </div>
        <p className="hint">Events flow through these in order. Each stage is a queue plus a pool of workers.</p>
        {stages.map((stage, i) => (
          <div className="row-card stage" key={i}>
            <div className="stage-head">
              <span className="stage-index">{i + 1}</span>
              <input
                className="stage-name"
                aria-label="Stage name"
                value={stage.name}
                onChange={(e) => setStage(i, { name: e.target.value })}
              />
              <div className="stage-actions">
                <button className="icon" aria-label="Move up" title="Move up" disabled={i === 0} onClick={() => moveStage(i, -1)}>
                  ↑
                </button>
                <button
                  className="icon"
                  aria-label="Move down"
                  title="Move down"
                  disabled={i === stages.length - 1}
                  onClick={() => moveStage(i, 1)}
                >
                  ↓
                </button>
                <button
                  className="icon"
                  aria-label="Remove stage"
                  title="Remove stage"
                  disabled={stages.length === 1}
                  onClick={() => removeStage(i)}
                >
                  ✕
                </button>
              </div>
            </div>
            <div className="field-grid three">
              <NumberField label="Workers" value={stage.workers} min={1} integer onChange={(workers) => setStage(i, { workers })} />
              <NumberField
                label="Time per event"
                unit="s"
                value={stage.service_time}
                positive
                onChange={(service_time) => setStage(i, { service_time })}
              />
              <label className="field">
                <span>Timing</span>
                <select value={stage.service} onChange={(e) => setStage(i, { service: e.target.value as ServicePattern })}>
                  <option value="exponential">Varies</option>
                  <option value="constant">Fixed</option>
                </select>
              </label>
            </div>
          </div>
        ))}
      </section>

      <section>
        <h3>Compare</h3>
        <p className="hint">Run several worker counts for one stage side by side.</p>
        <div className="field-grid">
          <label className="field">
            <span>Vary workers at</span>
            <select value={compare.stage} onChange={(e) => onCompareChange({ ...compare, stage: e.target.value })}>
              <option value="">Don't compare</option>
              {stages.map((s) => (
                <option key={s.name} value={s.name}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Worker counts</span>
            <input
              value={compare.values}
              disabled={!compare.stage}
              placeholder="e.g. 10, 20, 30"
              onChange={(e) => onCompareChange({ ...compare, values: e.target.value })}
            />
          </label>
        </div>
      </section>
    </div>
  )
}

interface NumberFieldProps<T extends number | null> {
  label: string
  value: T
  onChange: (value: T) => void
  unit?: string
  min?: number // inclusive
  positive?: boolean // must be > 0
  integer?: boolean
  optional?: boolean
  placeholder?: string
}

/** A number input that lets you type freely and only commits valid values. */
function NumberField<T extends number | null>({
  label,
  value,
  onChange,
  unit,
  min,
  positive,
  integer,
  optional,
  placeholder,
}: NumberFieldProps<T>) {
  const [text, setText] = useState(value == null ? '' : String(value))
  useEffect(() => {
    // Sync when the value changes from outside (e.g. loading an example).
    setText((current) => (Number(current) === value && current !== '' ? current : value == null ? '' : String(value)))
  }, [value])

  const parsed = text.trim() === '' ? null : Number(text)
  const invalid =
    parsed === null
      ? !optional
      : !Number.isFinite(parsed) ||
        (positive === true && parsed <= 0) ||
        (min !== undefined && parsed < min) ||
        (integer === true && !Number.isInteger(parsed))

  return (
    <label className={`field${invalid ? ' invalid' : ''}`}>
      <span>{label}</span>
      <span className="input-wrap">
        <input
          inputMode="decimal"
          value={text}
          placeholder={placeholder}
          aria-invalid={invalid}
          onChange={(e) => {
            const t = e.target.value
            setText(t)
            const n = t.trim() === '' ? null : Number(t)
            if (n === null) {
              if (optional) onChange(null as T)
            } else if (Number.isFinite(n)) {
              onChange(n as T)
            }
          }}
        />
        {unit && <span className="unit">{unit}</span>}
      </span>
    </label>
  )
}
