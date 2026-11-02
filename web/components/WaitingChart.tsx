"use client";

import { useEffect, useRef, useState } from "react";
import type { Frame } from "../lib/api";
import { clock, waitingNow } from "../lib/corridor";

const H = 230;
const PAD_L = 42;
const PAD_B = 26;
const PAD_T = 14;

interface Props {
  withFrames: Frame[];
  withoutFrames: Frame[];
  startHour: number;
}

export default function WaitingChart({
  withFrames,
  withoutFrames,
  startHour,
}: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const update = () => setWidth(Math.max(280, el.clientWidth));
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  if (withFrames.length === 0 || width === 0) return <div ref={ref} />;

  const a = withFrames.map((f) => waitingNow(f.queues));
  const b = withoutFrames.map((f) => waitingNow(f.queues));
  const maxV = Math.max(10, ...a, ...b);
  const n = Math.max(a.length, b.length);
  const x = (i: number) => PAD_L + (i / (n - 1)) * (width - PAD_L - 12);
  const y = (v: number) => PAD_T + (1 - v / maxV) * (H - PAD_T - PAD_B);
  const line = (s: number[]) =>
    s.map((v, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(" ");
  const ticks = [0, Math.round(maxV / 2), maxV];
  const times = withFrames
    .map((f, i) => ({ f, i }))
    .filter(({ f }) => f.minute % 30 === 0);
  const peak = (s: number[]) => Math.max(...s);

  return (
    <div ref={ref}>
      <svg
        width="100%"
        height={H}
        viewBox={`0 0 ${width} ${H}`}
        role="img"
        aria-label={`Riders waiting: peaks at ${peak(b)} without BusDrop, ${peak(a)} with.`}
      >
        {ticks.map((t) => (
          <g key={t}>
            <line
              x1={PAD_L}
              x2={width - 12}
              y1={y(t)}
              y2={y(t)}
              stroke="var(--hairline)"
              strokeWidth={1}
            />
            <text
              x={PAD_L - 8}
              y={y(t) + 4}
              textAnchor="end"
              className="chartTick"
            >
              {t}
            </text>
          </g>
        ))}
        {times.map(({ f, i }) => (
          <text key={f.minute} x={x(i)} y={H - 8} textAnchor="middle" className="chartTick">
            {clock(startHour, f.minute)}
          </text>
        ))}
        <path d={line(b)} fill="none" stroke="#8a939c" strokeWidth={2} strokeDasharray="5 4" />
        <path d={line(a)} fill="none" stroke="var(--ink)" strokeWidth={2.5} />
        <circle cx={x(a.length - 1)} cy={y(a[a.length - 1])} r={3.5} fill="var(--ink)" />
        <circle cx={x(b.length - 1)} cy={y(b[b.length - 1])} r={3.5} fill="#8a939c" />
      </svg>
    </div>
  );
}
