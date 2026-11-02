"use client";

import type { Corridor, Frame, RunData } from "../lib/api";
import { clock, langName, lastBefore, plural } from "../lib/corridor";
import styles from "./SeatRail.module.css";

export type Seat = "ride" | "dispatch" | "city";

interface Props {
  seat: Seat;
  corridor: Corridor;
  withRun: RunData;
  withoutRun: RunData;
  withFrame: Frame | null;
  minute: number;
}

function destName(corridor: Corridor, dests: string[]): string {
  if (dests.length === 0) return "your destination";
  return corridor.stops[dests[0]]?.name ?? dests[0];
}

export default function SeatRail({
  seat,
  corridor,
  withRun,
  withoutRun,
  withFrame,
  minute,
}: Props) {
  if (seat === "dispatch") return <DispatchSeat corridor={corridor} run={withRun} />;
  if (seat === "city")
    return <CitySeat corridor={corridor} withRun={withRun} withoutRun={withoutRun} />;
  return (
    <RideSeat
      corridor={corridor}
      run={withRun}
      frame={withFrame}
      minute={minute}
    />
  );
}

function RideSeat({
  corridor,
  run,
  frame,
  minute,
}: {
  corridor: Corridor;
  run: RunData;
  frame: Frame | null;
  minute: number;
}) {
  const move = run.moves.length > 0 ? run.moves[0] : null;
  const rescue =
    run.log.find((e) => e.approved && e.rider_ids.length > e.declined_ids.length) ??
    null;
  const note = lastBefore(run.voice, minute);
  if (!move || !rescue) {
    return (
      <div className={styles.rail}>
        <h2>You rode straight through.</h2>
        <p>Nothing overflowed this morning — no rescue needed.</p>
      </div>
    );
  }
  const fromRoute = move.from_bus.split("-")[0];
  const toRoute = move.to_bus.split("-")[0];
  const stopName = corridor.stops[move.stop_id]?.name ?? move.stop_id;
  const walked = minute >= move.minute;
  const queue = frame?.queues[move.stop_id] ?? 0;
  return (
    <div className={styles.rail}>
      <h2>Your seat</h2>
      <div className={styles.ticket}>
        <span className={styles.ticketTo}>
          → {destName(corridor, rescue.destinations)}
        </span>
        <span className={styles.ticketMeta}>
          {move.from_bus} · {stopName} · {clock(corridor.start_hour, move.minute)}
        </span>
      </div>
      <p className={styles.status} aria-live="polite">
        {walked ? (
          <>
            You walked to the {corridor.routes[toRoute]?.short ?? toRoute}{" "}
            bus — same ticket, no extra fare. One of {move.riders} who walked.
          </>
        ) : queue === 0 ? (
          <>
            No queue yet at {stopName} — the crush builds toward{" "}
            {clock(corridor.start_hour, move.minute)}. Press play.
          </>
        ) : (
          <>
            Waiting at {stopName} — <span className="tnum">{queue}</span> in
            the queue with you. Your bus, {move.from_bus} (
            {corridor.routes[fromRoute]?.short ?? fromRoute}), is full.
          </>
        )}
      </p>
      {note && (
        <p className={styles.note}>
          Driver note ({langName(note.language)}): {note.text}
        </p>
      )}
    </div>
  );
}

function DispatchSeat({
  corridor,
  run,
}: {
  corridor: Corridor;
  run: RunData;
}) {
  if (run.log.length === 0) {
    return (
      <div className={styles.rail}>
        <h2>The dispatch desk</h2>
        <p>No proposals — nothing overflowed this morning.</p>
      </div>
    );
  }
  return (
    <div className={styles.rail}>
      <h2>The dispatch desk</h2>
      <ol className={styles.feed}>
        {run.log.map((e, i) => {
          const fromRoute = e.from_bus.split("-")[0];
          const toRoute = e.to_bus.split("-")[0];
          const walked = e.rider_ids.length - e.declined_ids.length;
          return (
            <li key={`${e.minute}-${i}`}>
              <p className={styles.feedHead}>
                <time className="tnum">
                  {clock(corridor.start_hour, e.minute)}
                </time>{" "}
                {corridor.routes[fromRoute]?.short ?? fromRoute} →{" "}
                {corridor.routes[toRoute]?.short ?? toRoute} ·{" "}
                {corridor.stops[e.stop_id]?.name ?? e.stop_id}
              </p>
              <p className={styles.feedMeta}>
                {!e.approved
                  ? "blocked — no one moved"
                  : walked === 0
                    ? `${e.rider_ids.length} ${plural(e.rider_ids.length, "rider", "riders")} offered · all stayed`
                    : `${walked} ${plural(walked, "rider", "riders")} walked${
                        e.declined_ids.length > 0
                          ? ` · ${e.declined_ids.length} stayed`
                          : ""
                      }`}
              </p>
              {e.explanation && (
                <p className={styles.feedNote}>{e.explanation}</p>
              )}
              <span
                className={`${styles.stamp} ${e.approved ? styles.ok : styles.blocked}`}
              >
                {e.approved ? "Approved" : "Blocked"}
              </span>
            </li>
          );
        })}
      </ol>
      <p className={styles.footnote}>
        Every proposal clears four deterministic checks — destination, ETA
        window, capacity, ticket — before anyone moves.
      </p>
    </div>
  );
}

function CitySeat({
  corridor,
  withRun,
  withoutRun,
}: {
  corridor: Corridor;
  withRun: RunData;
  withoutRun: RunData;
}) {
  const res = withRun.result;
  const base = withoutRun.result;
  const saved = base.denied - res.denied;
  return (
    <div className={styles.rail}>
      <h2>The city ledger</h2>
      <ul className={styles.numbers}>
        <li>
          <strong className="tnum">{res.denied}</strong> left behind
          <span className="tnum">
            {" "}
            ({saved >= 0 ? `−${saved}` : `+${-saved}`} vs without)
          </span>
        </li>
        <li>
          <strong className="tnum">{res.wait.toFixed(1)} min</strong> average
          wait
          <span className="tnum">
            {" "}
            ({(res.wait - base.wait >= 0 ? "+" : "") +
              (res.wait - base.wait).toFixed(1)}
            )
          </span>
        </li>
        <li>
          <strong className="tnum">{Math.round(res.peak * 100)}%</strong>{" "}
          fullest bus
          <span className="tnum">
            {" "}
            ({Math.round((res.peak - base.peak) * 100)} pts)
          </span>
        </li>
      </ul>
      <ul className={styles.routes}>
        {Object.keys(base.denied_by_route)
          .sort()
          .map((rid) => (
            <li key={rid}>
              {rid} ({corridor.routes[rid]?.short ?? rid}){" "}
              <span className="tnum">
                {base.denied_by_route[rid]} → {res.denied_by_route[rid] ?? 0}
              </span>
            </li>
          ))}
      </ul>
    </div>
  );
}
