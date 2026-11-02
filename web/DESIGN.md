---
name: BusDrop web
description: "Your ticket belongs to your destination, not to one bus."
colors:
  paper: "#f2f3f1"
  sheet: "#ffffff"
  ink: "#17212b"
  ink-soft: "#3d4a58"
  ink-faint: "#5b6672"
  hairline: "#d8dbd6"
  r1-brick: "#b03a30"
  r2-teal: "#0e7c7b"
  r3-amber: "#c98a1b"
  stamp: "#e03e2d"
  stamp-deep: "#b62e21"
  ok: "#1e7e34"
  chart-grey: "#8a939c"
  ink-hover: "#0c1218"
typography:
  display:
    fontFamily: '"Archivo Variable", "Archivo", system-ui, -apple-system, "Segoe UI", sans-serif'
    fontSize: "clamp(2.4rem, 5.2vw, 4.1rem)"
    fontWeight: 850
    lineHeight: 1.02
    letterSpacing: "-0.03em"
  headline:
    fontFamily: '"Archivo Variable", "Archivo", system-ui, -apple-system, "Segoe UI", sans-serif'
    fontSize: "clamp(1.6rem, 3vw, 2.1rem)"
    fontWeight: 800
    letterSpacing: "-0.02em"
  title:
    fontFamily: '"Archivo Variable", "Archivo", system-ui, -apple-system, "Segoe UI", sans-serif'
    fontSize: "19px"
    fontWeight: 800
    letterSpacing: "-0.01em"
  body:
    fontFamily: '"Archivo Variable", "Archivo", system-ui, -apple-system, "Segoe UI", sans-serif'
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.5
  mono:
    fontFamily: '"Spline Sans Mono", ui-monospace, "SF Mono", Menlo, monospace'
    fontSize: "14px"
    fontWeight: 500
rounded:
  pill: "999px"
  sheet: "14px"
  card: "12px"
  ticket: "10px"
  stamp: "6px"
  focus: "2px"
spacing:
  stack: "36px"
  gutter: "28px"
  gap: "20px"
  pad: "18px"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    rounded: "{rounded.pill}"
    padding: "10px 24px"
  button-play:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    rounded: "{rounded.pill}"
    padding: "13px 30px"
  button-primary-hover:
    backgroundColor: "{colors.ink-hover}"
  chip:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.ink}"
    rounded: "{rounded.pill}"
    padding: "8px 20px"
  chip-checked:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    rounded: "{rounded.pill}"
    padding: "8px 20px"
  card-sheet:
    backgroundColor: "{colors.sheet}"
    rounded: "{rounded.sheet}"
    padding: "20px 22px"
---

# Design System: BusDrop web

## Overview

**Creative North Star: "The Diagram"**

A Beck-style schematic transit world: paper ground, ink linework, three
line colors, timetable rules, tabular mono figures. The morning is a
rescue, not a dashboard — the first viewport stages one bus crushing
under load beside a ticking waiting count, one action releases into the
living diagram, and the morning replays from three seats. Schematics
are not north-up: the trunk axis runs horizontal, branches fan left,
the spine runs right. Every visual is drawn from live engine data at
render time; no stock, no generated rasters. (Direction "The Diagram",
surface seed 965d55dd, dealt lead The Crush Clock.)

**Key Characteristics:**

- Paper ground with ink linework; color is rationed to meaning.
- Timetables, rules, and stamps: the visual language of a printed
  transit notice, not an analytics dashboard.
- Numbers are always tabular mono; prose is always Archivo.
- The rescue moment is the only thing allowed to shout.

## Colors

Paper ground, ink linework, three line colors; vermilion is spent only
where a rider's fate turns.

### Primary

- **Schematic Ink** (#17212b): linework, trunk casing, text, primary
  buttons, checked pills, hop tags, and buses at crush load.

### Secondary

- **Royapettah Brick** (#b03a30): R1 line, branches, bus dots, legend
  swatches, trunk offset −10.
- **Teynampet Teal** (#0e7c7b): R2 line, trunk offset 0.
- **Gemini Amber** (#c98a1b): R3 line, darkened for linework, trunk
  offset +10.

### Tertiary

- **Vermilion Stamp** (#e03e2d): the rescue moment only — hop arcs,
  handoff pings, blocked-desk stamps, offline engine dot.
- **Stamp Deep** (#b62e21): near-crush buses, hop dots, the staged
  crush word in the meter.
- **Ledger Green** (#1e7e34): approval — live engine dot, Approved
  desk stamps.
- **Without Grey** (#8a939c): the no-BusDrop twin — dashed chart
  series, dashed legend swatch, end dot.

### Neutral

- **Paper** (#f2f3f1): page ground, text on ink fills, selection text.
- **Sheet** (#ffffff): cards, rails, diagram sheet, chart sheet, pills,
  trunk casing inner, interchange fills.
- **Ink Soft** (#3d4a58): secondary prose, deck, ticker, rail lines.
- **Ink Faint** (#5b6672): captions, legends, ticks, meta lines,
  scrollbars.
- **Hairline** (#d8dbd6): every seam — card borders, row rules, chart
  gridlines, ticket surroundings.

### Named Rules

**The Stamp Red Rule.** Vermilion (`--stamp`) and stamp-deep appear
only where a rider's fate turns: the staged crush word, hop arcs and
pings, near-crush buses, and the dispatch desk's Blocked stamp. Buses
at crush load go ink, not red — the crush is weight, not alarm
(`busColor` in `lib/corridor.ts`).
**The Three Lines Rule.** Route color is identity, never decoration:
R1 brick, R2 teal, R3 amber, always via `ROUTE_COLORS`. Nothing else
on the page wears these hues.
**The Load Words Rule.** Load is plain words only — Roomy, Busy,
Packed, Full (`loadWord`, thresholds 0.6 / 0.85 / 1.0). Percentages
appear only for the peak-load fallback and ledger figures.

## Typography

**Display Font:** Archivo Variable (with Archivo, system-ui fallback)
**Body Font:** Archivo Variable (with Archivo, system-ui fallback)
**Label/Mono Font:** Spline Sans Mono (with ui-monospace, SF Mono,
Menlo fallback)

**Character:** A transit notice set in grotesque prose with timetable
figures — Archivo carries the voice, Spline Sans Mono carries every
number, clock, label, and stamp.

### Hierarchy

- **Display** (850, clamp(2.4rem, 5.2vw, 4.1rem), 1.02): the thesis
  line in the Crush Clock, max 20ch, stretched 115%.
- **Headline** (800, clamp(1.6rem, 3vw, 2.1rem)): section titles
  ("How the peak unfolded"), stretched 110%.
- **Title** (800, 19px): seat-rail headings ("Your seat", "The
  dispatch desk", "The city ledger").
- **Body** (400, 16px, 1.5): prose, capped at 68ch (76ch in move
  sentences).
- **Mono count** (700, clamp(3.6rem, 9vw, 6rem), 1): the giant staged
  load figure (`onboard/capacity`) in the meter.
- **Mono readout** (700, 30px): diagram clock; outcome figures at
  clamp(2rem, 4vw, 2.9rem); dock clock at 18px.
- **Label** (500–700, 11–14.5px, mono): legends, ticks (11px), stamps
  (11px uppercase, 0.12em), stop labels (12.5px), ticker (13.5px),
  rail rows, captions (12.5px faint).

### Named Rules

**The Timetable Figures Rule.** Every number on the page is tabular:
`.tnum` plus `td`, `time`, and `output` all carry
`font-variant-numeric: tabular-nums`. Clocks, counts, waits, and
ledgers never wobble.
**The HTML Labels Rule.** Stop labels and handoff tags live in HTML
over the SVG so they never shrink with the viewBox; chart ticks use
the true-size `.chartTick` class (11px mono, ink-faint).

## Layout

One viewport at a time, stacked on a 1240px column (28px gutters,
36px section rhythm):

1. Masthead: wordmark (900, stretched 125%), corridor tag in mono,
   engine live/offline pill.
2. The Crush Clock (`CrushClock`): thesis line, two-sentence deck,
   then the meter — the giant staged load figure (`onboard/capacity`
   in mono, crush word in stamp-deep caps, bus id with route dot)
   beside the waiting rail (clock line, waiting count with a 900ms
   ease-out-cubic count-up tick, ticket destinations, Play-the-rescue
   action), over a faint trunk echo (the real trunk geometry redrawn
   in three line colors at 0.1 opacity). Stakes line beneath ("N
   riders moved · M fewer left behind").
3. The seat console: "Take a seat" switcher (Rider / Dispatcher /
   City pills) over a 7fr/5fr grid pairing the living `Diagram`
   (legend, clock readout, waiting/moved counts) with the `SeatRail`
   — a rider ticket (dashed-border destination stub, queue status,
   driver note), a dispatch stamped feed (one Approved/Blocked
   rotated stamp per proposal, four-check footnote), or a city ledger
   (left-behind, wait, peak with with-vs-without deltas, per-route
   table). A veil ("Assembling the morning…") covers the rail while
   runs load. The console scrolls into view (smooth unless
   reduced-motion) when the rescue plays, with 140px scroll margin.
4. The ticker: a mono ledger line between hairline rules narrating
   the latest move at the current minute plus the driver note.
5. The sticky dock: replay transport (Replay/Stop/Again pill, time
   slider, mono clock) over Morning / Dispatcher / Map-shows /
   Realism pill groups. Sticks at top 12px with the page's only
   shadow; goes static under 700px.
6. Outcome strip: left behind, average wait, fullest bus between 2px
   ink rules, each with a with-vs-without delta; the without-line
   beneath in faint mono. Same fleet, same riders; only the
   dispatcher differs.
7. "How the peak unfolded": waiting-through-the-morning chart (solid
   ink with-BusDrop vs dashed grey without) on a sheet with legend
   and caption.
8. "Moves that mattered": latest five moves as plain sentences with
   the dispatcher's note; the rest under a details fold. Empty
   mornings read "nothing overflowed".
9. "Behind the scenes": verifier approvals/blocks, rider declines,
   per-route left-behind table. Footer restates the terms: same
   buses, same tickets, no extra fare; synthetic demand, simulated
   live.

Responsive: console grid and meter collapse to one column (900px /
760px); branch labels hide and the readout shrinks at 640px; masthead
tag hides and the outcome strip stacks with hairline dividers at
700px. Replay ticks at 140ms per minute; reduced-motion readers get
final figures immediately and auto scrolling.

## Elevation & Depth

Flat paper by default; depth is tonal layering (paper vs sheet vs
ink fills), never lifted cards.

### Shadow Vocabulary

- **Dock float** (`box-shadow: 0 14px 34px rgba(23, 33, 43, 0.1)`):
  the sticky replay dock only, so it reads as floating above the
  scroll beneath it.

### Named Rules

**The Flat-By-Default Rule.** Surfaces are flat at rest. The dock's
shadow is the single exception; nothing else casts one.
**The Veil Rule.** Loading states are translucent white veils with a
breathing mono line ("Assembling the morning…"), never spinners.

## Shapes

Pills for everything touchable, sheets for everything held, rules for
everything separated. Buttons, pills, swatches, engine dot, tags, and
stop labels are fully round (999px); sheets and rails are gently
curved (14px); notices are 12px; tickets (dashed ink-faint border on
paper) and error-code blocks are 10px; desk stamps are small rotated
rectangles (6px, 1.5px currentColor border, 2deg tilt). Outcome bands
and footers open with 2px ink rules; rows and rail lines separate
with 1px hairlines. Focus is a 2px ink outline offset 3px.

## Components

### Buttons

- **Shape:** pill (999px), no border.
- **Primary:** ink fill, paper text; replay size (10px 24px, 15px),
  play-the-rescue size (13px 30px, 16px), both weight 700.
- **Hover / Focus:** deepens to near-black (#0c1218); visible ink
  focus outline. Disabled drops to 0.45 opacity with a not-allowed
  cursor.
- **Chips (seats + dock groups):** sheet pills with hairline borders;
  the checked pill inverts to ink fill with paper text
  (`:has(input:checked)` over visually hidden native inputs).

### Cards / Containers

- **Corner Style:** sheets 14px, notices 12px, tickets 10px dashed.
- **Background:** sheet on paper ground; tickets invert to paper on
  sheet.
- **Shadow Strategy:** none (see Elevation); only the dock floats.
- **Border:** 1px hairline throughout; 2px ink rules frame outcome
  bands, table heads, footers, and the meter top.
- **Internal Padding:** rail 20px 22px; dock 14px 18px; chart sheet
  18px/8px; error card 40px.

### Inputs / Fields

- **Style:** the time slider is a native range with `accent-color:
  ink`; scenario/dispatcher/view/realism controls are native radios
  and checkboxes skinned as chips.
- **Focus:** chip focus rings via `:has(input:focus-visible)`; global
  2px ink focus outline.
- **Error / Disabled:** the Spark option disables (0.45 opacity, tooltip) when the engine reports no key; engine-down and run-failed
  states are sheet error cards with start instructions or retry.

### Navigation

No site navigation; the masthead is identity plus engine status, and
the "Take a seat" switcher plus dock groups are the page's only
control rails. All controls are native inputs under pill labels, so
keyboard and screen-reader behavior comes free.

### The Schematic

Ink casing (31px) with a sheet inner (26px) carries three offset
parallel trunk lines (6px, ±10px); branches draw in route colors
(6.5px) with a 1s draw-on animation. Queue halos swell at stops (ink
at 0.06), buses glide as dots (route color; ink at crush, stamp-deep
near-crush; depot dots at 0.3 until their start minute), and each
handoff draws a vermilion hop arc with a ping and an ink rider-count
tag. Interchanges are sheet rings in ink; the BWY terminus carries an
ink core. The whole figure carries a text equivalent via `aria-label`
(clock, waiting, full buses, moved so far).

### The Stamped Feed

Each dispatch proposal is a ledger row (mono clock head, route arrow,
stop; walked/stayed meta; dispatcher note) closed by a rotated
Approved (ledger green) or Blocked (vermilion) stamp. The feed scrolls
past 420px in the world's own thin grey scrollbars.

## Do's and Don'ts

Concrete guardrails from the built system.

### Do:

- **Do** set every number, clock, and ledger line in Spline Sans Mono
  with tabular figures.
- **Do** spend vermilion only where a rider's fate turns (crush word,
  hops, pings, Blocked stamps).
- **Do** crush buses to ink and near-crush to stamp-deep; never red
  for a full bus dot.
- **Do** name load with Roomy / Busy / Packed / Full.
- **Do** render stop labels and handoff tags in HTML over the SVG.
- **Do** skin controls as pills with hidden native inputs and an ink
  checked state.
- **Do** frame outcome bands with 2px ink rules and separate rows
  with hairlines.
- **Do** veil loading regions with breathing mono text, never
  spinners.

### Don't:

- **Don't** put shadows on anything but the sticky dock.
- **Don't** use line colors (brick, teal, amber) for anything except
  route identity.
- **Don't** invent a fourth line color or a second accent red.
- **Don't** scale type with the diagram viewBox.
- **Don't** gate any story on AI: the full morning runs offline, and
  the Spark option disables honestly without a key.
- **Don't** compare runs that differ by anything but the dispatcher.
- **Don't** use proportional figures for counts, clocks, or waits.
