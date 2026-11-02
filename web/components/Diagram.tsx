"use client";

import { useMemo } from "react";
import type { Corridor, Frame } from "../lib/api";
import {
  ROUTE_COLORS,
  busColor,
  clock,
  loadWord,
  makeProjector,
  offsetPoints,
  waitingNow,
} from "../lib/corridor";
import styles from "./Diagram.module.css";

const W = 1000;
const H = 620;
const TRUNK = ["THL", "LIC", "SIM", "CEN", "BWY"];
const ROUTE_OFFSET: Record<string, number> = { R1: -10, R2: 0, R3: 10 };

interface LabelCfg {
  pos: "above" | "below" | "left" | "right";
  branch?: boolean;
}
const LABELS: Record<string, LabelCfg> = {
  ROY: { pos: "left", branch: true },
  PYC: { pos: "above", branch: true },
  TEY: { pos: "below", branch: true },
  SIE: { pos: "below", branch: true },
  GEM: { pos: "above", branch: true },
  THL: { pos: "above" },
  LIC: { pos: "below" },
  SIM: { pos: "above" },
  CEN: { pos: "below" },
  BWY: { pos: "right" },
};

function dOf(pts: Array<{ x: number; y: number }>): string {
  return pts
    .map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(1)} ${p.y.toFixed(1)}`)
    .join(" ");
}

interface Props {
  corridor: Corridor;
  frame: Frame | null;
  minute: number;
  movedSoFar: number;
}

export default function Diagram({ corridor, frame, minute, movedSoFar }: Props) {
  const geo = useMemo(() => {
    const proj = makeProjector(corridor, W, H);
    const at = (sid: string) => {
      const s = corridor.stops[sid];
      return { x: proj.x(s.lon, s.lat), y: proj.y(s.lon, s.lat) };
    };
    const stopXY: Record<string, { x: number; y: number }> = {};
    for (const sid of Object.keys(corridor.stops)) stopXY[sid] = at(sid);
    const branches: Record<string, string> = {};
    for (const [rid, route] of Object.entries(corridor.routes)) {
      const end = route.stop_ids.indexOf("THL");
      branches[rid] = dOf(route.stop_ids.slice(0, end + 1).map(at));
    }
    const trunkCenter = TRUNK.map(at);
    const trunk: Record<string, string> = {};
    for (const rid of Object.keys(corridor.routes)) {
      trunk[rid] = dOf(offsetPoints(trunkCenter, ROUTE_OFFSET[rid] ?? 0));
    }
    // Trunk tangent at each stop, for hop arcs.
    const tangent: Record<string, { x: number; y: number }> = {};
    trunkCenter.forEach((p, i) => {
      const q = trunkCenter[Math.min(i + 1, trunkCenter.length - 1)];
      const r = trunkCenter[Math.max(i - 1, 0)];
      const dx = q.x - r.x;
      const dy = q.y - r.y;
      const len = Math.hypot(dx, dy) || 1;
      tangent[TRUNK[i]] = { x: dx / len, y: dy / len };
    });
    return { proj, stopXY, branches, trunk, trunkCenter, tangent };
  }, [corridor]);

  const buses = useMemo(() => {
    if (!frame) return [];
    return Object.entries(frame.buses).map(([bid, b]) => ({
      bid,
      route: b.route,
      x: geo.proj.x(b.lon, b.lat),
      y: geo.proj.y(b.lon, b.lat),
      load: b.onboard / b.capacity,
      onboard: b.onboard,
      capacity: b.capacity,
      started: minute >= b.start,
    }));
  }, [frame, geo, minute]);

  const waiting = frame ? waitingNow(frame.queues) : 0;
  const full = buses.filter((b) => b.started && b.load >= 1).length;
  const hops = useMemo(() => {
    if (!frame) return [];
    return frame.handoffs.map((h, i) => {
      const s = geo.stopXY[h.stop_id];
      const fromRoute = frame.buses[h.from_bus]?.route ?? "R1";
      const toRoute = frame.buses[h.to_bus]?.route ?? "R2";
      // Hop across the parallel trunk lines at this stop.
      const t = geo.tangent[h.stop_id] ?? { x: 1, y: 0 };
      const n = { x: -t.y, y: t.x };
      const a = ROUTE_OFFSET[fromRoute] ?? 0;
      const c = ROUTE_OFFSET[toRoute] ?? 0;
      const p1 = { x: s.x + n.x * a, y: s.y + n.y * a };
      const p2 = { x: s.x + n.x * c, y: s.y + n.y * c };
      const mx = (p1.x + p2.x) / 2;
      const my = (p1.y + p2.y) / 2;
      return {
        key: `${minute}-${h.stop_id}-${i}`,
        stop_id: h.stop_id,
        riders: h.riders,
        toRoute,
        arc: `M${p1.x.toFixed(1)} ${p1.y.toFixed(1)} Q${mx.toFixed(1)} ${(my - 44).toFixed(1)} ${p2.x.toFixed(1)} ${p2.y.toFixed(1)}`,
        x: s.x,
        y: s.y,
      };
    });
  }, [frame, geo, minute]);

  const ariaLabel = frame
    ? `${clock(corridor.start_hour, minute)}: ${waiting} riders waiting, ${full} buses full, ${movedSoFar} moved so far.`
    : "Loading the morning replay.";

  return (
    <section className={styles.wrap} aria-label="Live corridor diagram">
      <div className={styles.chrome}>
        <ul className={styles.legend} aria-label="Routes">
          {Object.entries(corridor.routes).map(([rid, r]) => (
            <li key={rid}>
              <span
                className={styles.swatch}
                style={{ background: ROUTE_COLORS[rid] }}
                aria-hidden="true"
              />
              {r.short}
            </li>
          ))}
        </ul>
        <div className={styles.readout}>
          <time className="tnum" dateTime={`07:00+${minute}`}>
            {clock(corridor.start_hour, minute)}
          </time>
          <span className={styles.sub}>
            <span className="tnum">{waiting}</span> waiting ·{" "}
            <span className="tnum">{movedSoFar}</span> moved
          </span>
        </div>
      </div>

      <div className={styles.sheet}>
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className={styles.svg}
          role="img"
          aria-label={ariaLabel}
        >
          {/* queue halos */}
          {frame &&
            Object.entries(frame.queues).map(([sid, q]) =>
              q > 0 ? (
                <circle
                  key={sid}
                  cx={geo.stopXY[sid].x}
                  cy={geo.stopXY[sid].y}
                  r={10 + Math.min(q, 40) * 0.8}
                  className={styles.halo}
                />
              ) : null,
            )}
          {/* branch lines */}
          {Object.entries(geo.branches).map(([rid, d], i) => (
            <path
              key={rid}
              d={d}
              className={styles.branch}
              style={{
                stroke: ROUTE_COLORS[rid],
                animationDelay: `${i * 0.12}s`,
              }}
              pathLength={1}
              fill="none"
            />
          ))}
          {/* trunk bundle: ink casing, then three parallel lines */}
          <path
            d={dOf(geo.trunkCenter)}
            className={styles.casing}
            pathLength={1}
            fill="none"
          />
          <path
            d={dOf(geo.trunkCenter)}
            className={styles.casingInner}
            pathLength={1}
            fill="none"
          />
          {Object.entries(geo.trunk).map(([rid, d], i) => (
            <path
              key={rid}
              d={d}
              className={styles.trunk}
              style={{
                stroke: ROUTE_COLORS[rid],
                animationDelay: `${0.3 + i * 0.12}s`,
              }}
              pathLength={1}
              fill="none"
            />
          ))}
          {/* stops */}
          {Object.entries(corridor.stops).map(([sid, s]) => {
            const p = geo.stopXY[sid];
            if (!s.shared) {
              const rid = Object.keys(corridor.routes).find((r) =>
                corridor.routes[r].stop_ids.includes(sid),
              );
              return (
                <circle
                  key={sid}
                  cx={p.x}
                  cy={p.y}
                  r={6}
                  fill={ROUTE_COLORS[rid ?? "R1"]}
                  stroke="var(--ink)"
                  strokeWidth={1.5}
                />
              );
            }
            const terminus = sid === "BWY";
            return (
              <g key={sid}>
                <circle
                  cx={p.x}
                  cy={p.y}
                  r={terminus ? 10 : 9}
                  className={styles.interchange}
                />
                {terminus && <circle cx={p.x} cy={p.y} r={3.2} fill="var(--ink)" />}
              </g>
            );
          })}
          {/* handoff pulses + hop arcs */}
          {hops.map((h) => (
            <g key={h.key}>
              <circle cx={h.x} cy={h.y} r={9} className={styles.ping} />
              <path
                d={h.arc}
                className={styles.hop}
                pathLength={1}
                fill="none"
              />
              <circle cx={h.x} cy={h.y} r={4.5} className={styles.hopDot} />
            </g>
          ))}
          {/* buses */}
          {buses.map((b) => (
            <g
              key={b.bid}
              className={b.started ? styles.bus : styles.busDepot}
              style={{ transform: `translate(${b.x}px, ${b.y}px)` }}
            >
              <title>
                {b.bid} · {b.onboard}/{b.capacity} {loadWord(b.load)}
              </title>
              <circle r={b.started ? 8 : 4.5} fill={busColor(b.load, b.route)} />
            </g>
          ))}
        </svg>

        {/* stop labels live in HTML so they never shrink with the viewBox */}
        {Object.entries(corridor.stops).map(([sid, s]) => {
          const p = geo.stopXY[sid];
          const cfg = LABELS[sid];
          return (
            <span
              key={sid}
              className={`${styles.stopLabel} ${styles[cfg.pos]}${cfg.branch ? ` ${styles.branchLabel}` : ""}`}
              style={{ left: `${(p.x / W) * 100}%`, top: `${(p.y / H) * 100}%` }}
            >
              {s.name}
            </span>
          );
        })}

        {/* handoff tags */}
        {frame &&
          hops.map((h) => (
            <span
              key={h.key}
              className={styles.hopTag}
              style={{
                left: `${(h.x / W) * 100}%`,
                top: `${(h.y / H) * 100}%`,
              }}
            >
              {h.riders} → {corridor.routes[h.toRoute]?.short ?? h.toRoute}
            </span>
          ))}

        {!frame && (
          <div className={styles.veil} role="status">
            Assembling the morning…
          </div>
        )}
      </div>
    </section>
  );
}
