"""BusDrop operations view: replay the Anna Salai morning peak and see
what mid-route handoffs changed for riders.

Run from the repo root:  streamlit run dashboard/app.py
Then open the printed local URL (usually http://localhost:8501).
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import pydeck as pdk
import streamlit as st

from simulator.demand import generate_riders
from simulator.handoff import reckless_policy, scripted_policy
from simulator.network import STOP_COORDS, build_corridor, build_stops
from simulator.sim import COOLDOWN_MIN, Simulation

MINUTES = 180
START_HOUR = 7  # the simulated morning starts at 07:00

SCENARIOS = {
    "Morning rush": 42,
    "Festival crowd": 7,
    "Rainy Monday": 123,
}
ROUTE_SHORT = {"R1": "Royapettah", "R2": "Teynampet", "R3": "Gemini"}
STOP_NAMES = {sid: s.name for sid, s in build_stops().items()}


@st.cache_data(show_spinner="Replaying the morning peak...")
def run_recorded(mode: str, seed: int, riders_on: bool,
                 voice_on: bool) -> dict:
    """Run the corridor headless with per-minute frames; plain data only."""
    stops, routes, buses = build_corridor()
    riders = generate_riders(stops, routes, MINUTES, seed=seed)
    policy = None
    if mode == "spark":
        from dispatcher import (DispatcherError, SparkClient,
                                spark_policy_factory)
        try:
            client = SparkClient()
        except DispatcherError as e:
            raise RuntimeError(str(e))
        policy = spark_policy_factory(client)
    elif mode == "scripted":
        policy = scripted_policy
    elif mode == "reckless":
        policy = reckless_policy
    rider_policy = None
    if riders_on and policy is not None:
        from riders import rider_policy_factory
        rider_policy = rider_policy_factory()
    voice_feed = None
    if voice_on and policy is not None:
        from voice import load_demo
        voice_feed = load_demo()
    sim = Simulation(stops, routes, buses, riders, MINUTES,
                     handoff_policy=policy, record=True,
                     rider_policy=rider_policy, voice_feed=voice_feed)
    res = sim.run()
    return {
        "result": {
            "total": res.total_riders, "boarded": res.boarded,
            "alighted": res.alighted, "unserved": res.unserved,
            "denied": res.denied_boardings, "wait": res.avg_wait_min,
            "peak": res.peak_load_factor, "events": res.handoff_events,
            "moved": res.riders_transferred,
            "approved": res.verifier_approvals,
            "rejected": res.verifier_rejections,
            "offers": res.rider_offers, "declines": res.rider_declines,
            "denied_by_route": dict(res.denied_by_route),
            "avg_load_by_route": dict(res.avg_load_by_route),
            "peak_load_by_route": dict(res.peak_load_by_route),
        },
        "frames": sim.frames,
    }


def clock(minute: int) -> str:
    """Sim minute -> wall time, e.g. 105 -> 08:45."""
    return f"{START_HOUR + minute // 60:02d}:{minute % 60:02d}"


def load_word(load: float) -> str:
    if load >= 1.0:
        return "Full"
    if load >= 0.85:
        return "Packed"
    if load >= 0.6:
        return "Busy"
    return "Roomy"


def load_color(load: float) -> list[int]:
    """Green -> amber -> red as the bus fills."""
    r = int(60 + (220 - 60) * load)
    g = int(170 * (1 - load) + 60 * load)
    return [r, g, 70]


def waiting_now(frame: dict) -> int:
    return sum(frame["queues"].values())


def moved_so_far(frames: list, minute: int) -> int:
    return sum(h["riders"] for f in frames[:minute + 1]
               for h in f["handoffs"])


def latest_move(frames: list, minute: int) -> tuple[dict, dict] | None:
    """Most recent (frame, handoff) at or before minute."""
    for f in reversed(frames[:minute + 1]):
        if f["handoffs"]:
            return f, f["handoffs"][-1]
    return None


def move_sentence(h: dict, minute: int) -> str:
    n = h["riders"]
    riders = "rider" if n == 1 else "riders"
    frm = ROUTE_SHORT.get(h["from_bus"].split("-")[0], h["from_bus"])
    to = ROUTE_SHORT.get(h["to_bus"].split("-")[0], h["to_bus"])
    stop = STOP_NAMES.get(h["stop_id"], h["stop_id"])
    return (f"{clock(minute)}, {stop}: {n} {riders} stepped from the "
            f"{frm} bus to the {to} bus to make room.")


def stop_layer(frame: dict) -> pdk.Layer:
    data = [{"stop": sid, "name": nm, "lat": STOP_COORDS[sid][0],
             "lon": STOP_COORDS[sid][1],
             "waiting": frame["queues"].get(sid, 0)}
            for sid, nm in STOP_NAMES.items()]
    return pdk.Layer(
        "ScatterplotLayer", data, get_position=["lon", "lat"],
        get_fill_color=[70, 70, 70, 160], get_radius="waiting",
        radius_scale=18, radius_min_pixels=3, radius_max_pixels=22,
        pickable=True, auto_highlight=True,
    )


def bus_layer(frame: dict) -> pdk.Layer:
    data = []
    for bid, b in frame["buses"].items():
        load = b["onboard"] / b["capacity"]
        data.append({"bus": bid, "route": b["route"], "lat": b["lat"],
                     "lon": b["lon"], "onboard": b["onboard"],
                     "capacity": b["capacity"], "color": load_color(load),
                     "status": load_word(load)})
    return pdk.Layer(
        "ScatterplotLayer", data, get_position=["lon", "lat"],
        get_fill_color="color", get_radius=110, radius_min_pixels=5,
        pickable=True, auto_highlight=True,
    )


def pulse_layer(frame: dict) -> pdk.Layer | None:
    """Highlight stops where a handoff is happening this minute."""
    seen = {}
    for h in frame["handoffs"]:
        seen[h["stop_id"]] = seen.get(h["stop_id"], 0) + h["riders"]
    if not seen:
        return None
    data = [{"lon": STOP_COORDS[s][1], "lat": STOP_COORDS[s][0],
             "riders": n} for s, n in seen.items()]
    return pdk.Layer(
        "ScatterplotLayer", data, get_position=["lon", "lat"],
        get_fill_color=[255, 170, 0, 140], get_radius=220,
        radius_min_pixels=12, pickable=True,
    )


def route_lines() -> pdk.Layer:
    from simulator.network import build_routes
    lines = []
    for route in build_routes().values():
        pts = [STOP_COORDS[s] for s in route.stop_ids]
        for a, b in zip(pts, pts[1:]):
            lines.append({"from_lon": a[1], "from_lat": a[0],
                          "to_lon": b[1], "to_lat": b[0]})
    return pdk.Layer(
        "LineLayer", lines, get_source_position=["from_lon", "from_lat"],
        get_target_position=["to_lon", "to_lat"],
        get_color=[150, 150, 150, 90], get_width=2)


def stop_names_layer() -> pdk.Layer:
    data = [{"name": nm, "lat": STOP_COORDS[s][0], "lon": STOP_COORDS[s][1]}
            for s, nm in STOP_NAMES.items()]
    return pdk.Layer(
        "TextLayer", data, get_position=["lon", "lat"], get_text="name",
        get_size=11, get_color=[60, 60, 60],
        get_alignment_baseline="'bottom'")


st.set_page_config(page_title="BusDrop: Anna Salai mornings",
                   layout="wide")
st.title("BusDrop")
st.caption("Your ticket belongs to your destination, not to one bus. "
           "Replay the morning peak on Anna Salai and see what changes "
           "when crowded buses share riders mid-route.")

with st.sidebar:
    st.header("Settings")
    scenario = st.selectbox("Morning", list(SCENARIOS), index=0)
    dispatcher = st.radio("Dispatcher", ["Standard moves", "Muse Spark AI"],
                          help="Standard moves follow a fixed relief rule. "
                          "Muse Spark AI reasons over each meet and explains "
                          "itself (needs MODEL_API_KEY).")
    voice_on = st.checkbox("Driver voice notes", value=True,
                           help="Tamil/English crowd reports that warn the "
                           "dispatcher before the queue builds.")
    riders_on = st.checkbox("Riders can decline", value=True,
                            help="Every move is an offer; some riders keep "
                            "their seat.")
    st.divider()
    st.caption("Same fleet, same riders, both runs. Only the dispatcher "
               "differs.")

seed = SCENARIOS[scenario]
mode = "spark" if dispatcher == "Muse Spark AI" else "scripted"
try:
    with_run = run_recorded(mode, seed, riders_on, voice_on)
except RuntimeError as e:
    st.warning(f"Muse Spark is unreachable ({e}). Showing Standard moves "
               f"instead — add MODEL_API_KEY to try the AI dispatcher.")
    mode = "scripted"
    with_run = run_recorded(mode, seed, riders_on, voice_on)
without_run = run_recorded("baseline", seed, False, False)

res_with, res_without = with_run["result"], without_run["result"]
frames_with = with_run["frames"]
horizon = len(frames_with) - 1

saved = res_without["denied"] - res_with["denied"]
if res_with["moved"]:
    st.success(f"BusDrop moved {res_with['moved']} riders mid-route this "
               f"morning. {saved} fewer riders left behind "
               f"({res_without['denied']} without, {res_with['denied']} "
               f"with) — same buses, same tickets, no extra fare.")
else:
    st.info("No moves were needed this morning: nothing overflowed.")

view = st.segmented_control("Map shows", ["With BusDrop", "Without"],
                            default="With BusDrop", label_visibility="collapsed")
frames = frames_with if view == "With BusDrop" else without_run["frames"]

if "minute" not in st.session_state:
    st.session_state.minute = 0
if "playing" not in st.session_state:
    st.session_state.playing = False
play_col, slide_col = st.columns([1, 9])
with play_col:
    label = "Stop" if st.session_state.playing else "Replay"
    if st.button(label):
        if not st.session_state.playing and st.session_state.minute >= horizon:
            st.session_state.minute = 0
        st.session_state.playing = not st.session_state.playing
with slide_col:
    minute = st.select_slider("Time of morning",
                                options=list(range(horizon + 1)),
                                value=st.session_state.minute,
                                format_func=clock)
st.session_state.minute = minute
if st.session_state.playing:
    if minute >= horizon:
        st.session_state.playing = False
    else:
        st.session_state.minute = minute + 1
        time.sleep(0.15)
        st.rerun()

frame = frames[minute]
map_col, now_col = st.columns([2, 1])
with map_col:
    layers = [route_lines(), stop_layer(frame), stop_names_layer(),
              bus_layer(frame)]
    pulse = pulse_layer(frame)
    if pulse is not None:
        layers.append(pulse)
    deck = pdk.Deck(
        layers=layers,
        initial_view_state=pdk.ViewState(latitude=13.067, longitude=80.264,
                                         zoom=12.2, pitch=0),
        tooltip={"text": "{bus} ({route})\n{onboard}/{capacity} aboard, "
                         "{status}\n{name} stop: {waiting} waiting"},
    )
    st.pydeck_chart(deck)
    st.caption("Dots are buses, colored by how full they are. Dark circles "
               "are stops, sized by riders waiting. Amber marks a live "
               "handoff.")
with now_col:
    st.subheader(f"Right now: {clock(minute)}")
    full = sum(1 for b in frame["buses"].values()
               if b["onboard"] >= b["capacity"])
    c1, c2, c3 = st.columns(3)
    c1.metric("Waiting", waiting_now(frame))
    c2.metric("Buses full", full)
    c3.metric("Moved", moved_so_far(frames_with, minute))
    move = latest_move(frames_with, minute)
    st.markdown("**Latest move**")
    if move is None:
        st.write("None yet — the peak is still building.")
    else:
        f, h = move
        st.write(move_sentence(h, f["minute"]))
        if h["explanation"]:
            st.caption(f"Dispatcher: {h['explanation']}")
    if voice_on:
        from voice import load_demo
        signal = load_demo().latest_at(minute)
        st.markdown("**Driver note**")
        if signal is None:
            st.write("No voice notes yet.")
        else:
            lang = {"ta": "Tamil", "en": "English",
                    "mixed": "Tamil/English"}[signal.language]
            st.write(f"{clock(signal.minute)}, "
                     f"{STOP_NAMES.get(signal.stop_id, 'corridor')} "
                     f"({lang}): {signal.text}")

st.subheader("The morning in numbers")
m1, m2, m3 = st.columns(3)
m1.metric("Riders left behind", res_with["denied"],
          res_with["denied"] - res_without["denied"],
          delta_color="inverse",
          help="Boardings refused because the bus was full.")
m2.metric("Average wait", f"{res_with['wait']:.1f} min",
          f"{res_with['wait'] - res_without['wait']:.1f} min",
          delta_color="inverse")
m3.metric("Fullest bus", f"{res_with['peak'] * 100:.0f}% full",
          f"{(res_with['peak'] - res_without['peak']) * 100:.0f} pts",
          delta_color="inverse")
st.caption(f"Without BusDrop: {res_without['denied']} left behind, "
           f"{res_without['wait']:.1f} min average wait, "
           f"{res_without['peak'] * 100:.0f}% fullest bus.")

st.subheader("How the peak unfolded")
wait_df = pd.DataFrame({
    "Without": [waiting_now(f) for f in without_run["frames"]],
    "With BusDrop": [waiting_now(f) for f in frames_with],
})
wait_df.index = [clock(m) for m in range(len(wait_df))]
plot_df = wait_df.iloc[::5]  # every 5th minute keeps the axis readable
st.line_chart(plot_df)
st.caption("Riders waiting across all stops through the morning.")

st.subheader("Moves that mattered")
all_moves = [(f["minute"], h) for f in frames_with for h in f["handoffs"]]
if not all_moves:
    st.write("No moves this morning.")
else:
    for m, h in sorted(all_moves, reverse=True)[:5]:
        st.write(move_sentence(h, m))
        if h["explanation"]:
            st.caption(f"Dispatcher: {h['explanation']}")
    if len(all_moves) > 5:
        with st.expander(f"All {len(all_moves)} moves"):
            for m, h in sorted(all_moves, reverse=True)[5:]:
                st.write(move_sentence(h, m))

with st.expander("Behind the scenes"):
    st.write(f"Safety checks approved {res_with['approved']} moves and "
             f"blocked {res_with['rejected']}. Every rider kept their "
             f"ticket and destination; only the bus underneath changed.")
    if res_with["offers"]:
        st.write(f"{res_with['offers']} riders were offered a move and "
                 f"{res_with['declines']} kept their seat.")
    rows = []
    for rid in sorted(res_without["denied_by_route"]):
        rows.append({
            "route": f"{rid} ({ROUTE_SHORT.get(rid, rid)})",
            "left behind without": res_without["denied_by_route"][rid],
            "left behind with": res_with["denied_by_route"][rid],
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True)
