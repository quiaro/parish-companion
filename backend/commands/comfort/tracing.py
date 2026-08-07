"""
Optional timing/metadata-only tracing.
No-op entirely unless both langfuse keys are configured.
"""

from contextlib import contextmanager
from typing import Any, Generator, Literal

from langfuse import Langfuse, LangfuseGeneration, LangfuseRetriever, LangfuseSpan, propagate_attributes

from config import settings

_ENABLED = bool(settings.langfuse_public_key and settings.langfuse_secret_key)

# Every key any caller is allowed to put in `metadata=` for tracing purposes. Anything not
# listed is redacted, including the OpenAI auto-captured prompts/completions, which land in 
# `input`/`output`, not `metadata`, but go through the exact same masking call.
_ALLOWED_METADATA_KEYS = {"k", "outcome", "candidates_checked", "similarity_score"}


def _mask(*, data: Any, **_: Any) -> Any:
    """
    Fails closed: the only data ever let through is a flat dict containing exclusively
    primitive values under `_ALLOWED_METADATA_KEYS`. This is deliberately an allow-list 
    (recognize our own known-safe shapes) rather than a deny-list.
    """
    if data is None:
        return None
    if (
        isinstance(data, dict)
        and set(data.keys()) <= _ALLOWED_METADATA_KEYS
        and all(isinstance(v, (str, int, float, bool)) or v is None for v in data.values())
    ):
        return data
    return "[redacted]"


# Mirrors the SDK's own convention for a deliberately-disabled client (seen in 
# langfuse's get_client() fallback path) rather than leaving credentials empty by omission.
client = Langfuse(
    public_key=settings.langfuse_public_key or "disabled",
    secret_key=settings.langfuse_secret_key or "disabled",
    base_url=settings.langfuse_base_url or None,
    tracing_enabled=_ENABLED,
    mask=_mask,
)


@contextmanager
def traced(
    name: str, as_type: Literal["span", "retriever"] = "span", **metadata: Any
) -> Generator[LangfuseGeneration | LangfuseSpan | LangfuseRetriever, None, None]:
    """
    Yields the Langfuse span — a genuine no-op when tracing is disabled. 
    Never pass a metadata key without also adding it to _ALLOWED_METADATA_KEYS above.
    """
    with client.start_as_current_observation(as_type=as_type, name=name, metadata=metadata or None) as span:
        yield span


@contextmanager
def traced_session(session_id: str) -> Generator[None, None, None]:
    """
    Groups every span/generation created within this context under one Langfuse
    session, so a single /comfort request's classify -> retrieve -> frame steps show
    up together in the Langfuse UI. `session_id` must be a fresh, random, per-request
    token — never telegram_user_id nor the app's own Redis flow session id (itself 
    derived from the Telegram chat id). Unlike `metadata=` above, session_id is a 
    first-class span attribute that bypasses `_mask` entirely.
    """
    with propagate_attributes(session_id=session_id):
        yield
