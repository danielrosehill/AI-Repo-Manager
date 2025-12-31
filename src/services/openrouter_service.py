"""OpenRouter API service for embeddings and chat."""

import httpx
from typing import AsyncGenerator


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterService:
    """Service for OpenRouter API - embeddings and chat completions."""

    def __init__(
        self,
        api_key: str,
        embedding_model: str = "openai/text-embedding-3-small",
        chat_model: str = "anthropic/claude-sonnet-4",
    ):
        self.api_key = api_key
        self.embedding_model = embedding_model
        self.chat_model = chat_model
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=OPENROUTER_BASE_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/danielrosehill/AI-Repo-Manager",
                    "X-Title": "AI Repo Manager",
                },
                timeout=60.0,
            )
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def create_embedding(self, text: str) -> list[float]:
        """Create embedding for text using OpenRouter."""
        response = await self.client.post(
            "/embeddings",
            json={
                "model": self.embedding_model,
                "input": text,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["data"][0]["embedding"]

    async def create_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """Create embeddings for multiple texts."""
        response = await self.client.post(
            "/embeddings",
            json={
                "model": self.embedding_model,
                "input": texts,
            },
        )
        response.raise_for_status()
        data = response.json()

        # Sort by index to ensure correct order
        embeddings_data = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in embeddings_data]

    async def chat(
        self,
        messages: list[dict],
        system_prompt: str | None = None,
    ) -> str:
        """Send chat completion request."""
        all_messages = []

        if system_prompt:
            all_messages.append({"role": "system", "content": system_prompt})

        all_messages.extend(messages)

        response = await self.client.post(
            "/chat/completions",
            json={
                "model": self.chat_model,
                "messages": all_messages,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    async def chat_stream(
        self,
        messages: list[dict],
        system_prompt: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion response."""
        all_messages = []

        if system_prompt:
            all_messages.append({"role": "system", "content": system_prompt})

        all_messages.extend(messages)

        async with self.client.stream(
            "POST",
            "/chat/completions",
            json={
                "model": self.chat_model,
                "messages": all_messages,
                "stream": True,
            },
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        import json
                        data = json.loads(data_str)
                        delta = data["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue

    async def test_connection(self) -> tuple[bool, str]:
        """Test OpenRouter API connection."""
        try:
            # Simple test with a minimal request
            response = await self.client.get("/models")
            response.raise_for_status()
            return True, "Connected to OpenRouter"
        except httpx.HTTPStatusError as e:
            return False, f"OpenRouter API error: {e.response.status_code}"
        except Exception as e:
            return False, f"Connection error: {e}"
