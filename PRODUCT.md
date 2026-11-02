# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Next.js frontend in a new folder alongside the Python engine (user-chosen); live Python API backend serving simulation runs (user-chosen; API framework undecided). Streamlit dashboard stays untouched as backup.

## Users

Hackathon demo viewers — judges and visitors who must grasp the BusDrop story in minutes, with no prior knowledge of the codebase or the Chennai corridor.

## Product Purpose

BusDrop shows that a crowded bus corridor works better when tickets belong to destinations, not to one bus: an AI dispatcher moves riders mid-route between buses serving the same destination, a deterministic verifier keeps every move safe, and the morning peak ends with fewer riders left behind. Success is a viewer understanding the story and the outcome evidence in one short session.

## Positioning

Mid-route rider handoffs between same-destination buses, proposed by an AI dispatcher but authorized only by a deterministic four-check verifier (destination, ETA window, capacity, ticket) — the agent proposes, the rules dispose.

## Operating Context

Evaluated as a local interactive demo: pick a morning scenario, replay the peak on a corridor map, compare with/without handoff outcomes. Same fleet, same riders, both runs; only the dispatcher differs. AI dispatcher runs need MODEL_API_KEY; everything else runs offline.

## Capabilities and Constraints

- Python engine: 3-route Anna Salai corridor simulator, morning-peak demand, ticket ledger, scripted/reckless/Spark dispatcher policies, rider consent (patience rule or Spark Open), Tamil/English voice crowd signals.
- The verifier's four checks are the safety backstop; no proposal moves riders without passing all of them.
- New Next.js frontend reads live data from a local Python API (shape undecided); Streamlit dashboard kept as-is.
- All demand and rider data is synthetic; there is no real rider data anywhere in the product.

## Brand Commitments

Name BusDrop. Tagline: "Your ticket belongs to your destination, not to one bus." Setting: Chennai's Anna Salai corridor (Royapettah, Teynampet, Gemini routes into Broadway).

## Evidence on Hand

- Working simulator + verifier + rider/voice policies with 121-test suite (`simulator/`, `verifier/`, `riders/`, `voice/`, `tests/`).
- Incumbent Streamlit dashboard (`dashboard/app.py`): map replay, right-now rail, with/without comparison.
- No demo video, testimonials, benchmarks against real-world data, or deployment claims — future work must not fabricate any.

## Product Principles

- Comprehension first: every surface must teach the handoff story before showing controls.
- Same fleet, same riders: comparisons are honest only when nothing differs but the dispatcher.
- The verifier is the backstop: safety claims rest on deterministic checks, never on agent promises.
- Offline by default: the full story works with zero API keys; AI endpoints upgrade, never gate.
