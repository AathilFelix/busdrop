/* Typed client for the BusDrop engine (FastAPI, proxied at /api/*). */

export interface StopMeta {
  name: string;
  shared: boolean;
  lat: number;
  lon: number;
}

export interface RouteMeta {
  name: string;
  short: string;
  stop_ids: string[];
}

export interface Scenario {
  id: string;
  label: string;
  seed: number;
}

export interface Corridor {
  minutes: number;
  start_hour: number;
  scenarios: Scenario[];
  stops: Record<string, StopMeta>;
  routes: Record<string, RouteMeta>;
}

export interface BusFrame {
  route: string;
  lat: number;
  lon: number;
  onboard: number;
  capacity: number;
  start: number;
}

export interface HandoffEvent {
  from_bus: string;
  to_bus: string;
  stop_id: string;
  riders: number;
  explanation: string;
}

export interface Frame {
  minute: number;
  buses: Record<string, BusFrame>;
  queues: Record<string, number>;
  denied: number;
  handoffs: HandoffEvent[];
}

export interface RunResult {
  total: number;
  boarded: number;
  alighted: number;
  unserved: number;
  denied: number;
  wait: number;
  peak: number;
  events: number;
  moved: number;
  approved: number;
  rejected: number;
  offers: number;
  declines: number;
  denied_by_route: Record<string, number>;
  avg_load_by_route: Record<string, number>;
  peak_load_by_route: Record<string, number>;
}

export interface Move extends HandoffEvent {
  minute: number;
}

export interface VoiceSignal {
  minute: number;
  text: string;
  language: string;
  level: string;
  stop_id: string | null;
}

export interface LogEntry {
  minute: number;
  stop_id: string;
  from_bus: string;
  to_bus: string;
  rider_ids: string[];
  declined_ids: string[];
  destinations: string[];
  explanation: string;
  approved: boolean;
}

export interface RunData {
  result: RunResult;
  frames: Frame[];
  moves: Move[];
  voice: VoiceSignal[];
  log: LogEntry[];
}

export type DispatcherKind = "scripted" | "spark";

export async function fetchHealth(): Promise<{ ok: boolean; spark: boolean }> {
  const res = await fetch("/api/health", { cache: "no-store" });
  if (!res.ok) throw new Error(`engine health ${res.status}`);
  return res.json();
}

export async function fetchCorridor(): Promise<Corridor> {
  const res = await fetch("/api/corridor", { cache: "no-store" });
  if (!res.ok) throw new Error(`corridor ${res.status}`);
  return res.json();
}

export async function postRun(
  seed: number,
  dispatcher: DispatcherKind | "baseline",
  riders: boolean,
  voice: boolean,
  signal?: AbortSignal,
): Promise<RunData> {
  const res = await fetch("/api/run", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ seed, dispatcher, riders, voice }),
    signal,
  });
  if (res.status === 502) {
    const body = await res.json().catch(() => ({}));
    throw new SparkError(body.detail || "Muse Spark is unreachable.");
  }
  if (!res.ok) throw new Error(`run ${res.status}`);
  return res.json();
}

export class SparkError extends Error {}
