"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import CrushClock from "../components/CrushClock";
import Diagram from "../components/Diagram";
import SeatRail, { type Seat } from "../components/SeatRail";
import WaitingChart from "../components/WaitingChart";
import {
  SparkError,
  fetchCorridor,
  fetchHealth,
  postRun,
  type Corridor,
  type DispatcherKind,
  type Move,
  type RunData,
  type VoiceSignal,
} from "../lib/api";
import { clock, langName, lastBefore, plural } from "../lib/corridor";
import styles from "./page.module.css";

type View = "with" | "without";

export default function Page() {
  const [corridor, setCorridor] = useState<Corridor | null>(null);
  const [engineDown, setEngineDown] = useState(false);
  const [sparkAvailable, setSparkAvailable] = useState<boolean | null>(null);

  const [scenarioId, setScenarioId] = useState("morning");
  const [dispatcher, setDispatcher] = useState<DispatcherKind>("scripted");
  const [ridersOn, setRidersOn] = useState(true);
  const [voiceOn, setVoiceOn] = useState(true);
  const [view, setView] = useState<View>("with");

  const [withRun, setWithRun] = useState<RunData | null>(null);
  const [withoutRun, setWithoutRun] = useState<RunData | null>(null);
  const [runsLoading, setRunsLoading] = useState(false);
  const [runsFailed, setRunsFailed] = useState(false);
  const [sparkNotice, setSparkNotice] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  const [minute, setMinute] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [seat, setSeat] = useState<Seat>("ride");
  const abortRef = useRef<AbortController | null>(null);
  const consoleRef = useRef<HTMLElement | null>(null);

  // Boot: engine health + corridor geography.
  useEffect(() => {
    let alive = true;
    fetchHealth()
      .then((h) => alive && setSparkAvailable(h.spark))
      .catch(() => alive && setSparkAvailable(null));
    fetchCorridor()
      .then((c) => alive && setCorridor(c))
      .catch(() => alive && setEngineDown(true));
    return () => {
      alive = false;
    };
  }, []);

  // Reset the run UI the moment a fetch input changes. This render-time
  // adjustment (React docs: "storing information from previous renders")
  // keeps the fetch effect below free of synchronous setState calls.
  const fetchKey = corridor
    ? [scenarioId, dispatcher, ridersOn, voiceOn, nonce].join("|")
    : null;
  const [prevFetchKey, setPrevFetchKey] = useState<string | null>(null);
  if (fetchKey !== prevFetchKey) {
    setPrevFetchKey(fetchKey);
    if (fetchKey !== null) {
      setRunsLoading(true);
      setRunsFailed(false);
      setSparkNotice(null);
      setPlaying(false);
    }
  }

  // Runs: the configured morning plus its no-handoff twin. Same fleet,
  // same riders; only the dispatcher differs.
  useEffect(() => {
    if (!corridor) return;
    abortRef.current?.abort();
    const ctl = new AbortController();
    abortRef.current = ctl;
    const seed = corridor.scenarios.find((s) => s.id === scenarioId)?.seed ?? 42;

    const load = async () => {
      try {
        const base = postRun(seed, "baseline", false, false, ctl.signal);
        let withP: Promise<RunData>;
        if (dispatcher === "spark") {
          withP = postRun(seed, "spark", ridersOn, voiceOn, ctl.signal).catch(
            (e) => {
              if (e instanceof SparkError) {
                setSparkNotice(e.message);
                return postRun(seed, "scripted", ridersOn, voiceOn, ctl.signal);
              }
              throw e;
            },
          );
        } else {
          withP = postRun(seed, dispatcher, ridersOn, voiceOn, ctl.signal);
        }
        const [without, withR] = await Promise.all([base, withP]);
        if (ctl.signal.aborted) return;
        setWithoutRun(without);
        setWithRun(withR);
        setMinute(0);
      } catch (e) {
        if (ctl.signal.aborted) return;
        console.error(e);
        setRunsFailed(true);
      } finally {
        if (!ctl.signal.aborted) setRunsLoading(false);
      }
    };
    load();
    return () => ctl.abort();
  }, [corridor, scenarioId, dispatcher, ridersOn, voiceOn, nonce]);

  const frames = (view === "with" ? withRun?.frames : withoutRun?.frames) ?? [];
  const horizon = Math.max(0, frames.length - 1);
  const frame = frames.length > 0 ? frames[Math.min(minute, horizon)] : null;

  // Auto-pause when the replay reaches the last frame. Render-time
  // adjustment: converges immediately since playing becomes false.
  if (playing && frames.length > 0 && minute >= horizon) {
    setPlaying(false);
  }

  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => {
      setMinute((m) => Math.min(m + 1, horizon));
    }, 140);
    return () => clearInterval(id);
  }, [playing, horizon]);

  const movedSoFar = useMemo(() => {
    if (!withRun) return 0;
    let n = 0;
    for (const f of withRun.frames) {
      if (f.minute > minute) break;
      for (const h of f.handoffs) n += h.riders;
    }
    return n;
  }, [withRun, minute]);

  const latestMove: Move | null =
    withRun && view === "with" ? lastBefore(withRun.moves, minute) : null;
  const driverNote: VoiceSignal | null =
    withRun && voiceOn && view === "with"
      ? lastBefore(withRun.voice, minute)
      : null;

  if (engineDown || !corridor) {
    return (
      <div className={styles.page}>
        <Masthead status="offline" />
        <main className={styles.main}>
          {engineDown ? (
            <section className={styles.errorCard} role="alert">
              <h1>The engine isn&rsquo;t running.</h1>
              <p>
                This page replays live simulation runs, and the Python engine
                behind it isn&rsquo;t answering. Start it from the repo root,
                then reload:
              </p>
              <pre className="tnum">.venv/bin/uvicorn api:app --port 8000</pre>
              <button type="button" onClick={() => location.reload()}>
                Retry
              </button>
            </section>
          ) : (
            <section className={styles.errorCard} role="status">
              <h1>Warming up the depot…</h1>
              <p>Reaching the simulation engine.</p>
            </section>
          )}
        </main>
      </div>
    );
  }

  const res = withRun?.result;
  const base = withoutRun?.result;
  const saved = res && base ? base.denied - res.denied : 0;

  const toggleReplay = () => {
    if (playing) {
      setPlaying(false);
    } else {
      if (minute >= horizon) setMinute(0);
      setPlaying(true);
    }
  };

  const playRescue = (at: number) => {
    setMinute(Math.max(0, Math.min(at, horizon)));
    setPlaying(true);
    const calm = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    consoleRef.current?.scrollIntoView({
      behavior: calm ? "auto" : "smooth",
      block: "start",
    });
  };

  const withFrame =
    withRun && withRun.frames.length > 0
      ? withRun.frames[Math.min(minute, withRun.frames.length - 1)]
      : null;

  const moveSentence = (m: Move) => {
    const from = m.from_bus.split("-")[0];
    const to = m.to_bus.split("-")[0];
    const stop = corridor.stops[m.stop_id]?.name ?? m.stop_id;
    return `${clock(corridor.start_hour, m.minute)}, ${stop}: ${m.riders} ${plural(m.riders, "rider", "riders")} stepped from the ${corridor.routes[from]?.short ?? from} bus to the ${corridor.routes[to]?.short ?? to} bus.`;
  };

  return (
    <div className={styles.page}>
      <Masthead status={runsFailed ? "offline" : "live"} />

      <main className={styles.main}>
        <CrushClock
          corridor={corridor}
          withRun={withRun}
          withoutRun={withoutRun}
          loading={runsLoading || !withRun}
          onPlayRescue={playRescue}
        />

        {sparkNotice && (
          <p className={styles.notice} role="status">
            Muse Spark is unreachable ({sparkNotice}). Showing Standard moves
            instead — add MODEL_API_KEY to try the AI dispatcher.
          </p>
        )}

        {runsFailed ? (
          <section className={styles.errorCard} role="alert">
            <h2>The run failed.</h2>
            <p>The engine dropped this run. It may be restarting — try again.</p>
            <button type="button" onClick={() => setNonce((n) => n + 1)}>
              Run it again
            </button>
          </section>
        ) : (
          <section
            ref={consoleRef}
            className={styles.console}
            aria-label="Replay console"
          >
            <fieldset className={styles.seats}>
              <legend>Take a seat</legend>
              {(
                [
                  ["ride", "Rider"],
                  ["dispatch", "Dispatcher"],
                  ["city", "City"],
                ] as [Seat, string][]
              ).map(([id, label]) => (
                <label key={id}>
                  <input
                    type="radio"
                    name="seat"
                    checked={seat === id}
                    onChange={() => setSeat(id)}
                  />
                  {label}
                </label>
              ))}
            </fieldset>
            <div className={styles.consoleGrid}>
              <Diagram
                corridor={corridor}
                frame={runsLoading ? null : frame}
                minute={minute}
                movedSoFar={view === "with" ? movedSoFar : 0}
              />
              {runsLoading || !withRun || !withoutRun ? (
                <div className={styles.railVeil} role="status">
                  Assembling the morning…
                </div>
              ) : (
                <SeatRail
                  seat={seat}
                  corridor={corridor}
                  withRun={withRun}
                  withoutRun={withoutRun}
                  withFrame={withFrame}
                  minute={minute}
                />
              )}
            </div>
          </section>
        )}

        {frame && !runsLoading && (
          <p className={styles.ticker} aria-live="off">
            {latestMove ? (
              <span>{moveSentence(latestMove)} </span>
            ) : (
              <span>
                {clock(corridor.start_hour, minute)} — the peak is still
                building.{" "}
              </span>
            )}
            {driverNote && (
              <span className={styles.driverNote}>
                Driver note ({langName(driverNote.language)}):{" "}
                {driverNote.text}
              </span>
            )}
          </p>
        )}

        <section className={styles.dock} aria-label="Replay controls">
          <div className={styles.transport}>
            <button
              type="button"
              className={styles.replay}
              onClick={toggleReplay}
              disabled={frames.length === 0 || runsLoading}
            >
              {playing ? "Stop" : minute >= horizon && horizon > 0 ? "Replay again" : "Replay"}
            </button>
            <input
              type="range"
              min={0}
              max={horizon}
              value={Math.min(minute, horizon)}
              onChange={(e) => {
                setMinute(Number(e.target.value));
                setPlaying(false);
              }}
              aria-label="Time of morning"
              className={styles.slider}
              disabled={frames.length === 0}
            />
            <output className={`tnum ${styles.clockOut}`}>
              {clock(corridor.start_hour, Math.min(minute, horizon))}
            </output>
          </div>
          <div className={styles.groups}>
            <fieldset>
              <legend>Morning</legend>
              {corridor.scenarios.map((s) => (
                <label key={s.id}>
                  <input
                    type="radio"
                    name="scenario"
                    checked={scenarioId === s.id}
                    onChange={() => setScenarioId(s.id)}
                  />
                  {s.label}
                </label>
              ))}
            </fieldset>
            <fieldset>
              <legend>Dispatcher</legend>
              <label>
                <input
                  type="radio"
                  name="dispatcher"
                  checked={dispatcher === "scripted"}
                  onChange={() => setDispatcher("scripted")}
                />
                Standard moves
              </label>
              <label
                title={
                  sparkAvailable === false
                    ? "Needs MODEL_API_KEY in the engine environment"
                    : undefined
                }
              >
                <input
                  type="radio"
                  name="dispatcher"
                  checked={dispatcher === "spark"}
                  onChange={() => setDispatcher("spark")}
                  disabled={sparkAvailable === false}
                />
                Muse Spark AI
              </label>
            </fieldset>
            <fieldset>
              <legend>Map shows</legend>
              <label>
                <input
                  type="radio"
                  name="view"
                  checked={view === "with"}
                  onChange={() => setView("with")}
                />
                With BusDrop
              </label>
              <label>
                <input
                  type="radio"
                  name="view"
                  checked={view === "without"}
                  onChange={() => setView("without")}
                />
                Without
              </label>
            </fieldset>
            <fieldset>
              <legend>Realism</legend>
              <label>
                <input
                  type="checkbox"
                  checked={ridersOn}
                  onChange={(e) => setRidersOn(e.target.checked)}
                />
                Riders can decline
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={voiceOn}
                  onChange={(e) => setVoiceOn(e.target.checked)}
                />
                Driver voice notes
              </label>
            </fieldset>
          </div>
        </section>

        {res && base && (
          <section className={styles.outcomes} aria-label="The morning in numbers">
            <div className={styles.strip} aria-live="polite">
              <figure>
                <strong className="tnum">{res.denied}</strong>
                <figcaption>
                  riders left behind
                  <span className="tnum">
                    {saved >= 0 ? `−${saved}` : `+${-saved}`} vs without
                  </span>
                </figcaption>
              </figure>
              <figure>
                <strong className="tnum">{res.wait.toFixed(1)} min</strong>
                <figcaption>
                  average wait
                  <span className="tnum">
                    {(res.wait - base.wait >= 0 ? "+" : "") +
                      (res.wait - base.wait).toFixed(1)}{" "}
                    vs without
                  </span>
                </figcaption>
              </figure>
              <figure>
                <strong className="tnum">{Math.round(res.peak * 100)}%</strong>
                <figcaption>
                  fullest bus
                  <span className="tnum">
                    {Math.round((res.peak - base.peak) * 100)} pts vs without
                  </span>
                </figcaption>
              </figure>
            </div>
            <p className={styles.withoutLine}>
              Without BusDrop: {base.denied} left behind, {base.wait.toFixed(1)}{" "}
              min average wait, {Math.round(base.peak * 100)}% fullest bus.
            </p>
          </section>
        )}

        {withRun && withoutRun && (
          <section className={styles.section} aria-label="How the peak unfolded">
            <h2>How the peak unfolded</h2>
            <div className={styles.chartLegend} aria-hidden="true">
              <span>
                <i className={styles.dashSwatch} /> Without
              </span>
              <span>
                <i className={styles.solidSwatch} /> With BusDrop
              </span>
            </div>
            <div className={styles.chartSheet}>
              <WaitingChart
                withFrames={withRun.frames}
                withoutFrames={withoutRun.frames}
                startHour={corridor.start_hour}
              />
            </div>
            <p className={styles.caption}>
              Riders waiting across all stops through the morning.
            </p>
          </section>
        )}

        {withRun && (
          <section className={styles.section} aria-label="Moves that mattered">
            <h2>Moves that mattered</h2>
            {withRun.moves.length === 0 ? (
              <p>No moves this morning — nothing overflowed.</p>
            ) : (
              <>
                <ol className={styles.moves}>
                  {[...withRun.moves].reverse().slice(0, 5).map((m, i) => (
                    <li key={`${m.minute}-${i}`}>
                      <p>{moveSentence(m)}</p>
                      {m.explanation && (
                        <p className={styles.dispatcherNote}>
                          Dispatcher: {m.explanation}
                        </p>
                      )}
                    </li>
                  ))}
                </ol>
                {withRun.moves.length > 5 && (
                  <details className={styles.more}>
                    <summary>All {withRun.moves.length} moves</summary>
                    <ol className={styles.moves}>
                      {[...withRun.moves]
                        .reverse()
                        .slice(5)
                        .map((m, i) => (
                          <li key={`${m.minute}-${i}`}>
                            <p>{moveSentence(m)}</p>
                            {m.explanation && (
                              <p className={styles.dispatcherNote}>
                                Dispatcher: {m.explanation}
                              </p>
                            )}
                          </li>
                        ))}
                    </ol>
                  </details>
                )}
              </>
            )}
          </section>
        )}

        {res && base && (
          <section className={styles.section} aria-label="Behind the scenes">
            <h2>Behind the scenes</h2>
            <p>
              Safety checks approved {res.approved} {plural(res.approved, "move", "moves")} and
              blocked {res.rejected}. Every rider kept their ticket and
              destination; only the bus underneath changed.
            </p>
            {res.offers > 0 && (
              <p>
                {res.offers} riders were offered a move and {res.declines} kept
                their seat.
              </p>
            )}
            <table className={styles.routes}>
              <thead>
                <tr>
                  <th scope="col">Route</th>
                  <th scope="col">Left behind without</th>
                  <th scope="col">Left behind with</th>
                </tr>
              </thead>
              <tbody>
                {Object.keys(base.denied_by_route)
                  .sort()
                  .map((rid) => (
                    <tr key={rid}>
                      <th scope="row">
                        {rid} ({corridor.routes[rid]?.short ?? rid})
                      </th>
                      <td className="tnum">{base.denied_by_route[rid]}</td>
                      <td className="tnum">{res.denied_by_route[rid]}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </section>
        )}

        <footer className={styles.footer}>
          <p>Same buses, same tickets, no extra fare.</p>
          <p className={styles.fineprint}>
            Synthetic demand, simulated live. The full story runs offline; the
            AI dispatcher upgrades when the engine has a key.
          </p>
        </footer>
      </main>
    </div>
  );
}

function Masthead({ status }: { status: "live" | "offline" }) {
  return (
    <header className={styles.masthead}>
      <span className={styles.wordmark}>BusDrop</span>
      <span className={styles.mastRight}>
        <span>Anna Salai · morning peak</span>
        <span
          className={`${styles.engine} ${status === "live" ? styles.live : styles.off}`}
          role="status"
        >
          <i aria-hidden="true" />
          {status === "live" ? "Engine live" : "Engine offline"}
        </span>
      </span>
    </header>
  );
}
