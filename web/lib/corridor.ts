/* Corridor math: clock, load words, and the schematic projection.
   Schematics are not north-up: the projection rotates the trunk (THL->BWY)
   onto the horizontal so branches fan left and the spine runs right. */

import type { Corridor } from "./api";

export const ROUTE_COLORS: Record<string, string> = {
  R1: "var(--r1)",
  R2: "var(--r2)",
  R3: "var(--r3)",
};

export function clock(startHour: number, minute: number): string {
  const h = startHour + Math.floor(minute / 60);
  const m = minute % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

export type LoadWord = "Roomy" | "Busy" | "Packed" | "Full";

export function loadWord(load: number): LoadWord {
  if (load >= 1.0) return "Full";
  if (load >= 0.85) return "Packed";
  if (load >= 0.6) return "Busy";
  return "Roomy";
}

export function busColor(load: number, route: string): string {
  if (load >= 1.0) return "var(--ink)";
  if (load >= 0.85) return "var(--stamp-deep)";
  return ROUTE_COLORS[route] ?? "var(--ink)";
}

export interface Projector {
  x: (lon: number, lat: number) => number;
  y: (lon: number, lat: number) => number;
  width: number;
  height: number;
}

/** Build a trunk-horizontal projector for a viewBox of w x h. */
export function makeProjector(
  corridor: Corridor,
  w: number,
  h: number,
  pad = 70,
): Projector {
  const pts = Object.values(corridor.stops);
  // Rotate so the THL->BWY trunk axis lies flat.
  const a = corridor.stops["THL"];
  const b = corridor.stops["BWY"];
  const angle = Math.atan2(b.lat - a.lat, b.lon - a.lon);
  const rot = (lon: number, lat: number) => {
    const dx = lon - a.lon;
    const dy = lat - a.lat;
    return {
      u: dx * Math.cos(-angle) - dy * Math.sin(-angle),
      v: dx * Math.sin(-angle) + dy * Math.cos(-angle),
    };
  };
  const flat = pts.map((s) => rot(s.lon, s.lat));
  const us = flat.map((p) => p.u);
  const vs = flat.map((p) => p.v);
  const minU = Math.min(...us);
  const maxU = Math.max(...us);
  const minV = Math.min(...vs);
  const maxV = Math.max(...vs);
  const scale = Math.min(
    (w - pad * 2) / (maxU - minU || 1),
    (h - pad * 2) / (maxV - minV || 1),
  );
  const ox = (w - scale * (maxU - minU)) / 2;
  const oy = (h - scale * (maxV - minV)) / 2;
  return {
    width: w,
    height: h,
    x: (lon, lat) => ox + (rot(lon, lat).u - minU) * scale,
    y: (lon, lat) => oy + (rot(lon, lat).v - minV) * scale,
  };
}

/** Offset a trunk polyline sideways so parallel routes don't overlap. */
export function offsetPoints(
  pts: Array<{ x: number; y: number }>,
  dist: number,
): Array<{ x: number; y: number }> {
  return pts.map((p, i) => {
    const q = pts[Math.min(i + 1, pts.length - 1)];
    const r = pts[Math.max(i - 1, 0)];
    const dx = q.x - r.x;
    const dy = q.y - r.y;
    const len = Math.hypot(dx, dy) || 1;
    return { x: p.x + (-dy / len) * dist, y: p.y + (dx / len) * dist };
  });
}

export function polyline(pts: Array<{ x: number; y: number }>): string {
  return pts.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");
}

export function waitingNow(queues: Record<string, number>): number {
  return Object.values(queues).reduce((a, b) => a + b, 0);
}

export function plural(n: number, one: string, many: string): string {
  return n === 1 ? one : many;
}

export function lastBefore<T extends { minute: number }>(
  items: T[],
  minute: number,
): T | null {
  let found: T | null = null;
  for (const item of items) {
    if (item.minute > minute) break;
    found = item;
  }
  return found;
}

const LANG: Record<string, string> = {
  ta: "Tamil",
  en: "English",
  mixed: "Tamil/English",
};

export function langName(code: string): string {
  return LANG[code] ?? code;
}
