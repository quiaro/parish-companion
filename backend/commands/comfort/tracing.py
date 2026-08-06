"""
Optional timing/metadata-only tracing for the /comfort retrieval pipeline.
Callers must only ever pass non-identifying metadata into `traced`.
No-op entirely unless both langfuse keys are configured.
"""

from contextlib import contextmanager
from typing import Any, Generator, Literal

from langfuse import Langfuse, LangfuseGeneration, LangfuseSpan

from config import settings

_ENABLED = bool(settings.langfuse_public_key and settings.langfuse_secret_key)

client: Langfuse | None = None
if _ENABLED:
    client = Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        base_url=settings.langfuse_base_url or None,
    )


@contextmanager
def traced(
    name: str, as_type: Literal["span", "generation"] = "span", model: str | None = None, **metadata: Any
) -> Generator[LangfuseGeneration | LangfuseSpan | None, None, None]:
    """
    Yields the Langfuse span (or None if tracing is disabled). `metadata` known up front
    is attached at creation. Callers can also attach more via span.update(metadata={...})
    once the outcome is known (e.g. which retrieval branch was taken). Never pass raw message text, telegram_user_id, or session_id here.
    """
    if client is None:
        yield None
        return

    if as_type == "generation":
        cm = client.start_as_current_observation(
            as_type="generation", name=name, model=model, metadata=metadata or None
        )
    else:
        cm = client.start_as_current_observation(as_type="span", name=name, metadata=metadata or None)

    with cm as span:
        yield span
