"""
Stage 7: Response Delivery and Observability for THE RELAY.
Handles streaming token emission, timing instrumentation, and metrics logging.
"""

import sys
import time
from typing import AsyncIterator, List, Optional
from app.core.logging import RequestTrace
from app.providers.base import BaseProvider, StreamChunk

class ResponseDeliveryManager:
    @staticmethod
    async def deliver_stream(
        stream_iter: AsyncIterator[StreamChunk],
        trace: RequestTrace,
        console_output: bool = True
    ) -> str:
        """Emits tokens incrementally while recording precise arrival milestones."""
        accumulated_text = []

        async for chunk in stream_iter:
            if chunk.is_first:
                trace.mark_first_token()
            if chunk.delta:
                accumulated_text.append(chunk.delta)
                if console_output:
                    sys.stdout.write(chunk.delta)
                    sys.stdout.flush()

        if console_output:
            sys.stdout.write("\n")
            sys.stdout.flush()

        full_content = "".join(accumulated_text)
        return full_content

