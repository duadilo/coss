"""Token usage and cost tracking."""

from __future__ import annotations

from opencode.core.message import Usage


class CostTracker:
    """Tracks cumulative token usage for the session."""

    def __init__(self) -> None:
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0
        self.total_requests: int = 0

    def record(self, usage: Usage) -> None:
        self.total_input_tokens += usage.input_tokens
        self.total_output_tokens += usage.output_tokens
        self.total_requests += 1

    def summary(self) -> str:
        total = self.total_input_tokens + self.total_output_tokens
        return (
            f"Tokens: {total:,} total "
            f"({self.total_input_tokens:,} in / {self.total_output_tokens:,} out) "
            f"across {self.total_requests} requests"
        )
