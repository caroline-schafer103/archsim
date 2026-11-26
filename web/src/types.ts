// Mirrors src/archsim/models.py. The API speaks exactly these shapes.

export type ArrivalPattern = 'constant' | 'poisson'
export type ServicePattern = 'constant' | 'exponential'

export interface Spike {
  start: number
  duration: number
  multiplier: number
}

export interface Workload {
  rate: number
  duration: number
  arrivals: ArrivalPattern
  seed: number | null
  spikes: Spike[]
}

export interface Stage {
  name: string
  workers: number
  service_time: number
  service: ServicePattern
}

export interface SimConfig {
  name: string
  workload: Workload
  stages: Stage[]
}

export interface Sample {
  time: number
  queue_depth: number
  busy_workers: number
}

export interface StageResults {
  name: string
  workers: number
  capacity: number
  completed: number
  in_queue_at_end: number
  in_progress_at_end: number
  avg_queue_depth: number
  max_queue_depth: number
  avg_wait_time: number
  avg_processing_time: number
  utilization: number
  timeseries: Sample[]
}

export interface Bottleneck {
  stage: string
  utilization: number
  wait_share: number
}

export interface SimResults {
  config: SimConfig
  generated: number
  completed: number
  in_queue_at_end: number
  in_progress_at_end: number
  avg_queue_depth: number
  max_queue_depth: number
  avg_wait_time: number
  avg_processing_time: number
  avg_latency: number
  p50_latency: number
  p95_latency: number
  p99_latency: number
  throughput: number
  spike_recovery: (number | null)[]
  stages: StageResults[]
  bottleneck: Bottleneck | null
  timeseries: Sample[]
}

export interface Example {
  id: string
  title: string
  description: string
  config: SimConfig
}
