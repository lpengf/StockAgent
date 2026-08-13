"""LLM gateway. Every model provider adapts to this Protocol.

The default `NullLLMGateway` returns a deterministic empty payload so that
running without any external model key still succeeds — the deterministic
agents ignore the gateway result.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    model_id: str


class LLMGateway(Protocol):
    def complete(self, *, system: str, user: str, schema: dict | None = None) -> LLMResponse: ...


class NullLLMGateway:
    """Zero-cost fallback used in the deterministic build.

    Returns an empty payload so callers can log usage without branching.
    """

    def complete(self, *, system: str, user: str, schema: dict | None = None) -> LLMResponse:
        del system, user, schema
        return LLMResponse(text="", input_tokens=0, output_tokens=0, model_id="null")


def get_llm_gateway() -> LLMGateway:
    return NullLLMGateway()
