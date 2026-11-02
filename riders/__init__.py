"""BusDrop rider agents: every handoff is an offer the rider can refuse.

The dispatcher proposes, the verifier authorizes, the rider decides.
Phase 5."""
from .open import (DEFAULT_MODEL, RiderError, SparkOpenClient,
                   resolve_endpoint)
from .policy import (CRUSH_LOAD, EAGER_PATIENCE, FULL_LOAD,
                     SEAT_LOVER_PATIENCE, SYSTEM_PROMPT, build_messages,
                     build_offer, rider_policy_factory, rule_decision)

__all__ = ["CRUSH_LOAD", "DEFAULT_MODEL", "EAGER_PATIENCE", "FULL_LOAD",
           "SEAT_LOVER_PATIENCE", "SYSTEM_PROMPT", "RiderError",
           "SparkOpenClient", "build_messages", "build_offer",
           "resolve_endpoint", "rider_policy_factory", "rule_decision"]
