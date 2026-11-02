"use client";

import { useEffect, useMemo, useState } from "react";
import type { Corridor, RunData } from "../lib/api";
import {
  ROUTE_COLORS,
  clock,
  loadWord,
  makeProjector,
  offsetPoints,
  plural,
} from "../lib/corridor";
import styles from "./CrushClock.module.css";

const TRUNK = ["THL", "LIC", "SIM", "CEN", "BWY"];
const ECHO_OFFSETS = [-10, 0, 10];

interface Props {
  corridor: Corridor;
  withRun: RunData | null;
  withoutRun: RunData | null;
  loading: boolean;
  onPlayRescue: (minute: number) => void;
}

export default function CrushClock({
  corridor,
  withRun,
  withoutRun,
  loading,
  onPlayRescue,
}: Props) {
  const res = withRun?.result ?? null;
  const base = withoutRun?.result ?? null;
  const saved = res && base ? base.denied - res.denied : 0;

  const move = withRun && withRun.moves.length > 0 ? withRun.moves[0] : null;
  const frame = withRun && move ? (withRun.frames[move.minute] ?? null) : null;
  const bus = frame && move ? (frame.buses[move.from_bus] ?? null) : null;
  const rescue =
    withRun?.log.find(
      (e) => e.approved && e.rider_ids.length > e.declined_ids.length,
    ) ?? null;
  // The queue drains as the rescue lands, so stage the peak pressure from
  // the run-up window — the number that forced the move.
  let queuePeak = 0;
  if (withRun && move) {
    for (let m = Math.max(0, move.minute - 10); m <= move.minute; m++) {
      const f = withRun.frames[m];
      if (f) queuePeak = Math.max(queuePeak, f.queues[move.stop_id] ?? 0);
    }
  }

  const ready = !loading && withRun && res && base;
  const staged = ready && move && frame && bus && rescue;

  // The waiting count ticks up once the rescue stages; reduced-motion
  // readers get the final figure immediately.
  const stagedKey = staged && move ? `${move.minute}-${queuePeak}` : null;
  const [tickKey, setTickKey] = useState<string | null>(null);
  const [ticked, setTicked] = useState(0);
  if (stagedKey !== tickKey) {
    setTickKey(stagedKey);
    setTicked(0);
  }
  const calm =
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  useEffect(() => {
    if (stagedKey === null || calm) return;
    let raf = 0;
    const t0 = performance.now();
    const dur = 900;
    const step = (t: number) => {
      const p = Math.min(1, (t - t0) / dur);
      setTicked(Math.round(queuePeak * (1 - Math.pow(1 - p, 3))));
      if (p < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [stagedKey, queuePeak, calm]);
  const shownWaiting = calm ? queuePeak : ticked;

  // Faint echo of the real trunk geometry behind the meter.
  const echo = useMemo(() => {
    const proj = makeProjector(corridor, 600, 220);
    const center = TRUNK.map((sid) => {
      const s = corridor.stops[sid];
      return { x: proj.x(s.lon, s.lat), y: proj.y(s.lon, s.lat) };
    });
    return ECHO_OFFSETS.map((d) =>
      offsetPoints(center, d)
        .map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(1)} ${p.y.toFixed(1)}`)
        .join(" "),
    );
  }, [corridor]);

  const fromRoute = move ? move.from_bus.split("-")[0] : "";
  const toRoute = move ? move.to_bus.split("-")[0] : "";
  const stopName = move
    ? (corridor.stops[move.stop_id]?.name ?? move.stop_id)
    : "";
  const destLead =
    rescue && rescue.destinations.length > 0
      ? (corridor.stops[rescue.destinations[0]]?.name ??
        rescue.destinations[0])
      : null;
  const destMore =
    rescue && rescue.destinations.length > 1
      ? rescue.destinations.length - 1
      : 0;

  return (
    <section className={styles.crush} aria-label="The morning's rescue">
      <h1>Your ticket belongs to your destination, not to one bus.</h1>
      <p className={styles.deck}>
        When one Chennai bus overflows, BusDrop moves riders mid-route to a
        roomier bus going the same way — same ticket, no extra fare. This
        morning, one bus is about to boil over.
      </p>

      {!ready || !withRun ? (
        <div className={styles.meter} role="status">
          Assembling the morning…
        </div>
      ) : staged && move && bus && rescue ? (
        <div className={styles.meter}>
          <svg
            className={styles.echo}
            viewBox="0 0 600 220"
            preserveAspectRatio="xMidYMid slice"
            aria-hidden="true"
          >
            {echo.map((d, i) => (
              <path
                key={i}
                d={d}
                fill="none"
                stroke={["var(--r1)", "var(--r2)", "var(--r3)"][i]}
                strokeWidth={7 - i}
              />
            ))}
          </svg>
          <div className={styles.figure}>
            <span className={`tnum ${styles.count}`}>
              {bus.onboard}/{bus.capacity}
            </span>
            <span className={styles.word}>
              {loadWord(bus.onboard / bus.capacity)}
            </span>
            <span className={styles.busId}>
              <i
                aria-hidden="true"
                style={{ background: ROUTE_COLORS[fromRoute] }}
              />
              {move.from_bus} ·{" "}
              {corridor.routes[fromRoute]?.short ?? fromRoute}
            </span>
          </div>
          <div className={styles.rail}>
            <p className="tnum">
              {clock(corridor.start_hour, move.minute)} · {stopName}
            </p>
            <p className="tnum">
              {shownWaiting} waiting · {move.riders}{" "}
              {plural(move.riders, "rider", "riders")} walked to the{" "}
              {corridor.routes[toRoute]?.short ?? toRoute} bus
            </p>
            {destLead && (
              <p>
                tickets to <strong>{destLead}</strong>
                {destMore > 0 && ` +${destMore} more`}
              </p>
            )}
            <button
              type="button"
              className={styles.play}
              onClick={() => onPlayRescue(Math.max(0, move.minute - 10))}
            >
              Play the rescue
            </button>
          </div>
        </div>
      ) : (
        <div className={styles.meter}>
          <div className={styles.figure}>
            <span className={`tnum ${styles.count}`}>
              {Math.round((res?.peak ?? 0) * 100)}%
            </span>
            <span className={styles.word}>peak load</span>
          </div>
          <div className={styles.rail}>
            <p>The morning never boiled over — nothing overflowed.</p>
            <button
              type="button"
              className={styles.play}
              onClick={() => onPlayRescue(0)}
            >
              Replay the morning
            </button>
          </div>
        </div>
      )}

      {res && base && (
        <p className={styles.stakes} aria-live="polite">
          This morning: <strong className="tnum">{res.moved}</strong>{" "}
          {plural(res.moved, "rider", "riders")} moved ·{" "}
          <strong className="tnum">{saved}</strong> fewer left behind
        </p>
      )}
    </section>
  );
}
