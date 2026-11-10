"""
Tests for Calibrated Model Stand-in Simulator across all profiles.
"""

import asyncio
import pytest
from app.providers.simulator_provider import StandInSimulatorProvider

def test_simulator_normal_profile():
    async def _run():
        sim = StandInSimulatorProvider(profile="normal", seed=42)
        messages = [{"role": "user", "content": "What is scaled dot product attention?"}]
        resp = await sim.generate(messages)

        assert resp.status_code == 200
        assert resp.source == "stand-in"
        assert resp.first_token_ms > 0
        assert resp.total_ms > resp.first_token_ms
        assert len(resp.content) > 20
        assert "x-ratelimit-remaining-requests" in resp.headers

    asyncio.run(_run())

def test_simulator_rate_limited_profile():
    async def _run():
        # Configure tiny RPM limit of 2 to trigger 429
        sim = StandInSimulatorProvider(profile="rate_limited", seed=42, rpm_limit=2)
        messages = [{"role": "user", "content": "Hello"}]

        resp1 = await sim.generate(messages)
        assert resp1.status_code == 200

        resp2 = await sim.generate(messages)
        assert resp2.status_code == 200

        # 3rd request breaches RPM limit
        resp3 = await sim.generate(messages)
        assert resp3.status_code == 429
        assert resp3.rate_limited is True
        assert resp3.retry_after_s is not None
        assert "retry-after" in resp3.headers

    asyncio.run(_run())

def test_simulator_daily_quota_exhausted_profile():
    async def _run():
        sim = StandInSimulatorProvider(profile="daily_quota_exhausted", seed=42)
        messages = [{"role": "user", "content": "Tell me about Moshi"}]
        resp = await sim.generate(messages)

        assert resp.status_code == 429
        assert resp.rate_limited is True
        assert resp.retry_after_s == 86400.0
        assert "daily" in resp.error.lower()

    asyncio.run(_run())

def test_simulator_streaming():
    async def _run():
        sim = StandInSimulatorProvider(profile="normal", seed=42)
        messages = [{"role": "user", "content": "What is H-Net?"}]

        chunks = []
        async for chunk in sim.stream(messages):
            chunks.append(chunk)

        assert len(chunks) > 5
        assert chunks[0].is_first is True
        assert chunks[-1].is_final is True
        full_text = "".join(c.delta for c in chunks)
        assert len(full_text) > 20

    asyncio.run(_run())
