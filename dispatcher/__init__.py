"""BusDrop agentic dispatcher: Muse Spark proposes handoffs via tool
calls, the verifier authorizes them. Phase 4."""
from .policy import spark_policy_factory
from .spark import BASE_URL, MODEL_ID, DispatcherError, SparkClient
from .tools import (PROPOSE_HANDOFF_SCHEMA, SYSTEM_PROMPT, build_messages,
                    get_corridor_state)

__all__ = ["BASE_URL", "MODEL_ID", "DispatcherError", "SparkClient",
           "PROPOSE_HANDOFF_SCHEMA", "SYSTEM_PROMPT", "build_messages",
           "get_corridor_state", "spark_policy_factory"]
