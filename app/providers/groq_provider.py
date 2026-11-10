"""
Real Groq API Provider Integration.
Interacts with the live Groq hosted inference endpoints and captures exact rate-limit telemetry.
"""

import json
import time
from typing import Any, AsyncIterator, Dict, List, Optional
import httpx
from app.core.config import settings
from app.providers.base import BaseProvider, ProviderResponse, StreamChunk

class GroqProvider(BaseProvider):
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None
    ):
        self.api_key = api_key or settings.groq_api_key
        self.model = model or settings.groq_model
        self.base_url = base_url or settings.groq_base_url
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=settings.groq_request_timeout,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
        )

    def _extract_telemetry_headers(self, headers: httpx.Headers) -> Dict[str, str]:
        telemetry = {}
        target_keys = [
            "x-ratelimit-limit-requests",
            "x-ratelimit-limit-tokens",
            "x-ratelimit-remaining-requests",
            "x-ratelimit-remaining-tokens",
            "x-ratelimit-reset-requests",
            "x-ratelimit-reset-tokens",
            "retry-after",
        ]
        for k in target_keys:
            if k in headers:
                telemetry[k] = headers[k]
        return telemetry

    def _parse_retry_after(self, headers: httpx.Headers) -> Optional[float]:
        val = headers.get("retry-after")
        if val:
            try:
                return float(val)
            except ValueError:
                return 2.0
        return None

    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 512,
        **kwargs
    ) -> ProviderResponse:
        start_t = time.perf_counter()
        first_token_ms = 0.0

        if not self.api_key:
            return ProviderResponse(
                content="",
                status_code=401,
                source="real",
                error="GROQ_API_KEY environment variable is not set.",
                total_ms=0.0
            )

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False
        }

        try:
            resp = await self.client.post("/chat/completions", json=payload)
            total_ms = (time.perf_counter() - start_t) * 1000.0
            headers_dict = self._extract_telemetry_headers(resp.headers)
            retry_after = self._parse_retry_after(resp.headers)

            if resp.status_code == 200:
                data = resp.json()
                choice = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                tokens_in = usage.get("prompt_tokens", 0)
                tokens_out = usage.get("completion_tokens", 0)
                first_token_ms = total_ms * 0.45  # Estimated TTFT for non-streamed batch

                return ProviderResponse(
                    content=choice,
                    status_code=200,
                    source="real",
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    first_token_ms=first_token_ms,
                    total_ms=total_ms,
                    headers=headers_dict,
                    rate_limited=False
                )

            elif resp.status_code == 429:
                err_text = resp.text
                return ProviderResponse(
                    content="",
                    status_code=429,
                    source="real",
                    first_token_ms=total_ms,
                    total_ms=total_ms,
                    headers=headers_dict,
                    retry_after_s=retry_after or 2.0,
                    rate_limited=True,
                    error=f"Groq Rate Limit Exceeded (HTTP 429): {err_text}"
                )
            else:
                return ProviderResponse(
                    content="",
                    status_code=resp.status_code,
                    source="real",
                    first_token_ms=total_ms,
                    total_ms=total_ms,
                    headers=headers_dict,
                    error=f"Groq API Error {resp.status_code}: {resp.text}"
                )

        except httpx.TimeoutException:
            total_ms = (time.perf_counter() - start_t) * 1000.0
            return ProviderResponse(
                content="",
                status_code=408,
                source="real",
                first_token_ms=total_ms,
                total_ms=total_ms,
                error="Groq request timed out."
            )
        except Exception as e:
            total_ms = (time.perf_counter() - start_t) * 1000.0
            return ProviderResponse(
                content="",
                status_code=500,
                source="real",
                first_token_ms=total_ms,
                total_ms=total_ms,
                error=f"Groq client exception: {str(e)}"
            )

    async def stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 512,
        **kwargs
    ) -> AsyncIterator[StreamChunk]:
        start_t = time.perf_counter()
        first_token_seen = False

        if not self.api_key:
            yield StreamChunk(delta="Error: Missing GROQ_API_KEY", is_first=True, is_final=True)
            return

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True
        }

        async with self.client.stream("POST", "/chat/completions", json=payload) as resp:
            if resp.status_code != 200:
                elapsed = (time.perf_counter() - start_t) * 1000.0
                yield StreamChunk(
                    delta=f"Groq Error HTTP {resp.status_code}",
                    is_first=True,
                    is_final=True,
                    elapsed_ms=elapsed
                )
                return

            async for line in resp.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                raw_data = line[6:].strip()
                if raw_data == "[DONE]":
                    break

                try:
                    chunk_json = json.loads(raw_data)
                    delta_text = chunk_json["choices"][0]["delta"].get("content", "")
                    if delta_text:
                        elapsed = (time.perf_counter() - start_t) * 1000.0
                        is_first = not first_token_seen
                        first_token_seen = True
                        yield StreamChunk(
                            delta=delta_text,
                            is_first=is_first,
                            elapsed_ms=elapsed
                        )
                except Exception:
                    continue

        elapsed = (time.perf_counter() - start_t) * 1000.0
        yield StreamChunk(delta="", is_final=True, elapsed_ms=elapsed)

    async def close(self):
        await self.client.aclose()

