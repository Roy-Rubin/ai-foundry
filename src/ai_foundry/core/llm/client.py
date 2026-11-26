"""Text generation clients for live and zero-cost runs."""

import json
from typing import Any, Protocol
from urllib.request import Request

from ai_foundry.core.sources.http import HttpClient


class TextClient(Protocol):
    """Text generation boundary used by project agents."""

    def generate(self, instructions: str, source: str) -> str:
        """Generate text.

        Args:
            instructions: Summarization instructions.
            source: Source material.

        Returns:
            Generated text.
        """
        # Implementations supply generated text.
        ...


class MockTextClient:
    """Generate deterministic placeholders without network access."""

    def generate(self, instructions: str, source: str) -> str:
        """Produce a visibly marked placeholder.

        Args:
            instructions: Unused live summarization instructions.
            source: Title and abstract.

        Returns:
            Deterministic mock text.
        """
        # Retain a short excerpt for inspecting report plumbing.
        excerpt: str = " ".join(source.split())[:240]
        summary: str = f"MOCK placeholder — source excerpt: {excerpt}"
        return summary


class OpenAITextClient:
    """Call OpenAI with a configurable model."""

    def __init__(self, api_key: str, model: str, transport: HttpClient) -> None:
        """Configure the provider.

        Args:
            api_key: OpenAI credential.
            model: Model ID.
            transport: HTTP transport.
        """
        # Keep credentials out of logs and report data.
        self.api_key: str = api_key
        self.model: str = model
        self.transport: HttpClient = transport

    def generate(self, instructions: str, source: str) -> str:
        """Summarize source text using the configured model.

        Args:
            instructions: Developer instructions.
            source: Untrusted title and abstract.

        Returns:
            Nonempty model response.

        Raises:
            ValueError: If the provider response has no usable summary.
            OSError: If the provider request fails.
        """
        # Send source material as a separate user message.
        body: bytes = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "developer", "content": instructions},
                {"role": "user", "content": source},
            ],
            "max_completion_tokens": 350,
        }).encode()
        request: Request = Request(
            "https://api.openai.com/v1/chat/completions",
            data=body,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
        )
        payload: bytes = self.transport.request(request)
        # Validate the response before the workflow persists it.
        try:
            response: dict[str, Any] = json.loads(payload)
            summary: str = response["choices"][0]["message"]["content"]
            if not isinstance(summary, str) or not summary.strip():
                raise ValueError("Empty model summary")
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
            raise ValueError("Invalid model response") from error
        return summary
