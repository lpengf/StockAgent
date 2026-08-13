"""LLM gateway seam.

The current build is deterministic (no LLM calls). This module keeps the
interface open so future roles that use a model can be swapped in without
touching orchestrator or agent code.
"""

from stock_agent.infrastructure.llm.gateway import LLMGateway, NullLLMGateway, get_llm_gateway

__all__ = ["LLMGateway", "NullLLMGateway", "get_llm_gateway"]
