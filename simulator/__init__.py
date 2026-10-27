"""BusDrop corridor simulator.

Phase 1: deterministic baseline with no agents. Models three Chennai routes
sharing the Anna Salai trunk into Broadway, plus morning-peak rider demand.
Phase 2: ticket ledger + handoff mechanics, driven by an optional policy
hook (scripted demo harness; the agent arrives in phase 4).
"""
