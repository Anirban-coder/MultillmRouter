"""
The heart of the system.

call_llm(messages) tries each provider in PROVIDERS (in order).
If one fails (rate limit / quota / timeout / server error), it moves
to the next one automatically — using the exact same `messages` list,
so the conversation context is never lost.

You can also force a single specific provider (no failover) by passing
forced_provider="groq" (or any provider name from providers.py).
"""

import os
import litellm
from app.providers import PROVIDERS

# Don't let litellm print your keys or crash the process on non-fatal warnings
litellm.suppress_debug_info = True


class AllProvidersFailedError(Exception):
    pass


def _prep_env(provider: dict):
    """Make sure the API key litellm expects is actually set for this call."""
    real_key = os.getenv(provider["api_key_env"])
    if not real_key:
        return None
    if provider.get("litellm_key_env"):
        os.environ[provider["litellm_key_env"]] = real_key
    return real_key


def call_llm(messages: list[dict], max_tokens: int = 1000, forced_provider: str = None) -> dict:
    """
    messages: standard OpenAI-style list, e.g.
        [{"role": "user", "content": "hello"}]
    forced_provider: if set (e.g. "groq"), ONLY tries that provider — no
        auto-failover. If None, tries all providers in order like normal.

    Returns: {"content": str, "provider_used": str, "attempts": [list of tried providers]}
    """
    attempts = []

    provider_list = PROVIDERS
    if forced_provider:
        provider_list = [p for p in PROVIDERS if p["name"] == forced_provider]
        if not provider_list:
            raise AllProvidersFailedError(f"Unknown provider '{forced_provider}'")

    for provider in provider_list:
        api_key = _prep_env(provider)
        if not api_key:
            # No key in .env for this provider yet — skip it silently
            attempts.append({"provider": provider["name"], "status": "skipped_no_key"})
            continue

        call_kwargs = {
            "model": provider["model"],
            "messages": messages,
            "max_tokens": max_tokens,
            "timeout": 30,
        }

        # NVIDIA / Cloudflare need an explicit api_base + api_key passed directly
        if provider.get("api_base"):
            call_kwargs["api_base"] = provider["api_base"]
            call_kwargs["api_key"] = api_key

        try:
            response = litellm.completion(**call_kwargs)
            content = response.choices[0].message.content
            attempts.append({"provider": provider["name"], "status": "success"})
            return {
                "content": content,
                "provider_used": provider["name"],
                "attempts": attempts,
            }

        except litellm.RateLimitError as e:
            attempts.append({"provider": provider["name"], "status": "rate_limited", "error": str(e)})
            continue  # jump to next provider — this is the "auto-switch" you asked for

        except litellm.AuthenticationError as e:
            attempts.append({"provider": provider["name"], "status": "bad_api_key", "error": str(e)})
            continue

        except Exception as e:
            attempts.append({"provider": provider["name"], "status": "error", "error": str(e)})
            continue

    raise AllProvidersFailedError(f"Every provider failed or had no key set. Attempts: {attempts}")